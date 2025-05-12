from PySide6.QtWidgets import QHeaderView, QTableView
from PySide6.QtCore import Signal, Qt
import os
import logging

from common.actions import Actions
from model.song import Song
from views.songlist.songlist_model import SongTableModel

logger = logging.getLogger(__name__)

class SongListView(QTableView):
    selected_songs_changed = Signal(list) # Emits list of selected Song objects

    def __init__(self, model: SongTableModel, actions: Actions, parent=None):
        super().__init__(parent)
        self.setModel(model)
        self.tableModel = model
        self.actions = actions

        # Connect selection changed signal
        self.selectionModel().selectionChanged.connect(self.onSelectionChanged)
        # Connect the view's signal to the action handler
        self.selected_songs_changed.connect(actions.set_selected_songs)

        self.setupUi()

    def setupUi(self):
        self.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        # Allow selecting multiple rows
        self.setSelectionMode(QTableView.SelectionMode.ExtendedSelection)
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
        selected_songs = []
        source_model = self.model().sourceModel()
        # Use selectedRows() to get all selected rows
        for index in self.selectionModel().selectedRows():
            source_index = self.model().mapToSource(index)
            if source_index.isValid() and source_index.row() < len(source_model.songs):
                song: Song = source_model.songs[source_index.row()]
                selected_songs.append(song)
            else:
                logger.warning(f"Invalid source index obtained: {source_index.row()}")

        if selected_songs:
            first_song = selected_songs[0]
            logger.debug(f"Selected {len(selected_songs)} songs. First: {first_song.title} by {first_song.artist}")
        else:
            logger.debug("Selection cleared.")

        # Emit the list of selected songs
        self.selected_songs_changed.emit(selected_songs)

        # Keep single song selection action for compatibility if needed elsewhere,
        # but primary handling should use the list via selected_songs_changed.
        # If actions.select_song is only used for single selection logic (e.g., detail view),
        # it might need adjustment or removal depending on overall architecture.
        # For now, let's assume the main handling is via set_selected_songs in Actions.
        # if selected_songs:
        #     self.actions.select_song(selected_songs[0].path) # Or adapt select_song if needed

