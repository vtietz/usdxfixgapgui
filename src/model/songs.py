from typing import List
from PySide6.QtCore import QObject, Signal  # Updated import
from model.song import Song, SongStatus


class Songs(QObject):

    cleared = Signal()  # Updated
    added = Signal(Song)  # Updated
    updated = Signal(Song)  # Updated
    deleted = Signal(Song)  # Updated
    error = Signal(Song, Exception)  # Updated
    filterChanged = Signal()  # Updated
    listChanged = Signal()  # Signal for when the list structure changes

    _filter: List[SongStatus] = []
    _filter_text: str = ""

    songs: List[Song] = []

    def clear(self):
        self.songs.clear()
        self.cleared.emit()
        self.listChanged.emit()  # Emit list changed signal

    def add(self, song: Song):
        self.songs.append(song)
        self.added.emit(song)
        self.listChanged.emit()  # Emit list changed signal

    def add_batch(self, songs: List[Song]):
        """Add multiple songs at once - more efficient than adding one by one."""
        if not songs:
            return

        self.songs.extend(songs)
        # Emit added signal for each song for compatibility
        for song in songs:
            self.added.emit(song)
        # Only emit list changed once at the end
        self.listChanged.emit()

    def remove(self, song: Song):
        self.songs.remove(song)
        self.deleted.emit(song)  # Changed from updated to deleted signal
        self.listChanged.emit()  # Emit list changed signal

    def list_changed(self):
        """Manually trigger list changed signal"""
        self.listChanged.emit()

    def __len__(self):
        return len(self.songs)

    def __getitem__(self, index):
        return self.songs[index]

    @property
    def filter(self):
        return self._filter

    @filter.setter
    def filter(self, value):
        self._filter = value
        self.filterChanged.emit()

    @property
    def filter_text(self):
        return self._filter_text

    @filter_text.setter
    def filter_text(self, value):
        self._filter_text = value
        self.filterChanged.emit()
