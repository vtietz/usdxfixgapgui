from typing import List
from PySide6.QtCore import QAbstractTableModel, Qt, QModelIndex, QTimer
import logging

from app.app_data import AppData
from model.song import Song, SongStatus
from model.song_list import SongList
from utils import files

logger = logging.getLogger(__name__)

class SongTableModel(QAbstractTableModel):
    def __init__(self, songs_model: SongList, data: AppData, parent=None):
        super().__init__(parent)
        self.app_data = data
        self.songs_model = songs_model
        self.songs: List[Song] = list(self.songs_model.songs)
        self.pending_songs = []

        # Connect signals
        self.songs_model.added.connect(self.song_added)
        self.songs_model.updated.connect(self.song_updated)
        self.songs_model.deleted.connect(self.song_deleted)
        self.songs_model.cleared.connect(self.songs_cleared)

        # Timer for adding pending songs
        self.timer = QTimer()
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.add_pending_songs)

    def song_added(self, song: Song):
        self.pending_songs.append(song)
        logger.info(f"Added to songlist model: {song}")
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

    def song_updated(self, song: Song):
        for idx, s in enumerate(self.songs):
            if s.path == song.path:
                self.dataChanged.emit(self.createIndex(idx, 0), self.createIndex(idx, self.columnCount() - 1))
                logger.info(f"Updated song: {song}")
                return
        logger.error(f"Song not found: {song}")

    def song_deleted(self, song: Song):
        try:
            row_index = self.songs.index(song)
            self.beginRemoveRows(QModelIndex(), row_index, row_index)
            self.songs.pop(row_index)
            self.endRemoveRows()
            logger.info(f"Deleted song: {song}")
        except ValueError:
            logger.error(f"Attempted to delete a song not in the list: {song}")

    def songs_cleared(self):
        self.beginResetModel()
        self.songs.clear()
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return len(self.songs)

    def columnCount(self, parent=QModelIndex()):
        return 12

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self.songs)):
            return None
        song: Song = self.songs[index.row()]
        column = index.column()
        if role == Qt.ItemDataRole.UserRole:
            return song
        elif role == Qt.ItemDataRole.DisplayRole:
            return [
                files.get_relative_path(self.app_data.directory, song.path),
                song.artist,
                song.title,
                song.duration_str,
                str(song.bpm),
                str(song.gap),
                str(song.gap_info.detected_gap) if song.gap_info else "",
                str(song.gap_info.diff) if song.gap_info else "",
                str(song.gap_info.notes_overlap) if song.gap_info else "",
                song.gap_info.processed_time if song.gap_info else "",
                song.normalized_str,
                f"ERROR: {song.error_message}" if song.status == SongStatus.ERROR else song.status.name,
            ][column]
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter if 3 <= column <= 8 or column == 10 else Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        elif role == Qt.ItemDataRole.BackgroundRole and song.status == SongStatus.ERROR:
            return Qt.GlobalColor.red
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return ["Path", "Artist", "Title", "Length", "BPM", "Gap", "Detected Gap", "Diff", "Notes", "Time", "Normalized", "Status"][section]
        return None

    def sort(self, column, order):
        self.layoutAboutToBeChanged.emit()
        self.songs.sort(key=lambda song: self.data(self.createIndex(self.songs.index(song), column), Qt.ItemDataRole.DisplayRole))
        if order == Qt.SortOrder.DescendingOrder:
            self.songs.reverse()
        self.layoutChanged.emit()
