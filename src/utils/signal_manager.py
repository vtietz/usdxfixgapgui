import logging
from typing import Any, Callable, Optional, TypeVar
from PySide6.QtCore import QObject
from model.song import Song, SongStatus

logger = logging.getLogger(__name__)

class SignalManager:
    """Centralized signal handling for workers."""
    
    @staticmethod
    def connect_worker_signals(worker, song: Song, data_obj, 
                               on_started: Optional[Callable] = None, 
                               on_error: Optional[Callable] = None, 
                               on_finished: Optional[Callable] = None):
        """
        Connect standard worker signals with customizable handlers.
        
        Args:
            worker: The worker object with signals
            song: The song being processed
            data_obj: The application data object
            on_started: Custom handler for started signal, defaults to standard handler
            on_error: Custom handler for error signal, defaults to standard handler
            on_finished: Custom handler for finished signal, defaults to standard handler
        """
        # Connect started signal
        if hasattr(worker.signals, 'started'):
            if on_started:
                worker.signals.started.connect(on_started)
            else:
                worker.signals.started.connect(lambda: SignalManager._on_worker_started(song, data_obj))
        
        # Connect error signal
        if hasattr(worker.signals, 'error'):
            if on_error:
                worker.signals.error.connect(on_error)
            else:
                worker.signals.error.connect(lambda: SignalManager._on_worker_error(song, data_obj))
        
        # Connect finished signal
        if hasattr(worker.signals, 'finished') and on_finished:
            worker.signals.finished.connect(on_finished)
        elif hasattr(worker.signals, 'finished'):
            worker.signals.finished.connect(lambda: SignalManager._on_worker_finished(song, data_obj))
        
        return worker
    
    @staticmethod
    def connect_custom_signal(worker, signal_name: str, handler: Callable):
        """Connect a custom signal on the worker to a handler."""
        if hasattr(worker.signals, signal_name):
            signal = getattr(worker.signals, signal_name)
            signal.connect(handler)
        else:
            logger.warning(f"Worker does not have signal '{signal_name}'")
    
    @staticmethod
    def _on_worker_started(song: Song, data_obj):
        """Standard handler for worker started signal."""
        song.status = SongStatus.PROCESSING
        data_obj.songs.updated.emit(song)
    
    @staticmethod
    def _on_worker_error(song: Song, data_obj):
        """Standard handler for worker error signal."""
        song.status = SongStatus.ERROR
        data_obj.songs.updated.emit(song)
    
    @staticmethod
    def _on_worker_finished(song: Song, data_obj):
        """Standard handler for worker finished signal."""
        data_obj.songs.updated.emit(song)
