# button_bar.py
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QFileDialog
from PyQt6.QtCore import pyqtSignal
from actions import Actions
import logging

from data import Config

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
        #self.loadSongsButton.clicked.connect(self.loadSongsClicked.emit)
        #actions.data.is_loading_songs_changed.connect(self.updateLoadButtonState)
        #actions.data.is_loading_songs_changed.connect(self.updateLoadButtonState)
        self.layout.addWidget(self.loadSongsButton)

        self.extractButton = QPushButton("Extract Vocals", self)
        self.extractButton.clicked.connect(self.extractVocalsClicked.emit)
        self.layout.addWidget(self.extractButton)

        # Detect Button
        self.detectButton = QPushButton("Detect Gap")
        self.detectButton.clicked.connect(self.detectClicked.emit)
        self.layout.addWidget(self.detectButton)

        # Delete Button
        self.deleteButton = QPushButton("Delete")
        self.deleteButton.clicked.connect(self.deleteClicked.emit)
        self.layout.addWidget(self.deleteButton)

        #self.loadSongsButton.clicked.connect(self.toggleLoadSongs)

    def updateLoadButtonState(self, isLoading: bool):
        self.loadSongsButton.setEnabled(not isLoading) 

    def onExtractionFinished(self, result):
        print(f"Extraction finished: {result}")
        # Update UI or notify user as needed

    def onExtractionError(self, error_info):
        print(f"Extraction error: {error_info[0]}")
        # Handle errors, update UI, or notify user as needed

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
