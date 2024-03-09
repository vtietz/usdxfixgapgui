# button_bar.py
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton
from PyQt6.QtCore import pyqtSignal
from actions import Actions

from data import AppData
#from workers.extract_vocals import ExtractVocalsWorker

class MenuBar(QWidget):
    
    loadSongsClicked = pyqtSignal()
    extractVocalsClicked = pyqtSignal()
    detectClicked = pyqtSignal()
    deleteClicked = pyqtSignal()

    actions: Actions = None

    def __init__(self, actions:Actions, parent=None):
      
        super().__init__(parent)
        self.layout = QHBoxLayout(self)
        self.actions = actions

        # Load Songs Button
        self.loadSongsButton = QPushButton("Load Songs")
        self.loadSongsButton.clicked.connect(self.loadSongsClicked.emit)
        actions.data.isLoadingSongsChanged.connect(self.updateLoadButtonState)
        self.layout.addWidget(self.loadSongsButton)

        self.extractButton = QPushButton("Extract Vocals", self)
        self.extractButton.clicked.connect(self.extractVocalsClicked.emit)
        self.layout.addWidget(self.extractButton)

        # Detect Button
        self.detectButton = QPushButton("Detect")
        self.detectButton.clicked.connect(self.detectClicked.emit)
        self.layout.addWidget(self.detectButton)

        # Delete Button
        self.deleteButton = QPushButton("Delete")
        self.deleteButton.clicked.connect(self.deleteClicked.emit)
        self.layout.addWidget(self.deleteButton)

        #self.loadSongsButton.clicked.connect(self.toggleLoadSongs)

    def updateLoadButtonState(self, isLoading: bool):
        if isLoading:
            self.loadSongsButton.setText("Cancel")
        else:
            self.loadSongsButton.setText("Load Songs")
            self.loadSongsButton.setEnabled(True) 

    def onExtractionFinished(self, result):
        print(f"Extraction finished: {result}")
        # Update UI or notify user as needed

    def onExtractionError(self, error_info):
        print(f"Extraction error: {error_info[0]}")
        # Handle errors, update UI, or notify user as needed