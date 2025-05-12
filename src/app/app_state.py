import os
from PySide6.QtCore import QObject, Signal
from model.song import Song
from model.song_list import SongList
from managers.song_manager import SongManager

class AppState(QObject):
    """Manages application-wide state"""
    
    # Define signals
    selected_songs_changed = Signal(list)
    selected_song_changed = Signal(object)
    is_loading_songs_changed = Signal(bool)
    gap_detection_finished = Signal(Song)
    gap_updated = Signal(Song)
    gap_reverted = Signal(Song)
    selection_changed = Signal()
    
    def __init__(self, songs=None):
        super().__init__()
        self.songs = songs or SongList()
        self.song_manager = SongManager(self.songs)
        self._connect_signals()
    
    def _connect_signals(self):
        """Connect song manager signals to AppState signals"""
        self.song_manager.selected_songs_changed.connect(self.selected_songs_changed)
        self.song_manager.selected_song_changed.connect(self.selected_song_changed)
        self.song_manager.is_loading_songs_changed.connect(self.is_loading_songs_changed)
        self.song_manager.gap_detection_finished.connect(self.gap_detection_finished)
        self.song_manager.gap_updated.connect(self.gap_updated)
        self.song_manager.gap_reverted.connect(self.gap_reverted)
        self.song_manager.selection_changed.connect(self.selection_changed)
    
    @property
    def selected_songs(self):
        return self.song_manager.selected_songs
    
    @selected_songs.setter
    def selected_songs(self, value):
        self.song_manager.selected_songs = value
    
    @property
    def first_selected_song(self):
        return self.song_manager.first_selected_song
    
    @property
    def is_loading_songs(self):
        return self.song_manager.is_loading_songs
    
    @is_loading_songs.setter
    def is_loading_songs(self, value):
        self.song_manager.is_loading_songs = value
