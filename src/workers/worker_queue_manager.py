import logging
from PySide6.QtCore import QObject, Signal as pyqtSignal, QTimer
from enum import Enum
import threading
import time

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
    ERROR = 5

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
    
    # New method to let workers handle completion logic
    def complete(self):
        """Mark the worker as complete - this should be called by the worker itself"""
        self.status = WorkerStatus.FINISHED
        # Base implementation doesn't emit any signals - each worker handles this
    
class WorkerQueueManager(QObject):
    task_id_counter = 0
    on_task_list_changed = pyqtSignal()

    def __init__(self, ui_update_interval=1.0):
        super().__init__()
        self.queued_tasks = []
        self.running_tasks = {}
        self._heartbeat_active = True
        self._ui_update_interval = ui_update_interval  # Update interval in seconds
        self._ui_update_pending = False  # Flag to track if UI updates are needed
        self._last_ui_update = time.time()  # Track when the last update occurred
        # Start a regular Python thread for heartbeat
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._heartbeat_thread.start()

    def _heartbeat_loop(self):
        """Background thread that periodically signals UI updates"""
        while self._heartbeat_active:
            time.sleep(0.1)  # Check more frequently, but update UI less frequently
            
            # Only update the UI if needed and if enough time has passed since the last update
            current_time = time.time()
            if self._ui_update_pending and (current_time - self._last_ui_update >= self._ui_update_interval):
                # Reset the flag and update the timestamp
                self._ui_update_pending = False
                self._last_ui_update = current_time
                # Schedule the UI update on the main thread
                self.on_task_list_changed.emit()

    def _mark_ui_update_needed(self):
        """Mark that the UI needs to be updated on the next heartbeat"""
        self._ui_update_pending = True
        
    def check_task_status(self):
        """Manually trigger UI updates when needed"""
        if self.running_tasks or self.queued_tasks:
            self._mark_ui_update_needed()

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
        
        self._mark_ui_update_needed()

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
            
            # Only update status if not already canceled
            if worker.status != WorkerStatus.CANCELLING:
                worker.status = WorkerStatus.FINISHED
                # We don't emit signals here anymore - each worker handles its own signals
            
        except Exception as e:
            logger.error(f"Exception in _start_worker for {worker.description}")
            logger.exception(e)
            worker.status = WorkerStatus.ERROR
            worker.signals.error.emit(e)  # This is still ok as it takes the exception as arg

    def on_task_finished(self, task_id):
        logger.info(f"Task {task_id} finished")
        worker = self.get_worker(task_id)
        if worker:
            worker.status = WorkerStatus.FINISHED
        self._finalize_task(task_id)

    def _finalize_task(self, task_id):
        self.running_tasks.pop(task_id, None)
        if self.queued_tasks and not self.running_tasks:
            # Start next task directly, no need for QTimer
            self.start_next_task()
        # Mark for UI update instead of immediate update
        self._mark_ui_update_needed()

    def start_next_task(self):
        if self.queued_tasks and not self.running_tasks:
            worker = self.queued_tasks.pop(0)
            logger.info(f"Starting task: {worker.description}")
            run_async(self._start_worker(worker))

    def get_worker(self, task_id):
        return self.running_tasks.get(task_id, None)

    def cancel_task(self, task_id):
        worker = self.get_worker(task_id)
        if worker:
            worker.cancel()
        else:
            # Check if it's in the queue
            for i, worker in enumerate(self.queued_tasks):
                if worker.id == task_id:
                    worker.cancel()
                    self.queued_tasks.pop(i)
                    self._mark_ui_update_needed()
                    break

    def cancel_queue(self):
        while self.queued_tasks:
            worker = self.queued_tasks.pop()
            worker.cancel()
        for task_id in list(self.running_tasks.keys()):
            self.cancel_task(task_id)
        self._mark_ui_update_needed()

    def on_task_error(self, task_id, e):
        logger.error(f"Error executing task {task_id}: {e}")
        worker = self.get_worker(task_id)
        if worker:
            worker.status = WorkerStatus.ERROR
        self.on_task_finished(task_id)

    def on_task_canceled(self, task_id):
        logger.info(f"Task {task_id} canceled")
        self.on_task_finished(task_id)

    def on_task_updated(self, task_id):
        # Mark for UI update instead of immediate update
        self._mark_ui_update_needed()
        
    def set_update_interval(self, seconds):
        """Change the UI update interval"""
        self._ui_update_interval = max(0.1, seconds)  # Minimum 0.1 seconds
        
    # Add method to clean up when app closes
    def cleanup(self):
        self._heartbeat_active = False
        if self._heartbeat_thread.is_alive():
            self._heartbeat_thread.join(timeout=0.5)
