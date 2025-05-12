import logging
from PySide6.QtCore import QObject

from .worker_signals import WorkerSignals
from .worker_status import WorkerStatus

logger = logging.getLogger(__name__)

class Worker(QObject):
    """
    Base class to provide a common interface and functionality for worker tasks.
    This class is designed to be subclassed with specific implementations of the asynchronous run method.
    """
    def __init__(self):
        super().__init__()
        self.signals = WorkerSignals()
        self._status = WorkerStatus.WAITING
        self._task_id = None
        self._description = "Undefined"
        self._is_canceled = False

    @property
    def id(self):
        """Unique identifier for the worker task."""
        return self._task_id

    @id.setter
    def id(self, value):
        self._task_id = value

    @property
    def description(self):
        """A description for the worker task."""
        return self._description

    @description.setter
    def description(self, value):
        self._description = value
        self.signals.progress.emit()

    @property
    def status(self):
        """The current status of the worker task."""
        return self._status
    
    @status.setter
    def status(self, value):
        self._status = value
        self.signals.progress.emit()

    async def run(self):
        """
        Asynchronous method to execute the worker's task. This method should be implemented
        by subclasses to define specific task behavior.
        """
        raise NotImplementedError("Worker subclass must implement an async run method.")

    def cancel(self):
        """
        Method to cancel the worker's task. This method can be overridden by subclasses
        to define custom cancellation behavior.
        """
        logger.info(f"Cancelling task: {self._task_id} {self._description}")
        self._is_canceled = True
        self._status = WorkerStatus.CANCELLING
        self.signals.canceled.emit()

    def is_cancelled(self):
        """Check if the worker's task has been cancelled."""
        return self._is_canceled
    
    def complete(self):
        """Mark the worker as complete - this should be called by the worker itself"""
        self.status = WorkerStatus.FINISHED
        # Base implementation doesn't emit any signals - each worker handles this
