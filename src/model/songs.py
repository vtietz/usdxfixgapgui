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

    _filter: List[SongStatus] = []
    _filter_text: str = ""

    songs: List[Song] = []

    def clear(self):
        self.songs.clear()
        self.cleared.emit()

    def add(self, song: Song):
        self.songs.append(song)
        self.added.emit(song)

    def remove(self, song: Song):
        self.songs.remove(song)
        self.updated.emit(song)

    def clear(self):
        self.songs.clear()
        self.cleared.emit()

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