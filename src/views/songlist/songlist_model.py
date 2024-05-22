from typing import List
from PyQt6.QtCore import QAbstractTableModel, Qt, QModelIndex, QTimer

from model.song import Song, SongStatus
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

        # timer for adding pending songs
        self.timer = QTimer()
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.add_pending_songs)

    def song_added(self, song: Song):
        self.pending_songs.append(song)
        logger.info(f"Pending addition of song: {song}")
        if not self.timer.isActive():
            self.timer.start()

    def add_pending_songs(self):
        if self.pending_songs:
            self.beginInsertRows(QModelIndex(), len(self.songs), len(self.songs) + len(self.pending_songs) - 1)
            self.songs.extend(self.pending_songs)
            self.pending_songs.clear()
            self.endInsertRows()
        if not self.pending_songs:
            self.timer.stop()

    # Slot for handling song updates
    def song_updated(self, song: Song):
        for idx, s in enumerate(self.songs):
            if s.path == song.path:  # Assuming 'path' is a unique identifier
                row_index = idx
                self.dataChanged.emit(self.createIndex(row_index, 0), self.createIndex(row_index, self.columnCount() - 1))
                logger.info(f"Updated song: {song}")
                return
        logger.error(f"Song not found: {song}")

    # Slot for handling song deletion
    def song_deleted(self, song: Song):
        try:
            row_index = self.songs.index(song)
            self.beginRemoveRows(QModelIndex(), row_index, row_index)
            self.songs.pop(row_index)
            self.endRemoveRows()
            logger.info(f"Deleted song: {song}")
        except ValueError:
            logger.error(f"Attempted to delete a song not in the list: {song}")

    # Slot for handling clearing songs
    def songs_cleared(self):
        self.beginResetModel()
        self.songs.clear()
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return len(self.songs)

    def columnCount(self, parent=QModelIndex()):
        return 11

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self.songs)):
            return None
        song: Song = self.songs[index.row()]
        column = index.column()
        if role == Qt.ItemDataRole.UserRole:
            return song
        elif role == Qt.ItemDataRole.DisplayRole:
            relative_path = song.relative_path
            artist = song.artist
            title = song.title
            duration_str = song.duration_str
            bpm = str(song.bpm)
            gap = str(song.gap)
            status_name = song.status.name
            status = song.status
            if(status == SongStatus.ERROR):
                status_name = f"ERROR: {song.error_message}"
            if(song.gap_info):
                detected_gap = str(song.gap_info.detected_gap)
                diff = str(song.gap_info.diff)
                notes_overlap = str(song.gap_info.notes_overlap)
                processed_time = song.gap_info.processed_time
            else:
                detected_gap = ""
                diff = ""
                notes_overlap = ""
                processed_time = ""
            return [
                relative_path,
                artist,
                title,
                duration_str,
                bpm,
                gap,
                detected_gap,
                diff,
                notes_overlap,
                processed_time,
                status_name,
            ][column]
        elif role == Qt.ItemDataRole.TextAlignmentRole:
          if 3 <= column <= 8: 
              return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
          else:
              return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        elif role == Qt.ItemDataRole.BackgroundRole:
            if song.status == SongStatus.ERROR:
                return Qt.GlobalColor.red

        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return ["Path", "Artist", "Title", "Length", "BPM", "Gap", "Detected Gap", "Diff", "Notes", "Time", "Status"][section]
        return None

    def sort(self, column, order):
        self.layoutAboutToBeChanged.emit()
        self.songs.sort(key=lambda song: self.data(self.createIndex(self.songs.index(song), column), Qt.ItemDataRole.DisplayRole))
        if order == Qt.SortOrder.DescendingOrder:
            self.songs.reverse()
        self.layoutChanged.emit()
