import os
from typing import List
from PyQt6.QtCore import QObject, pyqtSignal, pyqtProperty
from model.song import Song
from model.songs import Songs
from utils.worker_queue_manager import WorkerQueueManager

class Config(QObject):

    # Directory where the songs are located
    directory = os.path.join("..", "samples")
    #directory: str = "Z:\\UltraStarDeluxe\\Songs\\usdb.animux.de"

    # Detection time in seconds
    default_detection_time: int = 30

    # Maximum gap tolerance in milliseconds
    gap_tolerance: int = 500

    detected_gap_color = "blue"
    playback_position_color = "red"
    waveform_color = "gray"

    adjust_player_position_step = 100

class AppData(QObject):

    songs: Songs = Songs()
    
    _selected_song: Song = None
    _is_loading_songs: bool = False
    _player_position = 0
    _playing = False

    selected_song_changed = pyqtSignal(Song)
    is_loading_songs_changed = pyqtSignal(bool)
    player_position_changed = pyqtSignal(int)
    playing_changed = pyqtSignal(bool)

    worker_queue = WorkerQueueManager()


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

    @pyqtProperty(int, notify=player_position_changed)
    def player_position(self):
        return self._player_position

    @player_position.setter
    def player_position(self, value: int):
        if self._player_position != value:
            self._player_position = value
            self.player_position_changed.emit(self._player_position)

    def update_player_position(self, position):
        self.player_position = int(position) 

    @pyqtProperty(bool)
    def playing(self):
        return self._playing
    
    @playing.setter
    def playing(self, value: bool):
        print("Setting playing to", value)
        self._playing = value
        self.playing_changed.emit(self._playing) 

    def update_playing(self, value: bool):
        self.playing = value

