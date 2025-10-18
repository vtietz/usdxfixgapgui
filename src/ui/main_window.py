"""
Main Window Initialization

Creates and runs the main GUI window with all components.
Separated from main entry point for better code organization.
"""

import sys
import logging
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout
from PySide6.QtMultimedia import QMediaDevices
from PySide6.QtGui import QIcon
from PySide6.QtCore import QTimer

from actions import Actions
from app.app_data import AppData
from common.database import initialize_song_cache
from common.utils.async_logging import shutdown_async_logging

from utils.enable_darkmode import enable_dark_mode
from utils.check_dependencies import check_dependencies
from utils.files import resource_path
from utils.gpu_startup_logger import show_gpu_pack_dialog_if_needed

from ui.menu_bar import MenuBar
from ui.song_status import SongsStatusVisualizer
from ui.mediaplayer import MediaPlayerComponent
from ui.songlist.songlist_widget import SongListWidget
from ui.task_queue_viewer import TaskQueueViewer
from ui.log_viewer import LogViewerWidget

logger = logging.getLogger(__name__)


def create_and_run_gui(config, gpu_enabled, log_file_path):
    """
    Create and run the main GUI application.

    Args:
        config: Application config object
        gpu_enabled: Boolean indicating if GPU bootstrap succeeded
        log_file_path: Path to log file for log viewer

    Returns:
        Exit code for the application
    """

    # Initialize database before creating AppData
    db_path = initialize_song_cache()
    logger.info(f"Song cache database initialized at: {db_path}")

    # Create app data and actions
    data = AppData()
    data.config = config
    actions = Actions(data)

    # Create QApplication
    app = QApplication(sys.argv)

    # Show GPU Pack download dialog if needed (non-modal, so keep reference)
    gpu_dialog = show_gpu_pack_dialog_if_needed(config, gpu_enabled)

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
    window.setWindowTitle("USDX Gap Fix Gui")
    # Store dialog reference to prevent garbage collection
    if gpu_dialog:
        window._gpu_dialog_ref = gpu_dialog

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
            logger.debug(f"Window state saved: maximized")
        else:
            logger.debug(f"Window geometry saved: {config.window_width}x{config.window_height} at ({config.window_x}, {config.window_y})")

    # Connect to aboutToQuit to save geometry before closing
    app.aboutToQuit.connect(save_window_geometry)

    # Create UI components
    menuBar = MenuBar(actions, data)
    songStatus = SongsStatusVisualizer(data.songs)
    songListView = SongListWidget(data.songs, actions, data)
    mediaPlayerComponent = MediaPlayerComponent(data, actions)
    taskQueueViewer = TaskQueueViewer(actions.worker_queue)
    logViewer = LogViewerWidget(log_file_path, max_lines=1000)

    # Install event filter
    app.installEventFilter(mediaPlayerComponent.globalEventFilter)

    # Setup layout
    layout = QVBoxLayout()
    layout.addWidget(menuBar)
    layout.addWidget(songStatus)
    layout.addWidget(songListView, 2)
    layout.addWidget(mediaPlayerComponent, 1)
    layout.addWidget(taskQueueViewer, 1)
    layout.addWidget(logViewer)

    window.setLayout(layout)

    # Log runtime information
    try:
        from PySide6.QtCore import __version__ as qt_version
        logger.debug(f"Runtime PySide6 version: {qt_version}")
    except:
        logger.debug("Runtime PySide6 version: unknown")
    logger.debug(f"Python Executable: {sys.executable}")
    logger.debug(f"PYTHONPATH: {sys.path}")

    # Check dependencies
    dependencies = [
        ('ffmpeg', '-version'),
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
        supported_mime_types = QMediaDevices.supportedMimeTypes()
        logger.debug(f"Available multimedia backends: {supported_mime_types}")
    except AttributeError:
        logger.warning("Unable to retrieve supported multimedia backends.")

    # Show window
    window.show()

    # Auto-load last directory
    actions.auto_load_last_directory()

    # Enable dark mode
    enable_dark_mode(app)

    # Setup proper shutdown
    app.aboutToQuit.connect(shutdown_async_logging)
    app.aboutToQuit.connect(lambda: data.worker_queue.shutdown())
    app.aboutToQuit.connect(logViewer.cleanup)

    # Log completion and give async logger a moment to flush
    # This ensures initial logs appear in the log viewer
    logger.info("=== GUI Initialized Successfully ===")

    # Use QTimer to allow event loop to process initial logs
    def delayed_start():
        logger.info("Application ready for user interaction")

    QTimer.singleShot(200, delayed_start)  # 200ms delay

    # Start event loop
    return app.exec()
