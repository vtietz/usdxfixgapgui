from PySide6.QtWidgets import QHeaderView, QTableView
from PySide6.QtCore import Signal, Qt
import os
import logging

from actions import Actions
from model.song import Song
from views.songlist.songlist_model import SongTableModel

logger = logging.getLogger(__name__)

class SongListView(QTableView):
    rowSelected = Signal(int)  # Emits the row index of the selected song
    selectedTxtFile = Signal(str)  # Emits the file path

    def __init__(self, model: SongTableModel, actions: Actions, parent=None):
        super().__init__(parent)
        self.setModel(model)
        self.tableModel = model
        self.actions = actions

        # Connect selection changed signal
        self.selectionModel().selectionChanged.connect(self.onSelectionChanged)

        self.setupUi()

    def setupUi(self):
        self.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.setSortingEnabled(True)
        self.horizontalHeader().setSortIndicatorShown(True)
        self.horizontalHeader().setSectionsClickable(True)

        # Adjust column widths and resize modes
        for i in range(12):
            resize_mode = QHeaderView.ResizeMode.Stretch if i < 3 else QHeaderView.ResizeMode.ResizeToContents
            self.horizontalHeader().setSectionResizeMode(i, resize_mode)

        self.setColumnWidth(9, 100)

        # Sorting by the first column initially
        self.sortByColumn(0, Qt.SortOrder.AscendingOrder)

    def onSelectionChanged(self, selected, deselected):
        indexes = selected.indexes()
        if indexes:
            source_index = self.model().mapToSource(indexes[0])
            source_model = self.model().sourceModel()
            song: Song = source_model.songs[source_index.row()]

            logger.debug(f"Selected song details - Title: {song.title}, Artist: {song.artist}")
            logger.debug(f"Song path: {song.path}, Exists: {os.path.exists(song.path)}")
            logger.debug(f"Audio file: {song.audio_file}, Exists: {os.path.exists(song.audio_file) if song.audio_file else False}")

            self.actions.select_song(song.path)

