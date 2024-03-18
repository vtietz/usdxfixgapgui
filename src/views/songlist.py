from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem, QVBoxLayout, QPushButton, QHeaderView
from PyQt6.QtCore import pyqtSignal, Qt

from actions import Actions
from model.song import Song
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
        songs.added.connect(self.addSong)
        songs.updated.connect(self.updateSong)
        songs.error.connect(self.errorSong)
        songs.cleared.connect(self.clearSongs)
        self.setupUi()

    def setupUi(self):
        self.setColumnCount(7)
        self.setHorizontalHeaderLabels([
            "Path", 
            "Artist", 
            "Title", 
            "Gap", 
            "Detected Gap", 
            "Diff", 
            "Status"]
        )
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.setSortingEnabled(True)
        self.horizontalHeader().setSortIndicatorShown(True)
        self.horizontalHeader().setSectionsClickable(True)

        self.selectionModel().selectionChanged.connect(self.onSelectionChanged)

        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        self.setColumnWidth(3, 100)
        self.setColumnWidth(4, 100)
        self.setColumnWidth(5, 100)
        self.setColumnWidth(6, 100)

    def addSong(self, song: Song):
        rowPosition = self.rowCount()
        self.insertRow(rowPosition)
        items = [
            QTableWidgetItem(song.path),
            QTableWidgetItem(song.artist),
            QTableWidgetItem(song.title),
            QTableWidgetItem(str(song.gap)),
            QTableWidgetItem(str(song.info.detected_gap)),
            QTableWidgetItem(str(song.info.diff)),
            QTableWidgetItem(str(song.info.status.value))
        ]

        for i, item in enumerate(items):
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)  # Disable editing
            self.setItem(rowPosition, i, item)
            if(i >= 3 and i < 6):
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

    def updateSong(self, updated_song: Song):
        # Find the row of the song to update
        row_to_update = None
        for row in range(self.rowCount()):
            if self.item(row, 0).text() == updated_song.path:  # Assuming the path is in the first column
                row_to_update = row
                break

        if row_to_update is not None:
            # Update the row with new song details
            self.item(row_to_update, 1).setText(updated_song.artist)
            self.item(row_to_update, 2).setText(updated_song.title)
            self.item(row_to_update, 3).setText(str(updated_song.gap))
            self.item(row_to_update, 4).setText(str(updated_song.info.detected_gap))
            self.item(row_to_update, 5).setText(str(updated_song.info.diff))
            self.item(row_to_update, 6).setText(updated_song.info.status.value)


    def onSelectionChanged(self, selected, deselected):
        indexes = selected.indexes()
        if indexes:
            row = indexes[0].row()
            self.actions.setSelectedSong(self.songs[row].path)

    def clearSongs(self):
        self.setRowCount(0)

    def errorSong(self, song, exception):
        print(f"Error processing {song.path}: {exception}")
        self.updateSong(song)
