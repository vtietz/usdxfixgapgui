import os
from PySide6.QtCore import QObject, Signal, Property  # Updated imports
from config import Config
from model.song import Song
from model.songs import Songs
from utils import files

class AppData(QObject):

    config: Config = Config()

    songs: Songs = Songs()
    
    _selected_song: Song = None
    _is_loading_songs: bool = False

    selected_song_changed = Signal(Song)  # Updated
    is_loading_songs_changed = Signal(bool)  # Updated

    _directory = config.default_directory
    _tmp_path = files.generate_directory_hash(_directory)

    @Property(Song, notify=selected_song_changed)  # Updated
    def selected_song(self):
        return self._selected_song

    @selected_song.setter
    def selected_song(self, value: Song):
        if self._selected_song != value:
            self._selected_song = value
            self.selected_song_changed.emit(self._selected_song)

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

