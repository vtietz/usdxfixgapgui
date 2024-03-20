# button_bar.py
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QFileDialog, QComboBox
from PyQt6.QtCore import pyqtSignal
from actions import Actions
import logging

from data import Config
from model.info import Info, SongStatus
from model.song import Song

logger = logging.getLogger(__name__)

class MenuBar(QWidget):
    
    loadSongsClicked = pyqtSignal()
    extractVocalsClicked = pyqtSignal()
    detectClicked = pyqtSignal()
    deleteClicked = pyqtSignal()

    actions: Actions = None

    def __init__(self, actions:Actions, config: Config, parent=None):
      
        super().__init__(parent)
        self.layout = QHBoxLayout(self)
        self.actions = actions

        # Load Songs Button
        self.loadSongsButton = QPushButton("Load Songs")
        self.loadSongsButton.clicked.connect(self.choose_directory)
        self.layout.addWidget(self.loadSongsButton)

        self.extractButton = QPushButton("Extract Vocals", self)
        self.extractButton.clicked.connect(self.extractVocalsClicked.emit)
        self.layout.addWidget(self.extractButton)

        # Detect Button
        self.detectButton = QPushButton("Detect Gap")
        self.detectButton.clicked.connect(self.detectClicked.emit)
        self.layout.addWidget(self.detectButton)

        # Open song folder
        self.openFolderButton = QPushButton("Open Folder")
        self.openFolderButton.clicked.connect(lambda: actions.open_folder())
        self.layout.addWidget(self.openFolderButton)

        # Open usdx webseite
        self.open_usdx_button = QPushButton("Open in USDB")
        self.open_usdx_button.clicked.connect(lambda: actions.open_usdx())
        self.layout.addWidget(self.open_usdx_button)

        # Delete Button
        #self.deleteButton = QPushButton("Delete")
        #self.deleteButton.clicked.connect(self.deleteClicked.emit)
        #self.layout.addWidget(self.deleteButton)

        # Filter dropdown regarding the status of the songs
        self.filterDropdown = QComboBox()
        for status in SongStatus:
            self.filterDropdown.addItem(status.value)
        self.filterDropdown.currentIndexChanged.connect(self.onFilterChanged)
        self.layout.addWidget(self.filterDropdown)

        #self.loadSongsButton.clicked.connect(self.toggleLoadSongs)

        #self.loadSongsClicked.connect(lambda: actions.loadSongs())
        self.loadSongsClicked.connect(lambda: actions.choose_directory())
        self.extractVocalsClicked.connect(lambda: actions.extractVocals())
        self.detectClicked.connect(lambda: actions.detect_gap(start_now=True))

        self.actions.data.selected_song_changed.connect(self.onSelectedSongChanged)

        self.onSelectedSongChanged(None)

    def updateLoadButtonState(self, isLoading: bool):
        self.loadSongsButton.setEnabled(not isLoading) 

    def onExtractionFinished(self, result):
        print(f"Extraction finished: {result}")
        # Update UI or notify user as needed

    def onExtractionError(self, error_info):
        print(f"Extraction error: {error_info[0]}")
        # Handle errors, update UI, or notify user as needed

    def onSelectedSongChanged(self, song: Song):
        self.open_usdx_button.setEnabled(True if song and song.usdb_id else False)
        self.openFolderButton.setEnabled(True if song and song.path else False)
        self.detectButton.setEnabled(True if song and song.audio_file else False)
        self.extractButton.setEnabled(True if song and song.audio_file else False)

    def choose_directory(self):
        directory = QFileDialog.getExistingDirectory(
            self, 
            "Select Directory", 
            directory=self.actions.config.directory
        )
        if directory:  # Check if a directory was selected
            self.on_directory_selected(directory)

    def on_directory_selected(self, directory: str):
        self.actions.loadSongs(directory)

    def onFilterChanged(self, index):
        status_text = self.filterDropdown.currentText()
        status = Info.map_string_to_status(status_text)
        self.actions.data.songs.filter=status
        #self.actions.data.songs.filterChanged.emit(status)