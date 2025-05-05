from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import QSortFilterProxyModel
from common.actions import Actions
from common.data import AppData
from model.song import Song
from model.songs import Songs
from views.songlist.songlist_view import SongListView
from views.songlist.songlist_model import SongTableModel

class CustomSortFilterProxyModel(QSortFilterProxyModel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.selectedStatuses = []
        self.textFilter = ""

    def filterAcceptsRow(self, source_row, source_parent):
        # Access the source model's data for the given row
        song: Song = self.sourceModel().songs[source_row]

        # Implement filtering logic
        statusMatch = song.status.name in self.selectedStatuses if self.selectedStatuses else True
        textMatch = self.textFilter in song.artist.lower() or self.textFilter in song.title.lower()

        return statusMatch and textMatch

class SongListWidget(QWidget):
    def __init__(self, songs_model: Songs, actions: Actions, data: AppData,parent=None):
        super().__init__(parent)
        self.actions = actions

        # Create the table model and proxy model
        self.songs_model = songs_model
        self.tableModel = SongTableModel(songs_model, data)
        self.proxyModel = CustomSortFilterProxyModel()
        self.proxyModel.setSourceModel(self.tableModel)

        self.tableView = SongListView(self.proxyModel, actions)
        
        # Create song count label
        self.countLabel = QLabel()

        layout = QVBoxLayout()
        layout.addWidget(self.tableView)
        layout.addWidget(self.countLabel)
        self.setLayout(layout)

        # Connect signals to update the filter and status label
        self.songs_model.filterChanged.connect(self.updateFilter)
        
        # Connect model signals to update count when data changes
        self.tableModel.rowsInserted.connect(self.updateCountLabel)
        self.tableModel.rowsRemoved.connect(self.updateCountLabel)
        self.tableModel.modelReset.connect(self.updateCountLabel)
        self.proxyModel.rowsInserted.connect(self.updateCountLabel)
        self.proxyModel.rowsRemoved.connect(self.updateCountLabel)
        self.proxyModel.modelReset.connect(self.updateCountLabel)
        
        # Initial update of the count label
        self.updateCountLabel()

    def updateFilter(self):
        self.proxyModel.selectedStatuses = self.songs_model.filter
        self.proxyModel.textFilter = self.songs_model.filter_text.lower()
        self.proxyModel.invalidateFilter()
        self.updateCountLabel()
        
    def updateCountLabel(self):
        total_songs = len(self.songs_model.songs)
        shown_songs = self.proxyModel.rowCount()
        self.countLabel.setText(f"Showing {shown_songs} of {total_songs} songs")

