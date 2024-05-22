from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView, QTableView
from PyQt6.QtCore import pyqtSignal, Qt, QTimer

from actions import Actions
from model.song import Song
from model.songs import Songs

import logging

from views.songlist.songlist_model import SongTableModel

logger = logging.getLogger(__name__)

class SongListView(QTableView):
    
    actions: Actions
    songs: Songs

    rowSelected = pyqtSignal(int)  # Emits the row index of the selected song
    selectedTxtFile = pyqtSignal(str)  # Assuming you want to emit the file path; adjust as needed

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
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(8, QHeaderView.ResizeMode.ResizeToContents)  
        self.horizontalHeader().setSectionResizeMode(9, QHeaderView.ResizeMode.ResizeToContents)  
        self.horizontalHeader().setSectionResizeMode(10, QHeaderView.ResizeMode.ResizeToContents) 
        self.setColumnWidth(9, 100) 

        # Sorting by the first column initially, if needed
        self.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        
    def onSelectionChanged(self, selected, deselected):
        # Assuming single selection mode for simplicity
        indexes = selected.indexes()
        if indexes:
            # Map the selected index from the proxy model back to the source model
            source_index = self.model().mapToSource(indexes[0])
            
            # Now, source_index refers to the corresponding index in the source model
            # You can use source_index to access data in the source model
            source_model = self.model().sourceModel()
            song: Song = source_model.songs[source_index.row()]
            
            self.actions.select_song(song.path)

            logger.debug(f"Selected song: {song.title} by {song.artist}")

