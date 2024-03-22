from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem, QVBoxLayout, QPushButton, QHeaderView
from PyQt6.QtCore import pyqtSignal, Qt

from actions import Actions
from model.info import SongStatus
from model.song import Song
from model.songs import Songs

import logging

logger = logging.getLogger(__name__)

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

        self.sortByColumn(0, Qt.SortOrder.AscendingOrder)

        self.actions.data.songs.filterChanged.connect(self.updateFilter)

    def addSong(self, song: Song):
        logger.debug(f"Adding song {song.path}")
        self.setSortingEnabled(False)
        rowPosition = self.rowCount()
        self.insertRow(rowPosition)
        
        for i, value in enumerate([
            song.relative_path,
            song.artist,
            song.title,
            str(song.gap),
            str(song.info.detected_gap),
            str(song.info.diff),
            song.info.status.name  # Assuming you want to display the name of the status
        ]):
            item = QTableWidgetItem(value)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)  # Disable editing
            if i >= 3 and i < 6:
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.setItem(rowPosition, i, item)
        
        # Store the entire Song object in the row's first column for easy retrieval
        self.item(rowPosition, 0).setData(Qt.ItemDataRole.UserRole, song)
        
        self.setSortingEnabled(True)
        self.updateFilter()

    def updateSong(self, updated_song: Song):
        for row in range(self.rowCount()):
            item = self.item(row, 0)  # Assuming the Song object is stored in the first column
            song = item.data(Qt.ItemDataRole.UserRole)
            if song == updated_song:
                # Update the row with new song details
                self.item(row, 1).setText(updated_song.artist)
                self.item(row, 2).setText(updated_song.title)
                self.item(row, 3).setText(str(updated_song.gap))
                self.item(row, 4).setText(str(updated_song.info.detected_gap))
                self.item(row, 5).setText(str(updated_song.info.diff))
                self.item(row, 6).setText(updated_song.info.status.value)
                # Update the stored Song object in case any other song attributes are used elsewhere
                item.setData(Qt.ItemDataRole.UserRole, updated_song)
                break  # Exit the loop once the song is found and updated
        self.updateFilter()

    def onSelectionChanged(self, selected, deselected):
        indexes = selected.indexes()
        if indexes:
            row = indexes[0].row()
            selectedSong = self.item(row, 0).data(Qt.ItemDataRole.UserRole)
            if selectedSong:
                self.actions.setSelectedSong(selectedSong.path)

    def clearSongs(self):
        self.setRowCount(0)

    def errorSong(self, song, exception):
        print(f"Error processing {song.path}: {exception}")
        self.updateSong(song)

    def updateFilter(self):
        status = self.actions.data.songs.filter
        textFilter = self.actions.data.songs.filter_text
        selectedRow = self.currentRow()
        rowVisibilityChanged = False  # Flag to track if any row's visibility changed
        textFilter = textFilter.lower()  # Convert filter text to lowercase for case-insensitive comparison

        # Iterate over all rows once to determine their visibility based on the filter criteria
        for row in range(self.rowCount()):
            songStatus = self.item(row, 6).text()
            artistName = self.item(row, 1).text().lower()  # Assuming column 1 is the artist name
            songTitle = self.item(row, 2).text().lower()  # Assuming column 2 is the song title

            # Check for status filter
            statusMatch = status == SongStatus.ALL or status.value == songStatus

            # Check for text filter match in either artist name or song title
            textMatch = textFilter in artistName or textFilter in songTitle

            shouldBeVisible = statusMatch and textMatch
            isCurrentlyVisible = not self.isRowHidden(row)
            
            # Update visibility only if there's a change to minimize costly operations
            if shouldBeVisible != isCurrentlyVisible:
                self.setRowHidden(row, not shouldBeVisible)
                rowVisibilityChanged = True

        # If no rows changed visibility, no need to adjust the selection
        if not rowVisibilityChanged:
            return

        # Adjust selection if the previously selected row is now hidden
        if self.isRowHidden(selectedRow):
            # Try to select a nearby visible row. First look upwards, then downwards
            for direction in (-1, 1):
                newRow = selectedRow
                while 0 <= newRow < self.rowCount():
                    if not self.isRowHidden(newRow):
                        self.selectRow(newRow)
                        return
                    newRow += direction
