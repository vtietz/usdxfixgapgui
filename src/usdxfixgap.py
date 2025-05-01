from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout
from PySide6.QtCore import __version__  # Updated import
import sys
from common.actions import Actions
from common.data import AppData, Config
from utils.enable_darkmode import enable_dark_mode
from utils.check_dependencies import check_dependencies
from views.menu_bar import MenuBar
from common.database import initialize_song_cache  # Add this import

from views.song_status import SongsStatusVisualizer
from views.media_player import MediaPlayerComponent, MediaPlayerEventFilter
from views.songlist.songlist_widget import SongListWidget
from views.task_queue_viewer import TaskQueueViewer

import logging
import logging.handlers # Import handlers

from PySide6.QtMultimedia import QMediaDevices
from PySide6.QtGui import QIcon

import os

logger = logging.getLogger(__name__)

# --- Logging Setup ---
def get_app_dir():
    """Get the directory of the executable or script."""
    if hasattr(sys, '_MEIPASS'):
        # Running in a PyInstaller bundle
        return os.path.dirname(sys.executable)
    # Running as a script
    return os.path.dirname(os.path.abspath(__file__))

log_file_path = os.path.join(get_app_dir(), 'usdxfixgap.log')

# Configure root logger
log_formatter = logging.Formatter('%(asctime)s %(name)s %(levelname)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
log_handler = logging.handlers.RotatingFileHandler(log_file_path, maxBytes=10*1024*1024, backupCount=3, encoding='utf-8') # Rotate logs (e.g., 10MB * 3 backups)
log_handler.setFormatter(log_formatter)

root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)
root_logger.addHandler(log_handler)

# Remove basicConfig if it was called elsewhere or rely on the root logger configuration
# logging.basicConfig(...) # REMOVE THIS LINE if present

# --- End Logging Setup ---

# Initialize database before creating AppData
db_path = initialize_song_cache()
logger.info(f"Song cache database initialized at: {db_path}")

data = AppData()
actions = Actions(data)

app = QApplication(sys.argv)

def resource_path(relative_path):
    """Get the absolute path to a resource, works for dev and PyInstaller."""
    if hasattr(sys, '_MEIPASS'):
        # Running in a PyInstaller bundle
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

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
songListView = SongListWidget(data.songs, actions)
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

# Start the event loop
sys.exit(app.exec())
