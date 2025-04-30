# button_bar.py
from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QFileDialog, QSizePolicy, QLineEdit, QMessageBox
from PySide6.QtCore import Signal
from actions import Actions
from data import AppData
import logging

from data import Config
from model.song import Song, SongStatus
from views.multi_select_box import MultiSelectComboBox

logger = logging.getLogger(__name__)

class MenuBar(QWidget):
    
    loadSongsClicked = Signal()
    extractVocalsClicked = Signal()
    detectClicked = Signal()
    deleteClicked = Signal()

    _song: Song = None

    def __init__(self, actions:Actions, data:AppData, parent=None):
      
        super().__init__(parent)
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.actions = actions
        self.data = data
        self.config = data.config

        # Load Songs Button
        self.loadSongsButton = QPushButton("Load Songs")
        self.loadSongsButton.clicked.connect(self.choose_directory)
        self.layout.addWidget(self.loadSongsButton)

        # Detect Button
        self.detectButton = QPushButton("Detect Gap")
        #self.detectButton.clicked.connect(self.detectClicked.emit)
        self.detectButton.clicked.connect(lambda: actions.detect_gap(overwrite=True))
        self.layout.addWidget(self.detectButton)

        # Open song folder
        self.openFolderButton = QPushButton("Open Folder")
        self.openFolderButton.clicked.connect(lambda: actions.open_folder())
        self.layout.addWidget(self.openFolderButton)

        # Open usdx webseite
        self.open_usdx_button = QPushButton("Open in USDB")
        self.open_usdx_button.clicked.connect(lambda: actions.open_usdx())
        self.layout.addWidget(self.open_usdx_button)

        # Reload song
        self.reload_button = QPushButton("Reload Song")
        self.reload_button.clicked.connect(lambda: actions.reload_song())
        self.layout.addWidget(self.reload_button)

        # Normalize song
        self.normalize_button = QPushButton("Normalize Song")
        self.normalize_button.clicked.connect(lambda: actions.normalize_song())
        self.layout.addWidget(self.normalize_button)

        # Delete song
        self.delete_button = QPushButton("Delete Song")
        self.delete_button.clicked.connect(self.onDeleteButtonClicked)
        self.layout.addWidget(self.delete_button)

        self.searchBox = QLineEdit()
        self.searchBox.setPlaceholderText("Search")
        self.searchBox.setMinimumWidth(200) 
        self.searchBox.textChanged.connect(self.onSearchChanged)
        self.layout.addWidget(self.searchBox)

        # Convert SongStatus values to a list of strings
        status_values = [status.value for status in SongStatus]
        self.filterDropdown = MultiSelectComboBox(items=status_values)
        self.filterDropdown.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.filterDropdown.setMinimumWidth(200) 
        self.filterDropdown.setSelectedItems(self.actions.data.songs.filter)
        self.filterDropdown.selectionChanged.connect(self.onFilterChanged)
        self.layout.addWidget(self.filterDropdown)

        self.loadSongsClicked.connect(lambda: actions.choose_directory())
        self.extractVocalsClicked.connect(lambda: actions.extractVocals())

        self.actions.data.selected_song_changed.connect(self.onSelectedSongChanged)

        self.onSelectedSongChanged(None)

    def onDeleteButtonClicked(self):
        msgBox = QMessageBox()
        msgBox.setIcon(QMessageBox.Icon.Information)  # Adjusted for Qt6 compatibility
        msgBox.setText(f"Are you sure you want to delete the following directory?\r\n{self._song.path}?")
        msgBox.setWindowTitle("Delete Confirmation")
        msgBox.setStandardButtons(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
        
        returnValue = msgBox.exec()
        if returnValue == QMessageBox.StandardButton.Ok:  # Adjusted for clarity
            self.actions.delete_selected_song()

    def updateLoadButtonState(self, isLoading: bool):
        self.loadSongsButton.setEnabled(not isLoading) 

    def onSearchChanged(self, text):
        self.actions.data.songs.filter_text = text

    def onSelectedSongChanged(self, song: Song):
        self._song = song
        self.open_usdx_button.setEnabled(True if song and song.usdb_id else False)
        self.openFolderButton.setEnabled(True if song and song.path else False)
        self.detectButton.setEnabled(True if song and song.audio_file and self.config.spleeter else False)
        self.reload_button.setEnabled(True if song and song.path else False)
        self.delete_button.setEnabled(True if song and song.path else False)
        self.normalize_button.setEnabled(True if song and song.audio_file else False)

    def choose_directory(self):
        directory = QFileDialog.getExistingDirectory(
            self, 
            "Select Directory", 
            self.data.directory  # Pass the directory path as the third positional argument
        )
        if directory:  # Check if a directory was selected
            self.on_directory_selected(directory)

    def on_directory_selected(self, directory: str):
        self.actions.set_directory(directory)

    def onFilterChanged(self, selectedStatuses):
        self.actions.data.songs.filter=selectedStatuses