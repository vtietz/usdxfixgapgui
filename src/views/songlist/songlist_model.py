from typing import List
from PyQt6.QtCore import QAbstractTableModel, Qt, QModelIndex

from model.song import Song
from model.songs import Songs
import logging

logger = logging.getLogger(__name__)

class SongTableModel(QAbstractTableModel):
    def __init__(self, songs_model: Songs, parent=None):
        super().__init__(parent)
        self.songs_model = songs_model

        self.songs: List[Song] = list(self.songs_model.songs)  # Creates a shallow copy

        self.pending_songs = [] 

        # Connect signals
        self.songs_model.added.connect(self.song_added)
        self.songs_model.updated.connect(self.song_updated)
        self.songs_model.deleted.connect(self.song_deleted)
        self.songs_model.cleared.connect(self.songs_cleared)

    def song_added(self, song: Song):
        logging.debug("Adding song to model: %s", song)
        self.beginInsertRows(QModelIndex(), len(self.songs), len(self.songs))
        self.songs.append(song)
        self.endInsertRows()

    # Slot for handling song updates
    def song_updated(self, song: Song):
        row_index = self.songs.index(song)
        self.dataChanged.emit(self.createIndex(row_index, 0), self.createIndex(row_index, self.columnCount() - 1))

    # Slot for handling song deletion
    def song_deleted(self, song: Song):
        row_index = self.songs.index(song)
        self.beginRemoveRows(QModelIndex(), row_index, row_index)
        self.endRemoveRows()

    # Slot for handling clearing songs
    def songs_cleared(self):
        self.beginResetModel()
        self.songs.clear()
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return len(self.songs)

    def columnCount(self, parent=QModelIndex()):
        return 9

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self.songs)):
            return None
        song: Song = self.songs[index.row()]
        column = index.column()
        if role == Qt.ItemDataRole.UserRole:
            return song
        elif role == Qt.ItemDataRole.DisplayRole:
            return [
                song.relative_path,
                song.artist,
                song.title,
                song.duration_str,
                str(song.bpm),
                str(song.gap),
                str(song.gap_info.detected_gap),
                str(song.gap_info.diff),
                song.status.name,
            ][column]
        elif role == Qt.ItemDataRole.TextAlignmentRole:
          if 3 <= column <= 7: 
              return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
          else:
              return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter

        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return ["Path", "Artist", "Title", "Length", "BPM", "Gap", "Detected Gap", "Diff", "Status"][section]
        return None