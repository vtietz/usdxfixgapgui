from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem, QVBoxLayout, QPushButton, QHeaderView
from PyQt6.QtCore import pyqtSignal, Qt

from actions import Actions
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
        self.setColumnCount(9)
        self.setHorizontalHeaderLabels([
            "Path", 
            "Artist", 
            "Title",
            "Length",
            "BPM", 
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
        self.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeMode.Fixed)
        self.horizontalHeader().setSectionResizeMode(9, QHeaderView.ResizeMode.Fixed)
        self.setColumnWidth(3, 50)
        self.setColumnWidth(4, 65)
        self.setColumnWidth(5, 50)
        self.setColumnWidth(7, 50)
        self.setColumnWidth(8, 100)

        self.sortByColumn(0, Qt.SortOrder.AscendingOrder)

        self.actions.data.songs.filterChanged.connect(self.updateFilter)
        self.actions.data.songs.deleted.connect(self.deleteSong)

    def addSong(self, song: Song):
        logger.debug(f"Adding song {song.path}")
        self.setSortingEnabled(False)
        rowPosition = self.rowCount()
        self.insertRow(rowPosition)
        
        for i, value in enumerate([
            song.relative_path,
            song.artist,
            song.title,
            song.duration_str,
            str(song.bpm),
            str(song.gap),
            str(song.gap_info.detected_gap),
            str(song.gap_info.diff),
            song.status.name  # Assuming you want to display the name of the status
        ]):
            item = QTableWidgetItem(value)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)  # Disable editing
            if i >= 3 and i < 8:
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.setItem(rowPosition, i, item)
        
        # Store the entire Song object in the row's first column for easy retrieval
        self.item(rowPosition, 0).setData(Qt.ItemDataRole.UserRole, song)
        
        self.setSortingEnabled(True)
        self.updateFilter()
    
    def deleteSong(self, song: Song):
        for row in range(self.rowCount()):
            item = self.item(row, 0)
            if item.data(Qt.ItemDataRole.UserRole) == song:
                self.removeRow(row)
                break
        self.updateFilter()

    def updateSong(self, updated_song: Song):
        for row in range(self.rowCount()):
            item = self.item(row, 0)  # Assuming the Song object is stored in the first column
            song = item.data(Qt.ItemDataRole.UserRole)
            if song == updated_song:
                # Update the row with new song details
                self.item(row, 1).setText(updated_song.artist)
                self.item(row, 2).setText(updated_song.title)
                self.item(row, 3).setText(updated_song.duration_str)
                self.item(row, 4).setText(str(updated_song.bpm))
                self.item(row, 5).setText(str(updated_song.gap))
                self.item(row, 6).setText(str(updated_song.gap_info.detected_gap))
                self.item(row, 7).setText(str(updated_song.gap_info.diff))
                self.item(row, 8).setText(updated_song.status.value)
                # Update the stored Song object in case any other song attributes are used elsewhere
                item.setData(Qt.ItemDataRole.UserRole, updated_song)
                break  # Exit the loop once the song is found and updated
        self.updateFilter()

    def onSelectionChanged(self, selected, deselected):
        indexes = selected.indexes()
        if indexes:
            row = indexes[0].row()
            selectedSong: Song = self.item(row, 0).data(Qt.ItemDataRole.UserRole)
            if selectedSong:
                self.actions.select_song(selectedSong.path)

    def clearSongs(self):
        self.setRowCount(0)

    def errorSong(self, song, exception):
        self.updateSong(song)

    def updateFilter(self):
        selectedStatuses = self.actions.data.songs.filter  # This is now a list of selected statuses
        textFilter = self.actions.data.songs.filter_text.lower()  # Convert filter text to lowercase for case-insensitive comparison
        selectedRow = self.currentRow()
        rowVisibilityChanged = False  # Flag to track if any row's visibility changed

        # If selectedStatuses is empty, it implies no filtering by status, so all should be shown
        showAllStatuses = len(selectedStatuses) == 0

        # Iterate over all rows once to determine their visibility based on the filter criteria
        for row in range(self.rowCount()):
            songStatus = self.item(row, 8).text()  # Assuming column 8 is the song status
            artistName = self.item(row, 1).text().lower()  # Assuming column 1 is the artist name
            songTitle = self.item(row, 2).text().lower()  # Assuming column 2 is the song title

            # Check for status filter. If showAllStatuses is True, ignore status filtering
            statusMatch = showAllStatuses or songStatus in selectedStatuses

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
