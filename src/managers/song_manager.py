from typing import List
from PySide6.QtCore import QObject, Signal
from model.song import Song
from model.song_list import SongList

class SongManager(QObject):
    selected_songs_changed = Signal(list)
    selected_song_changed = Signal(Song)

    def __init__(self, songs: SongList):
        super().__init__()
        self.songs = songs
        self._selected_songs = []

    def get_selected_songs(self) -> List[Song]:
        """Returns the currently selected songs"""
        return self._selected_songs

    def select_songs(self, songs: List[Song]):
        """Select multiple songs and emit appropriate signals"""
        if self._selected_songs != songs:
            old_first = self._selected_songs[0] if self._selected_songs else None
            new_first = songs[0] if songs else None
            self._selected_songs = songs
            self.selected_songs_changed.emit(self._selected_songs)
            if old_first != new_first:
                self.selected_song_changed.emit(new_first)
    
    def select_song(self, song: Song):
        """Select a single song and emit appropriate signals"""
        if not song:
            self.select_songs([])
        else:
            self.select_songs([song])

    # Delegation methods to the Songs model
    def add_song(self, song: Song):
        """Add a song to the collection"""
        self.songs.add(song)
    
    def remove_song(self, song: Song):
        """Remove a song from the collection"""
        self.songs.remove(song)
    
    def clear_songs(self):
        """Clear all songs from the collection"""
        self.songs.clear()
        # Also clear selection when songs are cleared
        self.select_songs([])