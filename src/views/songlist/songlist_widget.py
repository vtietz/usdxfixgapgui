from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import QSortFilterProxyModel
from common.actions import Actions
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
    def __init__(self, songs_model: Songs, actions: Actions, parent=None):
        super().__init__(parent)
        self.actions = actions

        # Create the table model and proxy model
        self.songs_model = songs_model
        self.tableModel = SongTableModel(songs_model)
        self.proxyModel = CustomSortFilterProxyModel()
        self.proxyModel.setSourceModel(self.tableModel)

        self.tableView = SongListView(self.proxyModel, actions)
        
        # Create status label
        self.statusLabel = QLabel()
        self.updateStatusLabel()

        layout = QVBoxLayout()
        layout.addWidget(self.tableView)
        layout.addWidget(self.statusLabel)
        self.setLayout(layout)

        # Connect signals to update the filter and status label
        self.songs_model.filterChanged.connect(self.updateFilter)
        self.songs_model.added.connect(lambda _: self.updateStatusLabel())
        self.songs_model.deleted.connect(lambda _: self.updateStatusLabel())
        self.songs_model.cleared.connect(self.updateStatusLabel)

    def updateFilter(self):
        self.proxyModel.selectedStatuses = self.songs_model.filter
        self.proxyModel.textFilter = self.songs_model.filter_text.lower()
        self.proxyModel.invalidateFilter()
        self.updateStatusLabel()
        
    def updateStatusLabel(self):
        total_songs = len(self.songs_model)
        visible_songs = self.proxyModel.rowCount()
        
        if visible_songs == total_songs:
            text = f"{total_songs} song{'s' if total_songs != 1 else ''}"
        else:
            text = f"{visible_songs} of {total_songs} song{'s' if total_songs != 1 else ''}"
            
        self.statusLabel.setText(text)

