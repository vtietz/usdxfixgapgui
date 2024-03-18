import logging
from PyQt6.QtCore import QObject, QThreadPool, pyqtSignal, QRunnable
from enum import Enum

logger = logging.getLogger(__name__)

class IWorkerSignals(QObject):
    """Signals to be used by the IWorker class for inter-thread communication."""
    started = pyqtSignal()
    finished = pyqtSignal()
    progress = pyqtSignal()
    canceled = pyqtSignal()
    error = pyqtSignal(tuple)  # Consider defining a specific error class or structure

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
        self.isRunning = False

    def add_task(self, worker: IWorker, start_now=False):
        """Add a task to the queue or start immediately."""
        worker.id = self.get_unique_task_id()
        self.active_task_ids.add(worker.id)
        worker.signals.finished.connect(lambda: self.on_task_finished(worker.id))
        worker.signals.error.connect(lambda error_info: self.on_task_error(worker.id, error_info))
        worker.signals.canceled.connect(lambda: self.on_task_canceled(worker.id))
        worker.signals.progress.connect(lambda: self.on_task_updated(worker.id))
        
        if start_now:
            self._start_worker(worker)
        else:
            self.queue.append(worker)
            self.start_next_task()
        
        self.on_task_list_changed.emit()

    def get_unique_task_id(self):
        """Generate a unique task ID."""
        WorkerQueueManager.task_id_counter += 1
        return str(WorkerQueueManager.task_id_counter)

    def start_next_task(self):
        """Start the next task in the queue if not already running a task."""
        if self.queue and not self.isRunning:
            worker = self.queue.pop(0)
            logger.info(f"Starting task: {worker.description}")
            self._start_worker(worker)

    def _start_worker(self, worker: IWorker):
        """Start a worker task."""
        worker.status = WorkerStatus.RUNNING
        worker.signals.started.emit()
        self._thread_pool.start(worker)
        self.running_tasks[worker.id] = worker 
        self.on_task_list_changed.emit()

    def get_worker(self, task_id) -> IWorker:
        """Retrieve a worker by its task ID."""
        for worker in self.queue:
            if worker.id == task_id:
                return worker
        return self.running_tasks.get(task_id, None)

    def cancel_task(self, task_id):
        """Cancel a task by its ID."""
        logger.info(f"Cancelling task: {task_id}")
        worker = self.get_worker(task_id)
        logger.info(f"Worker: {worker}")
        if worker:
            worker.cancel()

    def cancel_queue(self):
        """Cancel all tasks in the queue."""
        for worker in self.queue:
            worker.cancel()
        self.queue.clear()
        self.active_task_ids.clear()
        self.isRunning = False
        self.on_task_list_changed.emit()

    def on_task_finished(self, task_id):
        logger.info(f"Task {task_id} finished")
        self.running_tasks.pop(task_id, None) 
        self._finalize_task(task_id)

    def on_task_error(self, task_id, error_info):
        logger.error(f"Task {task_id} error: {error_info[0]}")
        self._finalize_task(task_id)

    def on_task_canceled(self, task_id):
        logger.info(f"Task {task_id} canceled")
        self._finalize_task(task_id)

    def on_task_updated(self, task_id):
        logger.info(f"Task {task_id} updated")
        self.on_task_list_changed.emit()

    def _finalize_task(self, task_id):
        """Finalize task completion, error, or cancellation."""
        logger.info(f"Finalizing task: {task_id}")
        self.active_task_ids.discard(task_id)
        self.running_tasks.pop(task_id, None) 
        self.isRunning = False
        self.start_next_task()
        self.on_task_list_changed.emit()