
from typing import List
from PyQt6.QtCore import QObject, pyqtSignal
from model.info import SongStatus
from model.song import Song

class Songs(QObject):
    
    cleared = pyqtSignal()
    added = pyqtSignal(Song)
    updated = pyqtSignal(Song)
    error = pyqtSignal(Song, Exception)
    filterChanged = pyqtSignal(SongStatus)

    _filter: SongStatus = SongStatus.ALL
    
    songs: List[Song] = []

    def clear(self):
        self.songs.clear()
        self.cleared.emit()

    def add(self, song: Song):
        self.songs.append(song)
        self.added.emit(song)

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
        self.filterChanged.emit(value)