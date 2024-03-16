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
    

class AppData(QObject):
    songs: Songs = Songs()
    
    _selectedSong: Song = None
    _isLoadingSongs: bool = False

    selectedSongChanged = pyqtSignal(Song)
    isLoadingSongsChanged = pyqtSignal(bool)

    workerQueue = WorkerQueueManager()

    @pyqtProperty(Song, notify=selectedSongChanged)
    def selectedSong(self):
        return self._selectedSong

    @selectedSong.setter
    def selectedSong(self, value: Song):
        if self._selectedSong != value:
            self._selectedSong = value
            self.selectedSongChanged.emit(self._selectedSong)

    @pyqtProperty(bool, notify=isLoadingSongsChanged)
    def isLoadingSongs(self):
        return self._isLoadingSongs
    
    @isLoadingSongs.setter
    def isLoadingSongs(self, value: bool):
        if self._isLoadingSongs != value:
            self._isLoadingSongs = value
            self.isLoadingSongsChanged.emit(self._isLoadingSongs)

