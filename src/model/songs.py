
from typing import List
from PyQt6.QtCore import QObject, pyqtSignal
from model.song import Song

class Songs(QObject):
    
    cleared = pyqtSignal()
    added = pyqtSignal(Song)
    updated = pyqtSignal(Song)
    error = pyqtSignal(Song, Exception)
    
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