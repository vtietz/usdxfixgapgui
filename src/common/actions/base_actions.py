import logging
from PySide6.QtCore import QObject, QTimer
from typing import List, Callable
from common.data import AppData
from model.song import Song

logger = logging.getLogger(__name__)

class BaseActions(QObject):
    """Base class for all action modules"""
    
    def __init__(self, data: AppData):
        """
        Initialize with application data
        
        Args:
            data: Application data instance
        """
        super().__init__()
        self.data = data
        self.config = data.config
        self.worker_queue = data.worker_queue  # Use the shared worker queue from AppData
    
    # TODO: currently not sure if this is helpful
    def _queue_tasks_non_blocking(self, songs: List[Song], callback: Callable):
        """Queue tasks with a small delay between them to avoid UI freeze"""
        if not songs:
            return
            
        # Create a copy of the songs list to avoid modification issues
        songs_to_process = list(songs)
        
        # Process the first song immediately
        first_song = songs_to_process.pop(0)
        callback(first_song, True)  # True = is first song
        
        # If there are more songs, queue them with a small delay
        if songs_to_process:
            QTimer.singleShot(100, lambda: self._process_next_song(songs_to_process, callback))
    
    def _process_next_song(self, remaining_songs: List[Song], callback: Callable):
        """Process the next song in the queue with a delay"""
        if not remaining_songs:
            return
            
        # Process the next song
        next_song = remaining_songs.pop(0)
        callback(next_song, False)  # False = not first song
        
        # If there are more songs, queue the next one with a delay
        if remaining_songs:
            QTimer.singleShot(50, lambda: self._process_next_song(remaining_songs, callback))

    def _on_song_worker_started(self, song: Song):
        from model.song import SongStatus
        song.status = SongStatus.PROCESSING
        self.data.songs.updated.emit(song)

    def _on_song_worker_error(self, song: Song):
        from model.song import SongStatus
        song.status = SongStatus.ERROR
        self.data.songs.updated.emit(song)

    def _on_song_worker_finished(self, song: Song):
        self.data.songs.updated.emit(song)
