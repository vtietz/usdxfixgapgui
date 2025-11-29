"""
Main Window Initialization

Creates and runs the main GUI window with all components.
Separated from main entry point for better code organization.
"""

import os
import sys
import logging

from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QSplitter,
)
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
from ui.splash import create_splash_screen

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

    # Initialize database and confirm cache reset if needed
    if not _initialize_cache_and_confirm_rescan():
        return 0  # User cancelled

    # Create app data and actions
    data = AppData()
    data.config = config
    data.capabilities = capabilities
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
    _set_application_icon(app)

    # Create main window
    window = _create_main_window(app, config, gpu_dialog)

    # Optional splash screen before showing the full UI
    splash_ctx = create_splash_screen(app)

    # Connect to aboutToQuit to save geometry and filter state before closing
    app.aboutToQuit.connect(lambda: _save_window_state(window, config, data))

    # Create UI components
    menuBar, songStatus, songListView, mediaPlayerComponent, taskQueueViewer, logViewer = _create_ui_components(
        data, actions, log_file_path
    )

    # Connect signals
    _connect_ui_signals(data, menuBar, songStatus, app, mediaPlayerComponent)

    # Setup layout
    _setup_window_layout(
        window,
        config,
        menuBar,
        songStatus,
        songListView,
        mediaPlayerComponent,
        taskQueueViewer,
        logViewer,
        capabilities,
    )

    # Log runtime information and check dependencies
    _log_runtime_info_and_check_dependencies()

    # Defer showing the main window until splash finishes
    _schedule_window_show(
        app,
        splash_ctx,
        window,
        actions,
        config,
        data,
        menuBar,
        logViewer,
    )

    # Start event loop
    return app.exec()


# ==========================
# Helper functions
# ==========================


def _initialize_cache_and_confirm_rescan() -> bool:
    """Initialize song cache and confirm rescan if needed. Returns False if user cancels."""
    db_path, cache_was_cleared = initialize_song_cache()
    logger.debug("Song cache database initialized at: %s", db_path)

    if not cache_was_cleared:
        return True

    logger.info("Displaying re-scan confirmation dialog to user")
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
        return False

    logger.info("User confirmed re-scan. Proceeding with application startup.")
    return True


