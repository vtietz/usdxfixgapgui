from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout
import sys
from actions import Actions
from data import AppData
from enable_darkmode import enable_dark_mode
from views.menu_bar import MenuBar

# Import your custom components
from views.songlist import SongListView
from views.media_player import MediaPlayerComponent
from views.task_queue_viewer import TaskQueueViewer

data = AppData()
actions = Actions(data)

app = QApplication(sys.argv)
# Create the main window and set its properties
window = QWidget()
window.setWindowTitle("Modular PyQt6 Application")
window.resize(800, 600)


menuBar = MenuBar(actions)
menuBar.loadSongsClicked.connect(lambda: actions.loadSongs())
menuBar.extractVocalsClicked.connect(lambda: actions.extractVocals())

songListView = SongListView(data.songs, actions)
mediaPlayerComponent = MediaPlayerComponent(data)
taskQueueViewer = TaskQueueViewer(data.workerQueue)

# Set up the layout and add your components
layout = QVBoxLayout()
layout.addWidget(menuBar)
layout.addWidget(songListView, 2)  # Adjust stretch factor as needed
layout.addWidget(mediaPlayerComponent, 1)  # Adjust stretch factor as needed
layout.addWidget(taskQueueViewer, 1)  # Adjust stretch factor as needed

window.setLayout(layout)

from PyQt6.QtCore import QT_VERSION_STR, qVersion

print("Compile-time Qt version:", QT_VERSION_STR)
print("Runtime Qt version:", qVersion())

# Show the window
window.show()

enable_dark_mode(app)

# Start the event loop
sys.exit(app.exec())
