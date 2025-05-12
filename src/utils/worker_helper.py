import logging
from typing import Any, Callable, Optional, TypeVar
from PySide6.QtCore import QObject

logger = logging.getLogger(__name__)

T = TypeVar('T')  # Generic type for worker classes

class WorkerHelper:
    """Utility class for managing workers and connecting signals."""
    
    @staticmethod
    def create_worker(worker_class: type[T], *args, **kwargs) -> T:
        """Create a worker instance with the given arguments."""
        return worker_class(*args, **kwargs)
        
    @staticmethod
    def queue_worker(worker: QObject, worker_queue, start_now: bool = False) -> None:
        """Queue a worker task."""
        worker_queue.add_task(worker, start_now)
        
    @staticmethod
    def create_and_queue(worker_class, worker_queue, start_now=False, 
                         data_obj=None, song=None, on_finished=None, 
                         on_started=None, on_error=None, **kwargs):
        """Create a worker, connect signals via SignalManager, and queue it."""
        from utils.signal_manager import SignalManager
        
        worker = WorkerHelper.create_worker(worker_class, **kwargs)
        
        if data_obj and song:
            SignalManager.connect_worker_signals(
                worker, 
                song, 
                data_obj, 
                on_started=on_started,
                on_error=on_error,
                on_finished=on_finished
            )
            
        WorkerHelper.queue_worker(worker, worker_queue, start_now)
        return worker
