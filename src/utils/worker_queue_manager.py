import logging
import traceback
from PyQt6.QtCore import QObject, QThreadPool, pyqtSignal, QRunnable
from enum import Enum

logger = logging.getLogger(__name__)

class IWorkerSignals(QObject):
    """Signals to be used by the IWorker class for inter-thread communication."""
    started = pyqtSignal()
    finished = pyqtSignal()
    progress = pyqtSignal()
    canceled = pyqtSignal()
    error = pyqtSignal(str)

class WorkerStatus(Enum):
    """Enum to represent the status of a worker task."""
    RUNNING = 1
    WAITING = 2
    CANCELLING = 3
    FINISHED = 4

class IWorker(QRunnable):
    """
    Base class to provide common interface and functionality for worker tasks.
    This class is designed to be subclassed with specific implementations of the run method.
    """
    def __init__(self):
        super().__init__()
        self.signals = IWorkerSignals()
        self.status = WorkerStatus.WAITING
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

    def run(self):
        """
        Method to execute the worker's task. This method should be implemented
        by subclasses to define specific task behavior.
        """
        raise NotImplementedError("Worker subclass must implement a run method.")

    def cancel(self):
        """
        Method to cancel the worker's task. This method can be overridden by subclasses
        to define custom cancellation behavior.
        """
        logger.info(f"Cancelling task: {self._task_id} {self._description}")
        self._is_canceled = True
        self.status = WorkerStatus.CANCELLING
        self.signals.canceled.emit()

    def is_canceled(self):
        """Check if the worker's task has been cancelled."""
        return self._is_canceled
    
class WorkerQueueManager(QObject):
    task_id_counter = 0
    on_task_list_changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.queue = []
        self.active_task_ids = set()
        self.running_tasks = {}
        self._thread_pool = QThreadPool()

    def add_task(self, worker: IWorker, start_now=False):
        worker.id = self.get_unique_task_id()
        self.active_task_ids.add(worker.id)
        worker.signals.finished.connect(lambda: self.on_task_finished(worker.id))
        worker.signals.error.connect(lambda error_info: self.on_task_error(worker.id, error_info))
        worker.signals.canceled.connect(lambda: self.on_task_canceled(worker.id))
        worker.signals.progress.connect(lambda: self.on_task_updated(worker.id))
        
        if start_now or not self.running_tasks:
            self._start_worker(worker)
        else:
            self.queue.append(worker)
        
        self.on_task_list_changed.emit()

    def get_unique_task_id(self):
        WorkerQueueManager.task_id_counter += 1
        return str(WorkerQueueManager.task_id_counter)

    def _start_worker(self, worker: IWorker):
        worker.status = WorkerStatus.RUNNING
        worker.signals.started.emit()
        self._thread_pool.start(worker)
        self.running_tasks[worker.id] = worker

    def on_task_finished(self, task_id):
        self._finalize_task(task_id)

    def _finalize_task(self, task_id):
        self.running_tasks.pop(task_id, None)
        self.active_task_ids.discard(task_id)
        if self.queue:
            self.start_next_task()
        self.on_task_list_changed.emit()

    def start_next_task(self):
        if self.queue and not self.running_tasks:
            worker = self.queue.pop(0)
            logger.info(f"Starting task: {worker.description}")
            self._start_worker(worker)

    def get_worker(self, task_id) -> IWorker:
        return self.running_tasks.get(task_id, None)

    def cancel_task(self, task_id):
        worker = self.get_worker(task_id)
        if worker:
            worker.cancel()

    def cancel_queue(self):
        while self.queue:
            worker = self.queue.pop()
            worker.cancel()
        for task_id in list(self.running_tasks.keys()):
            self.cancel_task(task_id)
        self.on_task_list_changed.emit()

    def on_task_error(self, task_id, e):
        stack_trace = traceback.format_exc()
        logger.error(f"Error executing task: {e}\nStack trace:\n{stack_trace}")
        self.on_task_finished(task_id)

    def on_task_canceled(self, task_id):
        logger.info(f"Task {task_id} canceled")
        self.on_task_finished(task_id)

    def on_task_updated(self, task_id):
        self.on_task_list_changed.emit()