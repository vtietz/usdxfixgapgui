from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout
from PySide6.QtCore import __version__  # Updated import
import sys
from common.actions import Actions
from common.data import AppData, Config
from utils.enable_darkmode import enable_dark_mode
from utils.check_dependencies import check_dependencies
from views.menu_bar import MenuBar

from views.song_status import SongsStatusVisualizer
from views.media_player import MediaPlayerComponent, MediaPlayerEventFilter
from views.songlist.songlist_widget import SongListWidget
from views.task_queue_viewer import TaskQueueViewer

import logging

from PySide6.QtMultimedia import QMediaDevices
from PySide6.QtGui import QIcon

import os

logger = logging.getLogger(__name__)

data = AppData()
actions = Actions(data)

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(name)s %(levelname)s: %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')

app = QApplication(sys.argv)

def resource_path(relative_path):
    """Get the absolute path to a resource, works for dev and PyInstaller."""
    if hasattr(sys, '_MEIPASS'):
        # Running in a PyInstaller bundle
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

# Example usage
icon_path = resource_path("assets/usdxfixgap-icon.ico")
app.setWindowIcon(QIcon(icon_path))

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

enable_dark_mode(app)

# Start the event loop
sys.exit(app.exec())
