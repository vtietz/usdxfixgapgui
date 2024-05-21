import logging
from PyQt6.QtCore import QObject, pyqtSignal
from enum import Enum

from utils.run_async import run_async

logger = logging.getLogger(__name__)

class IWorkerSignals(QObject):
    """Signals to be used by the IWorker class for inter-task communication."""
    started = pyqtSignal()
    finished = pyqtSignal()
    progress = pyqtSignal()
    canceled = pyqtSignal()
    error = pyqtSignal(Exception)

class WorkerStatus(Enum):
    """Enum to represent the status of a worker task."""
    RUNNING = 1
    WAITING = 2
    CANCELLING = 3
    FINISHED = 4

class IWorker(QObject):
    """
    Base class to provide a common interface and functionality for worker tasks.
    This class is designed to be subclassed with specific implementations of the asynchronous run method.
    """
    def __init__(self):
        super().__init__()
        self.signals = IWorkerSignals()
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
    
class WorkerQueueManager(QObject):
    task_id_counter = 0
    on_task_list_changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.queued_tasks = []
        self.running_tasks = {}

    def add_task(self, worker: IWorker, start_now=False):
        worker.id = self.get_unique_task_id()
        logger.info(f"Adding task: {worker.description}")
        worker.signals.finished.connect(lambda: self.on_task_finished(worker.id))
        worker.signals.error.connect(lambda e: self.on_task_error(worker.id, e))
        worker.signals.canceled.connect(lambda: self.on_task_canceled(worker.id))
        worker.signals.progress.connect(lambda: self.on_task_updated(worker.id))
        
        if start_now or not self.running_tasks:
            logger.info(f"Scheduling task: {worker.description}")
            run_async(self._start_worker(worker))
        else:
            logger.info(f"Queueing task: {worker.description}")
            worker.status = WorkerStatus.WAITING
            self.queued_tasks.append(worker)
        
        self.on_task_list_changed.emit()

    def get_unique_task_id(self):
        WorkerQueueManager.task_id_counter += 1
        return str(WorkerQueueManager.task_id_counter)

    async def _start_worker(self, worker: IWorker):
        try:
            logger.info(f"Starting worker: {worker.description}")
            worker.status = WorkerStatus.RUNNING
            worker.signals.started.emit()
            self.running_tasks[worker.id] = worker
            await worker.run()
            self.on_task_finished(worker.id)
        except Exception as e:
            logger.error(f"Exception in _start_worker for {worker.description}")
            logger.exception(e)

    def on_task_finished(self, task_id):
        self._finalize_task(task_id)

    def _finalize_task(self, task_id):
        self.running_tasks.pop(task_id, None)
        if self.queued_tasks:
            self.start_next_task()
        self.on_task_list_changed.emit()

    def start_next_task(self):
        if self.queued_tasks and not self.running_tasks:
            worker = self.queued_tasks.pop(0)
            logger.info(f"Starting task: {worker.description}")
            run_async(self._start_worker(worker))

    def get_worker(self, task_id):
        return self.running_tasks.get(task_id, None)

    def cancel_task(self, task_id):
        worker: IWorker = self.get_worker(task_id)
        if worker:
            worker.cancel()

    def cancel_queue(self):
        while self.queued_tasks:
            worker = self.queued_tasks.pop()
            worker.cancel()
        for task_id in list(self.running_tasks.keys()):
            self.cancel_task(task_id)
        self.on_task_list_changed.emit()

    def on_task_error(self, task_id, e):
        logger.error(f"Error executing task {task_id}: {e}")
        self.on_task_finished(task_id)

    def on_task_canceled(self, task_id):
        logger.info(f"Task {task_id} canceled")
        self.on_task_finished(task_id)

    def on_task_updated(self, task_id):
        self.on_task_list_changed.emit()
