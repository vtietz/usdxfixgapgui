import logging
from PySide6.QtCore import QObject, QTimer
from typing import List, Callable, Any
from app.app_data import AppData
from managers.worker_queue_manager import WorkerQueueManager
from model.song import Song

logger = logging.getLogger(__name__)

class BaseManager(QObject):
    """Base class for all managers with common functionality"""

    def __init__(self, data: AppData, worker_queue: WorkerQueueManager):
        super().__init__()
        self.data = data
        self.config = data.config
        self.worker_queue = worker_queue

    def _queue_tasks_non_blocking(self, songs: List[Song], callback: Callable[[Song, bool], Any]):
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

    def _process_next_song(self, remaining_songs: List[Song], callback: Callable[[Song, bool], Any]):
        """Process the next song in the queue with a delay"""
        if not remaining_songs:
            return

        # Process the next song
        next_song = remaining_songs.pop(0)
        callback(next_song, False)  # False = not first song

        # If there are more songs, queue the next one with a delay
        if remaining_songs:
            QTimer.singleShot(50, lambda: self._process_next_song(remaining_songs, callback))
