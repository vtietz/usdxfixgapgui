"""
WatchModeController: Orchestrates filesystem watching and automated cache/detection updates.

Coordinates DirectoryWatcher, CacheUpdateScheduler, and GapDetectionScheduler
to provide seamless watch mode functionality.
"""

import logging
from PySide6.QtCore import QObject, Signal

from services.directory_watcher import DirectoryWatcher, WatchEvent
from services.cache_update_scheduler import CacheUpdateScheduler
from services.gap_detection_scheduler import GapDetectionScheduler
from workers.rescan_single_song import RescanSingleSongWorker
from model.song import Song

logger = logging.getLogger(__name__)


class WatchModeController(QObject):
    """
    Orchestrates watch mode components.

    Coordinates:
    - DirectoryWatcher: OS-native filesystem monitoring
    - CacheUpdateScheduler: Cache updates for Created/Deleted/Moved events
    - GapDetectionScheduler: Gap detection for Modified events

    Signals:
        started: Emitted when watch mode starts
        stopped: Emitted when watch mode stops
        error_occurred: Emitted when an error occurs (str)
    """

    started = Signal()
    stopped = Signal()
    error_occurred = Signal(str)

    def __init__(
        self,
        directory: str,
        debounce_ms: int,
        ignore_patterns: set,
        worker_queue_add_task,
        start_gap_detection,
        songs_get_by_txt_file,
        songs_get_by_path,
        songs_add,
        songs_remove_by_txt_file,
    ):
        """
        Initialize WatchModeController.

        Args:
            directory: Directory to watch
            debounce_ms: Debounce time in milliseconds
            ignore_patterns: Set of file patterns to ignore
            worker_queue_add_task: Callable to add tasks to worker queue
            start_gap_detection: Callable(song) to start gap detection
            songs_get_by_txt_file: Callable(txt_path) to get Song by txt file
            songs_get_by_path: Callable(path) to get Song by folder path
            songs_add: Callable(song) to add song to Songs collection
            songs_remove_by_txt_file: Callable(txt_file) to remove song
        """
        super().__init__()

        self._directory = directory
        self._debounce_ms = debounce_ms
        self._is_running = False

        # Initialize components
        self._watcher = DirectoryWatcher(ignore_patterns=ignore_patterns)

        self._cache_scheduler = CacheUpdateScheduler(
            worker_queue_add_task=worker_queue_add_task, songs_get_by_txt_file=songs_get_by_txt_file
        )

        self._gap_scheduler = GapDetectionScheduler(
            debounce_ms=debounce_ms,
            start_gap_detection=start_gap_detection,
            songs_get_by_txt_file=songs_get_by_txt_file,
            songs_get_by_path=songs_get_by_path,
        )

        # Store callbacks
        self._songs_add = songs_add
        self._songs_remove_by_txt_file = songs_remove_by_txt_file

        # Connect signals
        self._watcher.file_event.connect(self._on_file_event)
        self._watcher.error_occurred.connect(self._on_watcher_error)
        self._watcher.started.connect(self._on_watcher_started)
        self._watcher.stopped.connect(self._on_watcher_stopped)

        self._cache_scheduler.song_added.connect(self._on_song_added_worker)
        self._cache_scheduler.song_removed.connect(self._on_song_removed)

    def start(self) -> bool:
        """
        Start watch mode.

        Returns:
            True if started successfully, False otherwise
        """
        if self._is_running:
            logger.warning("Watch mode already running")
            return False

        logger.info(f"Starting watch mode on {self._directory}")

        success = self._watcher.start_watching(self._directory)

        if success:
            self._is_running = True

        return success

    def stop(self):
        """Stop watch mode."""
        if not self._is_running:
            return

        logger.info("Stopping watch mode")

        self._watcher.stop_watching()
        self._gap_scheduler.clear_pending()

        self._is_running = False

    def is_running(self) -> bool:
        """Check if watch mode is currently running."""
        return self._is_running

    def mark_detection_complete(self, song: Song):
        """
        Mark gap detection as complete for a song.

        Should be called when gap detection finishes.

        Args:
            song: The song that finished detection
        """
        self._gap_scheduler.mark_detection_complete(song)

    def _on_file_event(self, event: WatchEvent):
        """Handle filesystem event by routing to appropriate scheduler."""
        try:
            # Route to cache scheduler for create/delete/move
            if event.event_type in [event.event_type.CREATED, event.event_type.DELETED, event.event_type.MOVED]:
                self._cache_scheduler.handle_event(event)

            # Route to gap detection scheduler for modify
            if event.event_type == event.event_type.MODIFIED:
                self._gap_scheduler.handle_event(event)

        except Exception as e:
            logger.error(f"Error handling file event: {e}", exc_info=True)
            self.error_occurred.emit(f"Error handling file event: {e}")

    def _on_song_added_worker(self, worker: RescanSingleSongWorker):
        """Handle song scan worker being added."""
        # Connect to get results
        worker.signals.songScanned.connect(self._on_song_scanned)

    def _on_song_scanned(self, song: Song):
        """Handle newly scanned song."""
        try:
            logger.info(f"Adding scanned song to collection: {song.artist} - {song.title}")
            self._songs_add(song)

        except Exception as e:
            logger.error(f"Error adding scanned song: {e}", exc_info=True)

    def _on_song_removed(self, txt_file: str):
        """Handle song removal."""
        try:
            logger.info(f"Removing song from collection: {txt_file}")
            self._songs_remove_by_txt_file(txt_file)

        except Exception as e:
            logger.error(f"Error removing song: {e}", exc_info=True)

    def _on_watcher_error(self, error: str):
        """Handle watcher error."""
        logger.error(f"Directory watcher error: {error}")
        self.error_occurred.emit(error)

    def _on_watcher_started(self):
        """Handle watcher started."""
        logger.info("Directory watcher started successfully")
        self.started.emit()

    def _on_watcher_stopped(self):
        """Handle watcher stopped."""
        logger.info("Directory watcher stopped")
        self.stopped.emit()
