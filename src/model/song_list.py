from typing import List
from model.song import Song, SongStatus

class SongList:
    _filter: List[SongStatus] = []
    _filter_text: str = ""

    songs: List[Song] = []

    def clear(self):
        self.songs.clear()

    def add(self, song: Song):
        self.songs.append(song)

    def remove(self, song: Song):
        self.songs.remove(song)

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

    @property
    def filter_text(self):
        return self._filter_text
    
    @filter_text.setter
    def filter_text(self, value):
        self._filter_text = value