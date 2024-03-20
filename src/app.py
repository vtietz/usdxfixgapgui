from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout
from PyQt6.QtCore import QObject, QEvent, Qt
from PyQt6.QtCore import QT_VERSION_STR, qVersion
import sys
from actions import Actions
from data import AppData, Config
from enable_darkmode import enable_dark_mode
from utils.check_dependencies import check_dependencies
from views.menu_bar import MenuBar

from views.songlist import SongListView
from views.media_player import MediaPlayerComponent, MediaPlayerEventFilter
from views.task_queue_viewer import TaskQueueViewer

import logging

logger = logging.getLogger(__name__)

data = AppData()
config = Config()
actions = Actions(data, config)

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(name)s %(levelname)s: %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')


app = QApplication(sys.argv)

# Create the main window and set its properties
window = QWidget()
window.setWindowTitle("Modular PyQt6 Application")
window.resize(800, 600)


menuBar = MenuBar(actions, config)
songListView = SongListView(data.songs, actions)
mediaPlayerComponent = MediaPlayerComponent(data, config, actions)
taskQueueViewer = TaskQueueViewer(actions.worker_queue)

app.installEventFilter(mediaPlayerComponent.globalEventFilter)

# Set up the layout and add your components
layout = QVBoxLayout()
layout.addWidget(menuBar)
layout.addWidget(songListView, 2)  # Adjust stretch factor as needed
layout.addWidget(mediaPlayerComponent, 1)  # Adjust stretch factor as needed
layout.addWidget(taskQueueViewer, 1)  # Adjust stretch factor as needed

window.setLayout(layout)

logger.debug("Runtime Qt version: %s", qVersion())
logger.debug(f"Compile-time Qt version: {QT_VERSION_STR}")

# Example usage
dependencies = [
    ('spleeter', '--version'),
    ('ffmpeg', '-version'),  # Note that ffmpeg uses '-version' instead of '--version'
    ('ffmpeg-normalize', '--version')
]
if(not check_dependencies(dependencies)):
    logger.error("Some dependencies are not installed. Please install it and try again.")
    sys.exit(1)

# Show the window
window.show()

enable_dark_mode(app)

# Start the event loop
sys.exit(app.exec())
