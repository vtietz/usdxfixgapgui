import os
from PyQt6.QtCore import QObject, pyqtSignal, pyqtProperty
from model.song import Song
from model.songs import Songs

class Config(QObject):

    # Directory where the songs are located
    #directory = os.path.join("..", "samples")
    directory: str = "Z:\\UltraStarDeluxe\\Songs\\usdb.animux.de"

    tmp_root = os.path.join("..", ".tmp")

    # Detection time in seconds
    default_detection_time: int = 30

    # Maximum gap tolerance in milliseconds
    gap_tolerance: int = 500

    detected_gap_color = "blue"
    playback_position_color = "red"
    waveform_color = "gray"

    adjust_player_position_step_audio = 100
    adjust_player_position_step_vocals = 10

    spleeter = True

class AppData(QObject):

    songs: Songs = Songs()
    
    _selected_song: Song = None
    _is_loading_songs: bool = False

    tmp_folder: None

    selected_song_changed = pyqtSignal(Song)
    is_loading_songs_changed = pyqtSignal(bool)

    @pyqtProperty(Song, notify=selected_song_changed)
    def selected_song(self):
        return self._selected_song

    @selected_song.setter
    def selected_song(self, value: Song):
        if self._selected_song != value:
            self._selected_song = value
            self.selected_song_changed.emit(self._selected_song)

    @pyqtProperty(bool, notify=is_loading_songs_changed)
    def is_loading_songs(self):
        return self._is_loading_songs
    
    @is_loading_songs.setter
    def is_loading_songs(self, value: bool):
        if self._is_loading_songs != value:
            self._is_loading_songs = value
            self.is_loading_songs_changed.emit(self._is_loading_songs)