def _set_application_icon(app):
    """Set application icon from assets."""
    import os

    icon_path = resource_path("assets/usdxfixgap-icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
        logger.debug("Loaded icon from: %s", icon_path)
    else:
        logger.error("Icon file not found at expected path: %s", icon_path)


def _create_main_window(app, config, gpu_dialog):
    """Create and configure main window with geometry restoration."""
    window = QWidget()
    window.setWindowTitle("USDX FixGap")
    if gpu_dialog:
        app.setProperty("_gpu_dialog_ref", gpu_dialog)

    # Restore window geometry
    if config.window_x >= 0 and config.window_y >= 0:
        window.move(config.window_x, config.window_y)
    window.resize(config.window_width, config.window_height)
    window.setMinimumSize(600, 600)

    return window
def _save_window_state(window, config, data):
    """Save window geometry, maximized state, and filter state."""
    if not window.isMaximized():
        geometry = window.geometry()
        config.window_width = geometry.width()
        config.window_height = geometry.height()
        config.window_x = geometry.x()
        config.window_y = geometry.y()

    config.window_maximized = window.isMaximized()

    # Save filter state (defensive: normalize to strings)
    try:
        config.filter_text = data.songs.filter_text
        # Handle both str and SongStatus enum values defensively
        config.filter_statuses = [
            (s.name if hasattr(s, "name") else str(s)) for s in data.songs.filter
        ]
    except Exception as e:
        logger.warning("Failed to save filter state: %s. Using defaults.", e)
        config.filter_text = ""
        config.filter_statuses = []

    config.save()

    if window.isMaximized():
        logger.debug("Window state saved: maximized")
    else:
        logger.debug(
            "Window geometry saved: %sx%s at (%s, %s)",
            config.window_width,
            config.window_height,
            config.window_x,
            config.window_y,
        )
    logger.debug("Filter state saved: text='%s', statuses=%s", config.filter_text, config.filter_statuses)


def _create_ui_components(data, actions, log_file_path):
    """Create all UI components."""
    menuBar = MenuBar(actions, data)
    songStatus = SongsStatusVisualizer(data.songs, data)
    songListView = SongListWidget(data.songs, actions, data)
    mediaPlayerComponent = MediaPlayerComponent(data, actions)
    taskQueueViewer = TaskQueueViewer(actions.worker_queue)
    logViewer = LogViewerWidget(log_file_path, max_lines=1000)
    return menuBar, songStatus, songListView, mediaPlayerComponent, taskQueueViewer, logViewer


def _connect_ui_signals(data, menuBar, songStatus, app, mediaPlayerComponent):
    """Connect signals between UI components."""

    def on_loading_state_changed():
        songStatus.update_visualization()

    data.songs.listChanged.connect(on_loading_state_changed)
    data.is_loading_songs_changed.connect(menuBar.updateLoadButtonState)

    if mediaPlayerComponent.globalEventFilter is not None:
        app.installEventFilter(mediaPlayerComponent.globalEventFilter)


def _setup_window_layout(
    window, config, menuBar, songStatus, songListView, mediaPlayerComponent, taskQueueViewer, logViewer, capabilities
):
    """Setup main window layout with splitters and status indicators."""
    layout = QVBoxLayout()
    layout.setContentsMargins(5, 5, 5, 5)
    layout.setSpacing(2)
    layout.addWidget(menuBar)

    # Status row
    status_row = _create_status_row(songStatus, capabilities)
    layout.addLayout(status_row)

    # Main splitter with nested second splitter
    main_splitter = _create_main_splitter(config, songListView, mediaPlayerComponent, taskQueueViewer, logViewer)
    layout.addWidget(main_splitter)

    window.setLayout(layout)


def _create_status_row(songStatus, capabilities):
    """Create status row with song status and detection mode indicator."""
    status_row = QHBoxLayout()
    status_row.setSpacing(5)
    status_row.addWidget(songStatus, 1)

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
    return status_row


def _create_main_splitter(config, songListView, mediaPlayerComponent, taskQueueViewer, logViewer):
    """Create main splitter with nested second splitter."""
    main_splitter = QSplitter(Qt.Orientation.Vertical)
    main_splitter.setChildrenCollapsible(False)
    main_splitter.addWidget(songListView)

    # Second splitter for media player vs task/log
    second_splitter = QSplitter(Qt.Orientation.Vertical)
    second_splitter.setChildrenCollapsible(False)
    second_splitter.addWidget(mediaPlayerComponent)

    # Task/Log panel
    task_log_panel = QWidget()
    task_log_layout = QVBoxLayout(task_log_panel)
    task_log_layout.setContentsMargins(0, 0, 0, 0)
    task_log_layout.setSpacing(2)
    task_log_layout.addWidget(taskQueueViewer, 1)
    task_log_layout.addWidget(logViewer, 1)
    task_log_panel.setLayout(task_log_layout)

    second_splitter.addWidget(task_log_panel)

    # Restore second splitter position
    if config.second_splitter_pos:
        second_splitter.setSizes(config.second_splitter_pos)
    else:
        second_splitter.setSizes([200, 200])

    second_splitter.splitterMoved.connect(lambda: _save_splitter_position(config, second_splitter, "second"))

    main_splitter.addWidget(second_splitter)

    # Restore main splitter position
    if config.main_splitter_pos:
        main_splitter.setSizes(config.main_splitter_pos)
    else:
        total_height = 900
        main_splitter.setSizes([int(total_height * 0.66), int(total_height * 0.34)])

    main_splitter.splitterMoved.connect(lambda: _save_splitter_position(config, main_splitter, "main"))

    return main_splitter


def _save_splitter_position(config, splitter, name):
    """Save splitter position to config."""
    pos = splitter.sizes()
    if name == "main":
        config.main_splitter_pos = pos
    elif name == "second":
        config.second_splitter_pos = pos
    config.save()
    logger.debug("%s splitter position saved: %s", name.capitalize(), pos)


def _log_runtime_info_and_check_dependencies():
    """Log runtime information and check dependencies."""
    try:
        import PySide6

        qt_version = getattr(PySide6, "__version__", "unknown")
        logger.debug("Runtime PySide6 version: %s", qt_version)
    except Exception:
        logger.debug("Runtime PySide6 version: unknown")
    logger.debug("Python Executable: %s", sys.executable)
    logger.debug("PYTHONPATH: %s", sys.path)

    dependencies = [("ffmpeg", "-version")]
    if not check_dependencies(dependencies):
        logger.error("Some dependencies are not installed.")

    available_audio_outputs = QMediaDevices.audioOutputs()
    if not available_audio_outputs:
        logger.error("No audio output devices available.")
    else:
        logger.debug("Available audio outputs: %s", available_audio_outputs)

    try:
        supported_mime_types = getattr(QMediaDevices, "supportedMimeTypes", lambda: [])()
        logger.debug("Available multimedia backends: %s", supported_mime_types)
    except AttributeError:
        logger.debug("Multimedia backend query not available (not critical - app uses its own audio processing)")


def _setup_shutdown_sequence(app, data, logViewer):
    """Setup proper shutdown sequence for cleanup."""
    app.aboutToQuit.connect(lambda: data.worker_queue.shutdown())
    app.aboutToQuit.connect(shutdown_asyncio)
    app.aboutToQuit.connect(logViewer.cleanup)
    app.aboutToQuit.connect(shutdown_async_logging)


def _schedule_window_show(app, splash_ctx, window, actions, config, data, menuBar, logViewer):
    """Show main window after optional splash delay."""

    def _show_main_window():
        _post_window_show(app, window, actions, config, data, menuBar, logViewer)
        if splash_ctx:
            splash, _ = splash_ctx
            splash.finish(window)

    if splash_ctx:
        _, duration_ms = splash_ctx
        QTimer.singleShot(duration_ms, _show_main_window)
    else:
        _show_main_window()


def _post_window_show(app, window, actions, config, data, menuBar, logViewer):
    """Finalize UI activation once the splash screen is complete."""
    if config.window_maximized:
        window.showMaximized()
    else:
        window.show()
    actions.auto_load_last_directory()
    QTimer.singleShot(100, lambda: _restore_filter_state(config, data, menuBar))
    if config.watch_mode_default:
        actions.initial_scan_completed.connect(lambda: _auto_enable_watch_mode(actions))
    enable_dark_mode(app)
    _setup_shutdown_sequence(app, data, logViewer)
    logger.info("GUI Initialized Successfully")
    QTimer.singleShot(200, lambda: _log_delayed_start_info(data))


def _restore_filter_state(config, data, menuBar):
    """Restore filter state from config."""
    from model.song import SongStatus

    # Restore text filter
    if config.filter_text:
        data.songs.filter_text = config.filter_text
        # MenuBar renamed search input to searchBox (backward compatibility shim)
        search_widget = getattr(menuBar, "searchBox", None)
        if search_widget:
            search_widget.setText(config.filter_text)
        logger.debug("Restored text filter: '%s'", config.filter_text)

    # Restore status filters (as strings, not enums)
    if config.filter_statuses:
        try:
            # Validate status names exist in SongStatus enum
            valid_statuses = [name for name in config.filter_statuses if name in SongStatus.__members__]
            if valid_statuses:
                # Set as strings directly (Songs.filter expects List[str])
                data.songs.filter = valid_statuses
                menuBar.filterDropdown.setSelectedItems(valid_statuses)
                logger.debug("Restored status filters: %s", valid_statuses)

            # Log any invalid statuses
            invalid = set(config.filter_statuses) - set(valid_statuses)
            if invalid:
                logger.warning("Ignored invalid status filters: %s", invalid)
        except Exception as e:
            logger.warning("Failed to restore status filters: %s", e)


def _auto_enable_watch_mode(actions):
    """Auto-enable watch mode after initial scan completes (if configured)."""
    try:
        if actions.can_enable_watch_mode():
            logger.info("Auto-enabling watch mode (watch_mode_default=True)")
            success = actions.start_watch_mode()
            if success:
                logger.info("Watch mode auto-enabled successfully")
            else:
                logger.warning("Failed to auto-enable watch mode")
        else:
            logger.debug("Cannot auto-enable watch mode - requirements not met")
    except Exception as e:
        logger.error("Error auto-enabling watch mode: %s", e, exc_info=True)


def _log_delayed_start_info(data):
    """Log delayed start information."""
    logger.info("Configuration file: %s", data.config.config_path)
    logger.info("Application ready for user interaction")
