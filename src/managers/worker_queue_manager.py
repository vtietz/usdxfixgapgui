import logging
from PySide6.QtCore import QObject, Signal as pyqtSignal
from PySide6.QtWidgets import QApplication
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
    
    Workers can be classified as:
    - Standard (is_instant=False): Long-running tasks that run sequentially (gap detection, normalization, scan all)
    - Instant (is_instant=True): User-triggered tasks that can run immediately in parallel with standard tasks (waveform, light reload)
    """
    def __init__(self, is_instant: bool = False):
        super().__init__()
        self.signals = IWorkerSignals()
        self._status = WorkerStatus.WAITING
        self._task_id = None
        self._description = "Undefined"
        self._is_canceled = False
        self.is_instant = is_instant  # Instant tasks can run in parallel with standard tasks

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
        # Standard task lane (sequential, long-running)
        self.queued_tasks = []
        self.running_tasks = {}
        
        # Instant task lane (parallel to standard, max 1 concurrent)
        self.queued_instant_tasks = []
        self.running_instant_task = None
        
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
        logger.info(f"Creating task: {worker.description} (instant={worker.is_instant})")
        # Be tolerant to different signal signatures (e.g. DetectGapWorker.finished emits a result)
        worker.signals.finished.connect(lambda *args, wid=worker.id: self.on_task_finished(wid))
        worker.signals.error.connect(lambda e=None, wid=worker.id: self.on_task_error(wid, e))
        worker.signals.canceled.connect(lambda *args, wid=worker.id: self.on_task_canceled(wid))
        worker.signals.progress.connect(lambda *args, wid=worker.id: self.on_task_updated(wid))

        # Route to appropriate lane
        if worker.is_instant:
            # Instant lane: user-triggered, runs in parallel with standard tasks
            worker.status = WorkerStatus.WAITING
            self.queued_instant_tasks.append(worker)
            
            # Emit immediately so TaskQueueViewer updates right away
            self.on_task_list_changed.emit()
            self._mark_ui_update_needed()
            
            # Start immediately if requested and no instant task is running
            if start_now and self.running_instant_task is None:
                self.start_next_instant_task()
        else:
            # Standard lane: long-running sequential tasks
            worker.status = WorkerStatus.WAITING
            self.queued_tasks.append(worker)

            # Emit immediately so TaskQueueViewer updates right away, and also mark for coalesced refresh
            self.on_task_list_changed.emit()
            self._mark_ui_update_needed()

            # Start immediately if requested or if nothing is running
            if start_now or not self.running_tasks:
                self.start_next_task()

    def get_unique_task_id(self):
        WorkerQueueManager.task_id_counter += 1
        return str(WorkerQueueManager.task_id_counter)

    async def _start_worker(self, worker: IWorker):
        try:
            logger.info(f"Starting worker: {worker.description}")
            worker.status = WorkerStatus.RUNNING
            worker.signals.started.emit()
            self.running_tasks[worker.id] = worker
            # Reflect move from queue->running immediately
            self.on_task_list_changed.emit()
            self._mark_ui_update_needed()

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
        # Check if this is an instant task
        if self.running_instant_task and self.running_instant_task.id == task_id:
            self.running_instant_task = None
            # Start next instant task if any queued
            if self.queued_instant_tasks:
                self.start_next_instant_task()
        else:
            # Standard task lane
            self.running_tasks.pop(task_id, None)
            if self.queued_tasks and not self.running_tasks:
                # Start next task directly, no need for QTimer
                self.start_next_task()
        
        # Emit immediately so the UI reflects removals promptly, and mark for coalesced updates
        self.on_task_list_changed.emit()
        self._mark_ui_update_needed()

    def start_next_task(self):
        if self.queued_tasks and not self.running_tasks:
            worker = self.queued_tasks.pop(0)
            logger.info(f"Starting task: {worker.description}")
            run_async(self._start_worker(worker))
            # Reflect the change right away in the TaskQueueViewer
            self.on_task_list_changed.emit()
            self._mark_ui_update_needed()

    def start_next_instant_task(self):
        """Start the next instant task if the instant slot is available"""
        if self.queued_instant_tasks and self.running_instant_task is None:
            worker = self.queued_instant_tasks.pop(0)
            logger.info(f"Starting instant task: {worker.description}")
            self.running_instant_task = worker
            run_async(self._start_instant_worker(worker))
            # Reflect the change right away in the TaskQueueViewer
            self.on_task_list_changed.emit()
            self._mark_ui_update_needed()

    async def _start_instant_worker(self, worker: IWorker):
        """Start an instant worker in the instant lane"""
        try:
            logger.info(f"Starting instant worker: {worker.description}")
            worker.status = WorkerStatus.RUNNING
            worker.signals.started.emit()
            # Reflect move from queue->running immediately
            self.on_task_list_changed.emit()
            self._mark_ui_update_needed()

            await worker.run()

            # Only update status if not already canceled
            if worker.status != WorkerStatus.CANCELLING:
                worker.status = WorkerStatus.FINISHED

        except Exception as e:
            logger.error(f"Exception in _start_instant_worker for {worker.description}")
            logger.exception(e)
            worker.status = WorkerStatus.ERROR
            worker.signals.error.emit(e)

    def get_worker(self, task_id):
        # Check standard lane first
        worker = self.running_tasks.get(task_id, None)
        if worker:
            return worker
        # Check instant lane
        if self.running_instant_task and self.running_instant_task.id == task_id:
            return self.running_instant_task
        return None

    def cancel_task(self, task_id):
        worker = self.get_worker(task_id)
        if worker:
            worker.cancel()
            # Force an immediate UI update when cancelling
            self.on_task_list_changed.emit()
        else:
            # Check if it's in the standard queue
            for i, worker in enumerate(self.queued_tasks):
                if worker.id == task_id:
                    worker.cancel()
                    self.queued_tasks.pop(i)
                    # Force an immediate UI update
                    self.on_task_list_changed.emit()
                    return
            # Check if it's in the instant queue
            for i, worker in enumerate(self.queued_instant_tasks):
                if worker.id == task_id:
                    worker.cancel()
                    self.queued_instant_tasks.pop(i)
                    # Force an immediate UI update
                    self.on_task_list_changed.emit()
                    return

    def cancel_queue(self):
        # Cancel standard queue
        while self.queued_tasks:
            worker = self.queued_tasks.pop()
            worker.cancel()
        for task_id in list(self.running_tasks.keys()):
            self.cancel_task(task_id)
        
        # Cancel instant queue
        while self.queued_instant_tasks:
            worker = self.queued_instant_tasks.pop()
            worker.cancel()
        if self.running_instant_task:
            self.cancel_task(self.running_instant_task.id)
            
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
        # Emit immediate update so status changes are visible promptly,
        # and also mark for coalesced refresh via heartbeat
        self.on_task_list_changed.emit()
        self._mark_ui_update_needed()

    def set_update_interval(self, seconds):
        """Change the UI update interval"""
        self._ui_update_interval = max(0.1, seconds)  # Minimum 0.1 seconds

    # Add method to clean up when app closes
    def cleanup(self):
        self._heartbeat_active = False
        if self._heartbeat_thread.is_alive():
            self._heartbeat_thread.join(timeout=0.5)

    # Add this method to the WorkerQueueManager class
    def shutdown(self):
        """Properly shut down all workers when the application is closing"""
        logger.info("Shutting down worker queue")

        # Cancel all pending tasks
        self.cancel_queue()  # Use existing method instead of cancel_all_tasks

        # Wait for running tasks to finish (with a timeout)
        if self.running_tasks:  # Check if there are running tasks instead of current_worker
            MAX_WAIT_MS = 2000  # 2 seconds max wait
            start_time = time.time()
            while self.running_tasks and time.time() - start_time < (MAX_WAIT_MS / 1000):
                QApplication.processEvents()
                time.sleep(0.1)

        # Clean up resources
        self.cleanup()
