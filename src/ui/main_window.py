"""
Main Window Initialization

Creates and runs the main GUI window with all components.
Separated from main entry point for better code organization.
"""

import sys
import logging

from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QMessageBox, QSplitter
from PySide6.QtMultimedia import QMediaDevices
from PySide6.QtGui import QIcon
from PySide6.QtCore import QTimer, Qt

from actions import Actions
from app.app_data import AppData
from common.database import initialize_song_cache
from common.utils.async_logging import shutdown_async_logging

from utils.enable_darkmode import enable_dark_mode
from utils.check_dependencies import check_dependencies
from utils.run_async import shutdown_asyncio
from utils.files import resource_path

from ui.menu_bar import MenuBar
from ui.song_status import SongsStatusVisualizer
from ui.mediaplayer import MediaPlayerComponent
from ui.songlist.songlist_widget import SongListWidget
from ui.task_queue_viewer import TaskQueueViewer
from ui.log_viewer import LogViewerWidget

logger = logging.getLogger(__name__)


def create_and_run_gui(config, gpu_enabled, log_file_path, capabilities):
    """
    Create and run the main GUI application.

    Args:
        config: Application config object
        gpu_enabled: Boolean indicating if GPU bootstrap succeeded
        log_file_path: Path to log file for log viewer
        capabilities: SystemCapabilities object from startup checks

    Returns:
        Exit code for the application
    """

    # Initialize database before creating AppData
    db_path, cache_was_cleared = initialize_song_cache()
    logger.info(f"Song cache database initialized at: {db_path}")

    # If cache was cleared due to version upgrade, show confirmation dialog
    if cache_was_cleared:
        logger.info("Displaying re-scan confirmation dialog to user")
        # Create minimal QApplication for the dialog
        temp_app = QApplication.instance()
        if temp_app is None:
            temp_app = QApplication(sys.argv)

        msgBox = QMessageBox()
        msgBox.setIcon(QMessageBox.Icon.Information)
        msgBox.setWindowTitle("Re-scan Required")
        msgBox.setText("Due to application upgrade, a complete re-scan of all songs is required.")
        msgBox.setInformativeText("This will happen automatically on startup. Do you want to start now?")
        msgBox.setStandardButtons(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
        msgBox.button(QMessageBox.StandardButton.Ok).setText("Start Re-scan")
        msgBox.button(QMessageBox.StandardButton.Cancel).setText("Quit Application")
        msgBox.setDefaultButton(QMessageBox.StandardButton.Ok)

        result = msgBox.exec()

        if result == QMessageBox.StandardButton.Cancel:
            logger.info("User cancelled re-scan. Exiting application.")
            return 0  # Clean exit

        logger.info("User confirmed re-scan. Proceeding with application startup.")

    # Create app data and actions
    data = AppData()
    data.config = config
    data.capabilities = capabilities  # Store system capabilities from startup checks
    actions = Actions(data)

    # QApplication already created in main() for splash screen
    app = QApplication.instance()
    if app is None:
        logger.warning("QApplication not found, creating new instance")
        app = QApplication(sys.argv)

    # GPU Pack download dialog is now handled by the startup wizard (splash screen)
    # Legacy dialog disabled to avoid duplicate prompts
    gpu_dialog = None  # show_gpu_pack_dialog_if_needed(config, gpu_enabled)

    # Set application icon
    icon_path = resource_path("assets/usdxfixgap-icon.ico")
    import os

    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
        logger.info(f"Loaded icon from: {icon_path}")
    else:
        logger.error(f"Icon file not found at expected path: {icon_path}")

    # Create main window
    window = QWidget()
    window.setWindowTitle("USDX FixGap")
    # Store dialog reference to prevent garbage collection
    if gpu_dialog:
        app.setProperty("_gpu_dialog_ref", gpu_dialog)

    # Restore window geometry from config
    if config.window_x >= 0 and config.window_y >= 0:
        window.move(config.window_x, config.window_y)
    window.resize(config.window_width, config.window_height)
    window.setMinimumSize(600, 600)

    # Restore maximized state
    if config.window_maximized:
        window.showMaximized()

    # Save window geometry and state on close
    def save_window_geometry():
        # Only save normal geometry if not maximized
        # (Qt provides incorrect geometry when maximized)
        if not window.isMaximized():
            geometry = window.geometry()
            config.window_width = geometry.width()
            config.window_height = geometry.height()
            config.window_x = geometry.x()
            config.window_y = geometry.y()

        # Always save maximized state
        config.window_maximized = window.isMaximized()
        config.save()

        if window.isMaximized():
            logger.debug("Window state saved: maximized")
        else:
            logger.debug(
                f"Window geometry saved: {config.window_width}x{config.window_height} at ({config.window_x}, {config.window_y})"
            )

    # Connect to aboutToQuit to save geometry before closing
    app.aboutToQuit.connect(save_window_geometry)

    # Create UI components
    menuBar = MenuBar(actions, data)
    songStatus = SongsStatusVisualizer(data.songs, data)
    songListView = SongListWidget(data.songs, actions, data)
    mediaPlayerComponent = MediaPlayerComponent(data, actions)
    taskQueueViewer = TaskQueueViewer(actions.worker_queue)
    logViewer = LogViewerWidget(log_file_path, max_lines=1000)

    # Connect loading state changes to status visualizer
    def on_loading_state_changed():
        songStatus.update_visualization()

    # Monitor is_loading_songs changes (will be set in CoreActions)
    # We'll update every time songs are added during loading
    data.songs.listChanged.connect(on_loading_state_changed)

    # Connect loading state to menu bar to enable/disable buttons during scan
    data.is_loading_songs_changed.connect(menuBar.updateLoadButtonState)

    # Install event filter
    if mediaPlayerComponent.globalEventFilter is not None:
        app.installEventFilter(mediaPlayerComponent.globalEventFilter)

    # Setup layout
    layout = QVBoxLayout()
    layout.setContentsMargins(5, 5, 5, 5)
    layout.setSpacing(2)
    layout.addWidget(menuBar)

    # Status row: song status + detection mode indicator
    status_row = QHBoxLayout()
    status_row.setSpacing(5)
    status_row.addWidget(songStatus, 1)  # Song status takes most space

    # Detection mode indicator
    detection_label = QLabel()
    detection_label.setFixedHeight(20)
    detection_label.setStyleSheet(
        "padding: 2px 8px; font-size: 8px; background-color: #2E2E2E; color: rgba(255, 255, 255, 0.7);"
    )

    if capabilities and capabilities.can_detect:
        if capabilities.has_cuda:
            detection_label.setText("GPU")
            detection_label.setToolTip(
                f"Gap detection using GPU acceleration\nGPU: {capabilities.gpu_name or 'CUDA available'}"
            )
        else:
            detection_label.setText("CPU")
            detection_label.setToolTip("Gap detection using CPU (slower)\nTip: Install GPU Pack for faster detection")
    else:
        detection_label.setText("No Detection")
        if capabilities and not capabilities.has_torch:
            detection_label.setToolTip(f"PyTorch not available: {capabilities.torch_error or 'Not installed'}")
        elif capabilities and not capabilities.has_ffmpeg:
            detection_label.setToolTip("FFmpeg not available\nInstall FFmpeg to enable gap detection")
        else:
            detection_label.setToolTip("Gap detection disabled: System requirements not met")

    status_row.addWidget(detection_label)

    layout.addLayout(status_row)

    # Create main splitter to divide song list from bottom panel
    main_splitter = QSplitter(Qt.Orientation.Vertical)
    main_splitter.setChildrenCollapsible(False)  # Prevent panels from collapsing

    # Top section: song list
    main_splitter.addWidget(songListView)

    # Bottom section: nested splitter for media player vs task/log panel
    second_splitter = QSplitter(Qt.Orientation.Vertical)
    second_splitter.setChildrenCollapsible(False)

    # Media player (waveform is now flexible)
    second_splitter.addWidget(mediaPlayerComponent)

    # Task/Log panel (equal height)
    task_log_panel = QWidget()
    task_log_layout = QVBoxLayout(task_log_panel)
    task_log_layout.setContentsMargins(0, 0, 0, 0)
    task_log_layout.setSpacing(2)
    task_log_layout.addWidget(taskQueueViewer, 1)  # Equal stretch
    task_log_layout.addWidget(logViewer, 1)  # Equal stretch
    task_log_panel.setLayout(task_log_layout)

    second_splitter.addWidget(task_log_panel)

    # Restore second splitter position from config (default 1:1 ratio for media vs task/log)
    if config.second_splitter_pos:
        second_splitter.setSizes(config.second_splitter_pos)
    else:
        # Fallback default: 1:1 ratio
        second_splitter.setSizes([200, 200])

    # Save second splitter position on move
    def save_second_splitter_position():
        config.second_splitter_pos = second_splitter.sizes()
        config.save()
        logger.debug(f"Second splitter position saved: {config.second_splitter_pos}")

    second_splitter.splitterMoved.connect(save_second_splitter_position)

    # Add second splitter to main splitter
    main_splitter.addWidget(second_splitter)

    # Restore main splitter position from config (default 2:1 ratio)
    if config.main_splitter_pos:
        main_splitter.setSizes(config.main_splitter_pos)
    else:
        # Fallback default: 2:1 ratio
        total_height = 900  # Approximate default window height
        main_splitter.setSizes([int(total_height * 0.66), int(total_height * 0.34)])

    # Save main splitter position on move
    def save_splitter_position():
        config.main_splitter_pos = main_splitter.sizes()
        config.save()
        logger.debug(f"Main splitter position saved: {config.main_splitter_pos}")

    main_splitter.splitterMoved.connect(save_splitter_position)

    layout.addWidget(main_splitter)

    window.setLayout(layout)

    # Log runtime information
    try:
        import PySide6

        qt_version = getattr(PySide6, "__version__", "unknown")
        logger.debug(f"Runtime PySide6 version: {qt_version}")
    except Exception:
        logger.debug("Runtime PySide6 version: unknown")
    logger.debug(f"Python Executable: {sys.executable}")
    logger.debug(f"PYTHONPATH: {sys.path}")

    # Check dependencies
    dependencies = [
        ("ffmpeg", "-version"),
    ]
    if not check_dependencies(dependencies):
        logger.error("Some dependencies are not installed.")

    # Check audio devices
    available_audio_outputs = QMediaDevices.audioOutputs()
    if not available_audio_outputs:
        logger.error("No audio output devices available.")
    else:
        logger.debug(f"Available audio outputs: {available_audio_outputs}")

    # Check multimedia backends
    try:
        supported_mime_types = getattr(QMediaDevices, "supportedMimeTypes", lambda: [])()
        logger.debug(f"Available multimedia backends: {supported_mime_types}")
    except AttributeError:
        logger.debug("Multimedia backend query not available (not critical - app uses its own audio processing)")

    # Show window
    window.show()

    # Auto-load last directory
    actions.auto_load_last_directory()

    # Enable dark mode
    enable_dark_mode(app)

    # Setup proper shutdown sequence
    # Order matters: stop taking new work, wait for workers, stop async loop, cleanup UI
    app.aboutToQuit.connect(lambda: data.worker_queue.shutdown())  # Cancel tasks and wait
    app.aboutToQuit.connect(shutdown_asyncio)  # Stop asyncio event loop and thread
    app.aboutToQuit.connect(logViewer.cleanup)  # Cleanup UI components
    app.aboutToQuit.connect(shutdown_async_logging)  # Final logging shutdown

    # Log completion and give async logger a moment to flush
    # This ensures initial logs appear in the log viewer
    logger.info("GUI Initialized Successfully")

    # Use QTimer to allow event loop to process initial logs
    def delayed_start():
        logger.info(f"Configuration file: {data.config.config_path}")
        logger.info("Application ready for user interaction")

    QTimer.singleShot(200, delayed_start)  # 200ms delay

    # Start event loop
    return app.exec()
