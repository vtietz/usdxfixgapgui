import sys
import os
import logging

from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout
from PySide6.QtCore import __version__
from PySide6.QtMultimedia import QMediaDevices
from PySide6.QtGui import QIcon


from actions import Actions
from app.app_data import AppData, Config
from common.database import initialize_song_cache
from common.utils.async_logging import setup_async_logging, shutdown_async_logging

from utils.enable_darkmode import enable_dark_mode
from utils.check_dependencies import check_dependencies
from utils.files import get_app_dir, resource_path

from ui.menu_bar import MenuBar
from ui.song_status import SongsStatusVisualizer
from ui.mediaplayer import MediaPlayerComponent
from ui.songlist.songlist_widget import SongListWidget
from ui.task_queue_viewer import TaskQueueViewer

def main():
    # First create config to get log level before configuring logging
    config = Config()

    # --- Async Logging Setup ---
    log_file_path = os.path.join(get_app_dir(), 'usdxfixgap.log')
    setup_async_logging(
        log_level=config.log_level,
        log_file_path=log_file_path,
        max_bytes=10*1024*1024,  # 10MB
        backup_count=3
    )
    
    logger = logging.getLogger(__name__)
    logger.info(f"Application started with log level: {config.log_level_str}")
    # --- End Logging Setup ---

    # Initialize database before creating AppData
    db_path = initialize_song_cache()
    logger.info(f"Song cache database initialized at: {db_path}")

    data = AppData()
    data.config = config  # Make sure AppData uses our already created config
    actions = Actions(data)

    app = QApplication(sys.argv)

    # Example usage - This should now work correctly with the bundled asset
    icon_path = resource_path("assets/usdxfixgap-icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
        logger.info(f"Loaded icon from: {icon_path}")
    else:
        logger.error(f"Icon file not found at expected path: {icon_path}")

    # Create the main window and set its properties
    window = QWidget()
    window.setWindowTitle("USDX Gap Fix Gui")
    window.resize(800, 600)
    window.setMinimumSize(600, 600)

    menuBar = MenuBar(actions, data)
    songStatus = SongsStatusVisualizer(data.songs)
    songListView = SongListWidget(data.songs, actions, data)
    mediaPlayerComponent = MediaPlayerComponent(data, actions)
    taskQueueViewer = TaskQueueViewer(actions.worker_queue)

    app.installEventFilter(mediaPlayerComponent.globalEventFilter)

    # Set up the layout and add your components
    layout = QVBoxLayout()
    layout.addWidget(menuBar)
    layout.addWidget(songStatus)
    layout.addWidget(songListView, 2)  # Adjust stretch factor as needed
    layout.addWidget(mediaPlayerComponent, 1)  # Adjust stretch factor as needed
    layout.addWidget(taskQueueViewer, 1)  # Adjust stretch factor as needed

    window.setLayout(layout)

    logger.debug("Runtime PySide6 version: %s", __version__)  # Updated logging
    logger.debug(f"Python Executable: {sys.executable}")
    logger.debug(f"PYTHONPATH: {sys.path}")

    # Example usage
    dependencies = [
        ('spleeter', '--version'),
        ('ffmpeg', '-version'),  # Note that ffmpeg uses '-version' instead of '--version'
    ]
    if(not check_dependencies(dependencies)):
        logger.error("Some dependencies are not installed.")
        #sys.exit(1)

    # Check available audio output devices
    available_audio_outputs = QMediaDevices.audioOutputs()
    if not available_audio_outputs:
        logger.error("No audio output devices available.")
    else:
        logger.debug(f"Available audio outputs: {available_audio_outputs}")

    # Check available multimedia backends
    try:
        supported_mime_types = QMediaDevices.supportedMimeTypes()
        logger.debug(f"Available multimedia backends: {supported_mime_types}")
    except AttributeError:
        logger.warning("Unable to retrieve supported multimedia backends. This feature may not be available in your PySide6 version.")

    # Show the window
    window.show()

    actions.auto_load_last_directory()

    enable_dark_mode(app)

    # Set up proper shutdown
    app.aboutToQuit.connect(shutdown_async_logging)
    
    # Add this near the end of your main application setup
    app = QApplication.instance()
    app.aboutToQuit.connect(lambda: data.worker_queue.shutdown())

    # Start the event loop
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
