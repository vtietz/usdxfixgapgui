import os
from PySide6.QtCore import QObject, Signal, Property
from typing import List # Import List
from common.config import Config  # This was from config import Config
from model.song import Song
from model.songs import Songs
from utils import files

class AppData(QObject):

    # Added missing signal
    selected_song_changed = Signal(object)

    config: Config = Config()

    songs: Songs = Songs()

    _selected_songs: List[Song] = [] # Use List[Song] for type hint
    _is_loading_songs: bool = False

    selected_songs_changed = Signal(list)  # Signal still uses list
    is_loading_songs_changed = Signal(bool)

    # Add these new signals to support manager communication
    gap_detection_finished = Signal(object)  # Emits the song when gap detection is finished
    gap_updated = Signal(object)             # Emits the song when gap value is updated
    gap_reverted = Signal(object)            # Emits the song when gap value is reverted
    selection_changed = Signal()             # Emits when song selection changes

    _directory = config.default_directory
    _tmp_path = files.generate_directory_hash(_directory)

    @Property(list, notify=selected_songs_changed)  # Property still uses list
    def selected_songs(self):
        return self._selected_songs

    @selected_songs.setter
    def selected_songs(self, value: List[Song]): # Use List[Song] for type hint
        if self._selected_songs != value:
            old_first = self._selected_songs[0] if self._selected_songs else None
            new_first = value[0] if value else None
            self._selected_songs = value
            self.selected_songs_changed.emit(self._selected_songs)
            # Emit selected_song_changed when the first song changes
            if old_first != new_first:
                self.selected_song_changed.emit(new_first)

    @Property(Song, notify=selected_songs_changed) # New property for first selected song
    def first_selected_song(self):
        return self._selected_songs[0] if self._selected_songs else None

    @Property(bool, notify=is_loading_songs_changed)  # Updated
    def is_loading_songs(self):
        return self._is_loading_songs
    
    @is_loading_songs.setter
    def is_loading_songs(self, value: bool):
        if self._is_loading_songs != value:
            self._is_loading_songs = value
            self.is_loading_songs_changed.emit(self._is_loading_songs)

    @property
    def directory(self):
        return self._directory
    
    @directory.setter
    def directory(self, value: str):
        self._directory = value
        path_hash = files.generate_directory_hash(value)
        self._tmp_path = os.path.join(self.config.tmp_root, path_hash)

    @property
    def tmp_path(self):
        return self._tmp_path

