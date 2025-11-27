import logging
from collections import deque
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
    - Standard (is_instant=False): Long-running tasks that run sequentially
      (gap detection, normalization, scan all)
    - Instant (is_instant=True): User-triggered tasks that can run immediately
      in parallel with standard tasks (waveform, light reload)
    """

    def __init__(self, is_instant: bool = False):
        super().__init__()
        self.signals = IWorkerSignals()
        self._status = WorkerStatus.WAITING
        self._task_id = None
        self._description = "Undefined"
        self._is_canceled = False
        self.is_instant = is_instant  # Instant tasks can run in parallel with standard tasks
        # Cooperative yield: manager can inject a callback the worker checks to decide to yield
        self._yield_check = None

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
        # Don't emit progress on description change - too noisy
        # UI updates are triggered by explicit status changes

    @property
    def status(self):
        """The current status of the worker task."""
        return self._status

    @status.setter
    def status(self, value):
        old_status = self._status
        self._status = value
        # Only emit if status actually changed
        if old_status != value:
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

    def save_error_to_song(self, song, error: Exception):
        """
        Save error message to both song and gap_info (if exists).
        This is a generic helper for all workers that process songs.

        Args:
            song: The song object to save the error to
            error: The exception that occurred
        """
        error_msg = str(error)
        song.error_message = error_msg
        if hasattr(song, "gap_info") and song.gap_info:
            song.gap_info.error_message = error_msg
        logger.debug(f"Saved error to song {song.txt_file}: {error_msg}")

    # New method to let workers handle completion logic
    def complete(self):
        """Mark the worker as complete - this should be called by the worker itself"""
        self.status = WorkerStatus.FINISHED
        # Base implementation doesn't emit any signals - each worker handles this

    # Cooperative yield support
    def set_yield_check(self, fn):
        """
        Set a callback that returns True when the worker should cooperatively yield.
        The manager injects this to allow long-running workers to pause when user-priority work appears.
        """
        try:
            self._yield_check = fn
        except Exception:
            logger.debug("Failed to set yield_check on worker", exc_info=True)

    def should_yield(self) -> bool:
        """
        Return True if the worker should cooperatively yield (pause) right now.
        Safe to call from worker code; returns False if no check is set.
        """
        try:
            return bool(self._yield_check and self._yield_check())
        except Exception:
            # Defensive: never break worker execution due to yield check errors
            logger.debug("yield_check raised unexpectedly", exc_info=True)
            return False


class WorkerQueueManager(QObject):
    task_id_counter = 0
    on_task_list_changed = pyqtSignal()
    _start_queued_task_signal = pyqtSignal()  # Internal signal for heartbeat safety check

    def __init__(self, ui_update_interval=0.25):
        super().__init__()
        # Standard task lane (sequential, long-running) - using deque for O(1) FIFO
        self.queued_tasks = deque()
        self.running_tasks = {}

        # Instant task lane (parallel to standard, max 1 concurrent) - using deque for O(1) FIFO
        self.queued_instant_tasks = deque()
        self.running_instant_task = None

        self._heartbeat_active = True
        self._ui_update_interval = ui_update_interval  # Update interval in seconds
        self._ui_update_pending = False  # Flag to track if UI updates are needed
        self._last_ui_update = time.time()  # Track when the last update occurred
        self._standard_pause_until: float = 0.0  # When standard lane is allowed to resume
        self._standard_lane_hold_count = 0  # Re-entrant hold for standard lane

        # Connect the internal signal to start_next_task
        self._start_queued_task_signal.connect(self.start_next_task)

        # Start a regular Python thread for heartbeat
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._heartbeat_thread.start()

    def _heartbeat_loop(self):
        """Background thread that periodically signals UI updates"""
        while self._heartbeat_active:
            time.sleep(0.1)  # Check more frequently, but update UI less frequently

            # Safety check: ensure queued tasks get started if no tasks are running
            # This prevents tasks from getting stuck in WAITING status
            if self.queued_tasks and not self.running_tasks and not self._is_standard_lane_paused():
                # Emit signal to start task on main thread
                try:
                    self._start_queued_task_signal.emit()
                except Exception as e:
                    logger.debug("Error in heartbeat task starter: %s", e)

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

    def is_task_queued_for_song(self, song_txt_file: str, worker_class_name: str) -> bool:
        """
        Check if a task for a specific song is already queued or running.

        Args:
            song_txt_file: Path to the song's .txt file
            worker_class_name: Name of the worker class (e.g., 'DetectGapWorker', 'NormalizeAudioWorker')

        Returns:
            True if a matching task is queued or running
        """

        def _matches(worker) -> bool:
            if worker.__class__.__name__ != worker_class_name:
                return False
            # Prefer options.txt_file if present
            if hasattr(worker, "options") and hasattr(getattr(worker, "options"), "txt_file"):
                return worker.options.txt_file == song_txt_file
            # Fallback to song_path attribute
            if hasattr(worker, "song_path"):
                return worker.song_path == song_txt_file
            return False

        # Standard running tasks
        for worker in self.running_tasks.values():
            if _matches(worker):
                return True

        # Standard queued tasks
        for worker in self.queued_tasks:
            if _matches(worker):
                return True

        # Instant running task
        if self.running_instant_task and _matches(self.running_instant_task):
            return True

        # Instant queued tasks
        for worker in self.queued_instant_tasks:
            if _matches(worker):
                return True

        return False

    def add_task(self, worker: IWorker, start_now=False, priority=False):
        worker.id = self.get_unique_task_id()
        logger.debug(
            "Creating task: %s (instant=%s, priority=%s)",
            worker.description,
            worker.is_instant,
            priority,
        )
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

            # Start immediately if instant slot is free (instant tasks should always start ASAP)
            # This ensures user-triggered actions (reload, waveform) never wait behind standard tasks
            if self.running_instant_task is None:
                self.start_next_instant_task()
            else:
                # Emit immediate UI update so user sees queued instant task
                self.on_task_list_changed.emit()
        else:
            # Standard lane: long-running sequential tasks
            worker.status = WorkerStatus.WAITING

            # Provide cooperative yield check to allow pre-emption/pause while instant tasks run
            try:

                def yield_fn() -> bool:
                    return (
                        self._is_standard_lane_paused()
                        or bool(self.running_instant_task)
                        or bool(self.queued_instant_tasks)
                    )

                worker.set_yield_check(yield_fn)
            except Exception:
                logger.debug("Failed to attach yield_check to worker", exc_info=True)

            # Priority tasks go to front of queue (executed next), normal tasks go to back
            if priority:
                self.queued_tasks.appendleft(worker)
                logger.debug(
                    "[QUEUE] Added to front of standard queue (priority): %s (queue size: %s)",
                    worker.description,
                    len(self.queued_tasks),
                )
            else:
                self.queued_tasks.append(worker)
                logger.debug(
                    "[QUEUE] Added to back of standard queue: %s (queue size: %s)",
                    worker.description,
                    len(self.queued_tasks),
                )

            # Emit immediate UI update when adding to queue (don't wait for heartbeat)
            # This ensures users see queued tasks right away
            self.on_task_list_changed.emit()

            # Start immediately if requested or if nothing is running
            if start_now or not self.running_tasks:
                self.start_next_task()

    def get_unique_task_id(self):
        WorkerQueueManager.task_id_counter += 1
        return str(WorkerQueueManager.task_id_counter)

    async def _start_worker(self, worker: IWorker):
        try:
            logger.debug(f"Starting worker: {worker.description}")
            worker.status = WorkerStatus.RUNNING
            worker.signals.started.emit()
            # Note: worker already added to running_tasks in start_next_task()
            # to prevent race condition
            # Reflect status change immediately
            self.on_task_list_changed.emit()

            await worker.run()

            # Only update status if not already canceled
            if worker.status != WorkerStatus.CANCELLING:
                worker.status = WorkerStatus.FINISHED

        except Exception as e:
            logger.error(f"Exception in _start_worker for {worker.description}")
            logger.exception(e)
            worker.status = WorkerStatus.ERROR
            worker.signals.error.emit(e)  # This is still ok as it takes the exception as arg

    def on_task_finished(self, task_id):
        logger.debug(f"Task {task_id} finished")
        worker = self.get_worker(task_id)
        if worker:
            worker.status = WorkerStatus.FINISHED
        else:
            logger.debug(f"Worker {task_id} not found in running tasks (likely instant worker already cleaned up)")
        self._finalize_task(task_id)

    def _finalize_task(self, task_id):
        # Check if this is an instant task
        if self.running_instant_task and self.running_instant_task.id == task_id:
            self.running_instant_task = None
            # Emit immediately before starting next task to show current state
            self.on_task_list_changed.emit()
            # Start next instant task if any queued
            if self.queued_instant_tasks:
                self.start_next_instant_task()
        else:
            # Standard task lane
            self.running_tasks.pop(task_id, None)
            # Emit immediately before starting next task to show current state
            self.on_task_list_changed.emit()
            if self.queued_tasks and not self.running_tasks:
                # Start next task directly, no need for QTimer
                self.start_next_task()

        # Mark for coalesced updates
        self._mark_ui_update_needed()

    def start_next_task(self):
        # Critical: Check BEFORE removing from queue to prevent race condition
        # where multiple tasks are removed before any have been added to running_tasks
        if not self.queued_tasks:
            return
        if self.running_tasks:
            return
        if self._is_standard_lane_paused():
            return

        worker = self.queued_tasks.popleft()  # FIFO: remove from head
        logger.debug(
            "[QUEUE] Starting task: %s (remaining queued: %s)",
            worker.description,
            len(self.queued_tasks),
        )
        # Immediately add a placeholder to running_tasks to prevent race condition
        # where _finalize_task → start_next_task is called before _start_worker executes
        self.running_tasks[worker.id] = worker
        # Emit immediately to show task transition
        self.on_task_list_changed.emit()
        run_async(self._start_worker(worker))

    def start_next_instant_task(self):
        """Start the next instant task if the instant slot is available"""
        if self.queued_instant_tasks and self.running_instant_task is None:
            worker = self.queued_instant_tasks.popleft()  # FIFO: remove from head
            logger.debug("Starting instant task: %s", worker.description)
            # Emit immediately after removing from queue to show transition
            self.on_task_list_changed.emit()
            run_async(self._start_instant_worker(worker))

    async def _start_instant_worker(self, worker: IWorker):
        """Start an instant worker in the instant lane"""
        try:
            logger.debug(f"Starting instant worker: {worker.description}")
            worker.status = WorkerStatus.RUNNING
            worker.signals.started.emit()
            self.running_instant_task = worker
            # Reflect move from queue->running immediately
            self.on_task_list_changed.emit()

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
            # Mark UI update; viewer updates button immediately
            self._mark_ui_update_needed()
        else:
            # Check if it's in the standard queue
            for worker in list(self.queued_tasks):  # Convert to list for safe iteration
                if worker.id == task_id:
                    worker.cancel()
                    self.queued_tasks.remove(worker)  # Remove by value instead of index
                    # Mark UI update; heartbeat will emit
                    self._mark_ui_update_needed()
                    return
            # Check if it's in the instant queue
            for worker in list(self.queued_instant_tasks):  # Convert to list for safe iteration
                if worker.id == task_id:
                    worker.cancel()
                    self.queued_instant_tasks.remove(worker)  # Remove by value instead of index
                    # Mark UI update; heartbeat will emit
                    self._mark_ui_update_needed()
                    return

    def cancel_queue(self):
        # Cancel standard queue - head-first for "top-to-bottom" user expectation
        while self.queued_tasks:
            worker = self.queued_tasks.popleft()  # Cancel from head (FIFO order)
            worker.cancel()
        for task_id in list(self.running_tasks.keys()):
            self.cancel_task(task_id)

        # Cancel instant queue - head-first for "top-to-bottom" user expectation
        while self.queued_instant_tasks:
            worker = self.queued_instant_tasks.popleft()  # Cancel from head (FIFO order)
            worker.cancel()
        if self.running_instant_task:
            self.cancel_task(self.running_instant_task.id)

        self._mark_ui_update_needed()

    def on_task_error(self, task_id, e):
        import traceback

        worker = self.get_worker(task_id)

        # Log error with full details
        logger.error("=" * 60)
        logger.error(f"TASK ERROR - ID: {task_id}")
        if worker:
            logger.error(f"Task Description: {worker.description}")
        logger.error(f"Error: {str(e)}")

        # Log full stack trace if available
        if hasattr(e, "__traceback__") and e.__traceback__:
            logger.error("Stack trace:")
            for line in traceback.format_exception(type(e), e, e.__traceback__):
                logger.error(line.rstrip())
        logger.error("=" * 60)

        if worker:
            worker.status = WorkerStatus.ERROR
            # Show user-friendly error dialog
            self._show_task_error_dialog(worker, e)
        self.on_task_finished(task_id)

    def _show_task_error_dialog(self, worker: IWorker, exception: Exception):
        """
        Show error dialog to user when a worker task fails.

        Args:
            worker: The failed worker
            exception: The exception that caused the failure
        """
        import os
        import traceback
        from PySide6.QtWidgets import QMessageBox
        from PySide6.QtCore import QTimer

        # Don't show dialogs in test/CI environment
        if os.environ.get("USDX_SUPPRESS_ERROR_DIALOGS") == "1":
            logger.debug("Error dialog suppressed (USDX_SUPPRESS_ERROR_DIALOGS=1)")
            return

        logger.info(f"Showing error dialog to user for task: {worker.description}")

        def show_dialog():
            """Show dialog on main GUI thread."""
            try:
                msg_box = QMessageBox()
                msg_box.setIcon(QMessageBox.Icon.Critical)
                msg_box.setWindowTitle("Task Failed")

                # User-friendly message
                msg_box.setText(
                    f"Task failed: {worker.description}\n\n"
                    f"Error: {str(exception)}\n\n"
                    "The application will continue running, but this task could not be completed."
                )

                # Detailed technical info
                if hasattr(exception, "__traceback__") and exception.__traceback__:
                    details = "".join(traceback.format_exception(type(exception), exception, exception.__traceback__))
                    msg_box.setDetailedText(details)

                msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
                msg_box.exec()

                logger.info("Error dialog closed by user")

            except Exception as dialog_error:
                # If dialog fails, at least log it
                logger.error(f"Failed to show error dialog: {dialog_error}")

        # Queue dialog on main GUI thread to avoid threading issues
        QTimer.singleShot(0, show_dialog)

    def on_task_canceled(self, task_id):
        logger.info(f"Task {task_id} canceled")
        self.on_task_finished(task_id)

    def on_task_updated(self, task_id):
        # Coalesce updates via heartbeat to avoid flicker
        self._mark_ui_update_needed()

    def set_update_interval(self, seconds):
        """Change the UI update interval"""
        self._ui_update_interval = max(0.1, seconds)  # Minimum 0.1 seconds

    def pause_standard_lane(self, milliseconds: int = 250):
        """Temporarily delay starting standard-lane tasks (e.g., to prioritize user actions)."""
        ms = max(0, milliseconds)
        pause_until = time.time() + (ms / 1000.0)
        if pause_until > self._standard_pause_until:
            self._standard_pause_until = pause_until
            logger.debug("Standard queue paused for %dms", ms)

    def hold_standard_lane(self, reason=None):
        """Block standard-lane tasks until the hold is explicitly released (re-entrant)."""
        self._standard_lane_hold_count += 1
        logger.debug(
            "Standard queue hold ++ (reason=%s, count=%d)",
            reason or "unspecified",
            self._standard_lane_hold_count,
        )

    def release_standard_lane(self, reason=None):
        if self._standard_lane_hold_count <= 0:
            return
        self._standard_lane_hold_count -= 1
        logger.debug(
            "Standard queue hold -- (reason=%s, count=%d)",
            reason or "unspecified",
            self._standard_lane_hold_count,
        )

    def _is_standard_lane_paused(self) -> bool:
        if self._standard_lane_hold_count > 0:
            return True
        if not self._standard_pause_until:
            return False
        if time.time() >= self._standard_pause_until:
            self._standard_pause_until = 0.0
            return False
        return True

    # Add method to clean up when app closes
    def cleanup(self):
        self._heartbeat_active = False
        if self._heartbeat_thread.is_alive():
            self._heartbeat_thread.join(timeout=0.5)

    # Add this method to the WorkerQueueManager class
    def shutdown(self):
        """Properly shut down all workers when the application is closing"""
        logger.info("Shutting down worker queue - cancelling all tasks")

        # Cancel all queued tasks (standard and instant)
        self.cancel_queue()

        # Cancel all currently running tasks (standard lane)
        running_task_ids = list(self.running_tasks.keys())
        for task_id in running_task_ids:
            worker = self.running_tasks.get(task_id)
            if worker:
                logger.info("Cancelling task: %s %s", task_id, worker.description)
                worker.cancel()

        # Cancel instant task if running
        if self.running_instant_task:
            logger.info("Cancelling instant task: %s", self.running_instant_task.description)
            self.running_instant_task.cancel()

        # Wait for running tasks to finish gracefully (with a timeout)
        # This is critical - we must wait for async tasks to complete before asyncio shutdown
        if self.running_tasks or self.running_instant_task:
            MAX_WAIT_MS = 3000  # 3 seconds max wait (increased to allow proper cleanup)
            start_time = time.time()

            logger.debug(
                "Waiting for %s tasks to complete cancellation",
                len(self.running_tasks) + (1 if self.running_instant_task else 0),
            )

            while (self.running_tasks or self.running_instant_task) and time.time() - start_time < (MAX_WAIT_MS / 1000):
                QApplication.processEvents()
                time.sleep(0.05)  # Check every 50ms

            # Log results
            remaining = len(self.running_tasks) + (1 if self.running_instant_task else 0)
            if remaining > 0:
                logger.warning("Shutdown timeout - %s tasks still running after %sms", remaining, MAX_WAIT_MS)
                # Force-clear to prevent further issues
                self.running_tasks.clear()
                self.running_instant_task = None
            else:
                elapsed_ms = int((time.time() - start_time) * 1000)
                logger.info("All tasks completed cancellation in %sms", elapsed_ms)

        # Clean up resources
        self.cleanup()
        logger.info("Worker queue shutdown complete")
