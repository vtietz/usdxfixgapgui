import os
from PySide6.QtCore import QObject, Signal
from app.app_config import AppConfig
from app.app_state import AppState
from model.song import Song
from managers.worker_manager import WorkerManager

class AppData(QObject):
    """Main application data hub that coordinates between components"""
    
    # Forward signals from AppState
    selected_songs_changed = Signal(list)
    selected_song_changed = Signal(object)
    is_loading_songs_changed = Signal(bool)
    gap_detection_finished = Signal(Song)
    gap_updated = Signal(Song)
    gap_reverted = Signal(Song)
    selection_changed = Signal()
    
    def __init__(self, config=None):
        super().__init__()
        
        # Initialize components
        self.app_config = AppConfig(config)
        self.app_state = AppState()
        self.task_manager = WorkerManager()  # Using existing WorkerManager
        
        # Forward signals from app_state
        self._connect_signals()
    
    def _connect_signals(self):
        """Connect internal signals between components"""
        # Forward app_state signals to AppData signals for backward compatibility
        self.app_state.selected_songs_changed.connect(self.selected_songs_changed)
        self.app_state.selected_song_changed.connect(self.selected_song_changed)
        self.app_state.is_loading_songs_changed.connect(self.is_loading_songs_changed)
        self.app_state.gap_detection_finished.connect(self.gap_detection_finished)
        self.app_state.gap_updated.connect(self.gap_updated)
        self.app_state.gap_reverted.connect(self.gap_reverted)
        self.app_state.selection_changed.connect(self.selection_changed)
    
    # Property forwarding for backward compatibility
    @property
    def songs(self):
        return self.app_state.songs
    
    @property
    def selected_songs(self):
        return self.app_state.selected_songs
    
    @selected_songs.setter
    def selected_songs(self, value):
        self.app_state.selected_songs = value
    
    @property
    def first_selected_song(self):
        return self.app_state.first_selected_song
    
    @property
    def is_loading_songs(self):
        return self.app_state.is_loading_songs
    
    @is_loading_songs.setter
    def is_loading_songs(self, value):
        self.app_state.is_loading_songs = value
    
    @property
    def directory(self):
        return self.app_config.directory
    
    @directory.setter
    def directory(self, value):
        self.app_config.directory = value
    
    @property
    def tmp_path(self):
        return self.app_config.tmp_path
    
    @property
    def worker_manager(self):
        return self.task_manager
    
    @property
    def config(self):
        return self.app_config.config



