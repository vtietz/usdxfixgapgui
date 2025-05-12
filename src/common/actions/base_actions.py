import logging
from PySide6.QtCore import QObject, QTimer
from typing import List, Callable
from app.app_data import AppData
from model.song import Song, SongStatus
from utils.worker_helper import WorkerHelper
from utils.signal_manager import SignalManager

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
        self.worker_helper = WorkerHelper  # Reference the WorkerHelper class
        self.signal_manager = SignalManager  # Reference the SignalManager class
   
    def _on_song_worker_started(self, song: Song):
        """Legacy method maintained for backward compatibility"""
        song.status = SongStatus.PROCESSING
        self.data.songs.updated.emit(song)

    def _on_song_worker_error(self, song: Song):
        """Legacy method maintained for backward compatibility"""
        song.status = SongStatus.ERROR
        self.data.songs.updated.emit(song)

    def _on_song_worker_finished(self, song: Song):
        """Legacy method maintained for backward compatibility"""
        self.data.songs.updated.emit(song)
        
    def queue_worker(self, worker_class, song=None, start_now=False, on_finished=None, **kwargs):
        """Helper method to create and queue workers with standard signal connections"""
        worker = self.worker_helper.create_worker(worker_class, **kwargs)
        
        if song:
            # Set status before connecting signals
            song.status = SongStatus.QUEUED
            self.data.songs.updated.emit(song)
            
            # Use SignalManager for handling signals
            self.signal_manager.connect_worker_signals(
                worker, 
                song, 
                self.data,
                on_finished=on_finished if on_finished else None
            )
            
        self.worker_queue.add_task(worker, start_now)
        return worker
