from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout
from PyQt6.QtCore import QT_VERSION_STR, qVersion
import sys
from actions import Actions
from data import AppData, Config
from enable_darkmode import enable_dark_mode
from utils.check_dependencies import check_dependencies
from views.menu_bar import MenuBar

from views.song_status import SongsStatusVisualizer
from views.media_player import MediaPlayerComponent, MediaPlayerEventFilter
from views.songlist.songlist_widget import SongListWidget
from views.task_queue_viewer import TaskQueueViewer

import logging

logger = logging.getLogger(__name__)

data = AppData()
actions = Actions(data)

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(name)s %(levelname)s: %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')


app = QApplication(sys.argv)

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

logger.debug("Runtime Qt version: %s", qVersion())
logger.debug(f"Compile-time Qt version: {QT_VERSION_STR}")
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

# Show the window
window.show()

enable_dark_mode(app)

# Start the event loop
sys.exit(app.exec())
