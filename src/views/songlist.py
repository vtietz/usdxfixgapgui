from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem, QVBoxLayout, QPushButton
from PyQt6.QtCore import pyqtSignal, Qt

from actions import Actions
from model.songs import Songs

class SongListView(QTableWidget):
    
    actions: Actions
    songs: Songs

    rowSelected = pyqtSignal(int)  # Emits the row index of the selected song
    selectedTxtFile = pyqtSignal(str)  # Assuming you want to emit the file path; adjust as needed

    def __init__(self, songs:Songs, actions:Actions, parent=None):
        super().__init__(parent)
        self.actions = actions
        self.songs = songs
        songs.added.connect(self.addSongToList)
        songs.cleared.connect(self.clearSongs)
        self.setupUi()

    def setupUi(self):
        self.setColumnCount(7)
        self.setHorizontalHeaderLabels(["Path", "Artist", "Title", "Gap", "Detected Gap", "Diff", "Status"])
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.setSortingEnabled(True)
        self.horizontalHeader().setSortIndicatorShown(True)
        self.horizontalHeader().setSectionsClickable(True)
        self.selectionModel().selectionChanged.connect(self.onSelectionChanged)

    def addSongToList(self, song):
        rowPosition = self.rowCount()
        self.insertRow(rowPosition)
        items = [
            QTableWidgetItem(song.path),
            QTableWidgetItem(song.artist),
            QTableWidgetItem(song.title),
            QTableWidgetItem(str(song.gap)),
            QTableWidgetItem(str(song.detected_gap)),
            QTableWidgetItem(str(song.diff)),
            QTableWidgetItem(str(song.status))
        ]

        for i, item in enumerate(items):
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)  # Disable editing
            self.setItem(rowPosition, i, item)

    def onSelectionChanged(self, selected, deselected):
        indexes = selected.indexes()
        if indexes:
            row = indexes[0].row()
            self.actions.setSelectedSong(self.songs[row].path)

    def clearSongs(self):
        self.setRowCount(0)
