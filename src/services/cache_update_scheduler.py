"""
CacheUpdateScheduler: Handles cache updates for Created/Deleted/Moved filesystem events.

Coordinates cache database updates and AppData synchronization when files are
created, deleted, or moved in the watched directory.

Uses debouncing for CREATED events to ensure files are fully written before scanning.
"""

import logging
import os
from typing import Callable, Dict
from dataclasses import dataclass
from datetime import datetime

from PySide6.QtCore import QObject, Signal, QTimer
from services.directory_watcher import WatchEvent, WatchEventType
from workers.rescan_single_song import RescanSingleSongWorker
from common.database import remove_cache_entry

logger = logging.getLogger(__name__)


@dataclass
class _PendingCreation:
    """Track a pending file creation scan"""

    txt_file: str
    last_event_time: datetime
    timer: QTimer
    file_size: int = 0  # Track file size to detect stability


class CacheUpdateScheduler(QObject):
    """
    Schedules cache updates in response to filesystem events.

    Signals:
        song_added: Emitted when a new song should be added (RescanSingleSongWorker)
        song_removed: Emitted when a song should be removed (str: txt_file_path)
        song_moved: Emitted when a song is moved (old_path: str, new_path: str)
    """

    song_added = Signal(object)  # RescanSingleSongWorker
    song_removed = Signal(str)  # txt_file_path
    song_moved = Signal(str, str)  # old_path, new_path

    def __init__(self, worker_queue_add_task: Callable, songs_get_by_txt_file: Callable, debounce_ms: int = 2000):
        """
        Initialize CacheUpdateScheduler.

        Args:
            worker_queue_add_task: Callable to add tasks to worker queue
            songs_get_by_txt_file: Callable to get Song by txt_file path
            debounce_ms: Milliseconds to wait for file stability before scanning (default 2000ms)
        """
        super().__init__()
        self._worker_queue_add_task = worker_queue_add_task
        self._songs_get_by_txt_file = songs_get_by_txt_file
        self._debounce_ms = debounce_ms

        # Track pending file creations by txt file path
        self._pending_creations: Dict[str, _PendingCreation] = {}

    def handle_event(self, event: WatchEvent):
        """
        Handle a filesystem event and schedule appropriate cache updates.

        Args:
            event: The filesystem event to handle
        """
        try:
            if event.event_type == WatchEventType.CREATED:
                self._handle_created(event)
            elif event.event_type == WatchEventType.DELETED:
                self._handle_deleted(event)
            elif event.event_type == WatchEventType.MOVED:
                self._handle_moved(event)

        except Exception as e:
            logger.error(f"Error handling cache update event: {e}", exc_info=True)

    def _handle_created(self, event: WatchEvent):
        """Handle file/folder creation with debouncing to ensure files are complete."""
        path = event.path

        # Check if it's a .txt file (potential new song)
        if path.lower().endswith(".txt"):
            logger.debug(f"Detected new .txt file creation: {path}")

            # Schedule debounced scan to wait for file to be fully written
            self._schedule_creation_scan(path)

        elif event.is_directory:
            # New directory created - check if it contains .txt files
            self._scan_directory_for_songs(path)

    def _handle_deleted(self, event: WatchEvent):
        """Handle file/folder deletion."""
        path = event.path

        # Check if it's a .txt file
        if path.lower().endswith(".txt"):
            logger.info(f"Detected deleted .txt file: {path}")

            # Remove from cache
            try:
                remove_cache_entry(path)
            except Exception as e:
                logger.warning(f"Failed to remove cache entry for {path}: {e}")

            # Signal for AppData removal
            self.song_removed.emit(path)

        elif event.is_directory:
            # Directory deleted - remove all songs under it
            self._remove_songs_in_directory(path)

    def _handle_moved(self, event: WatchEvent):
        """Handle file/folder move/rename."""
        src_path = event.src_path
        dest_path = event.path

        if not src_path:
            logger.warning(f"Move event missing source path: {event}")
            return

        # Check if it's a .txt file
        if dest_path.lower().endswith(".txt"):
            logger.info(f"Detected moved .txt file: {src_path} -> {dest_path}")

            # Treat as delete + create for simplicity
            # (preserving song ID across moves is complex and error-prone)
            try:
                remove_cache_entry(src_path)
            except Exception as e:
                logger.warning(f"Failed to remove old cache entry for {src_path}: {e}")

            self.song_removed.emit(src_path)

            # Check if song already exists at destination (prevents duplicates on rapid moves)
            existing = self._songs_get_by_txt_file(dest_path)
            if not existing:
                # Rescan at new location
                worker = RescanSingleSongWorker(song_path=dest_path)
                self._worker_queue_add_task(worker)
                self.song_added.emit(worker)
            else:
                logger.debug(f"Song already exists at destination, skipping rescan: {dest_path}")

            self.song_moved.emit(src_path, dest_path)

        elif event.is_directory:
            # Directory moved/renamed - handle all songs inside
            self._handle_directory_moved(src_path, dest_path)

    def _schedule_creation_scan(self, txt_file: str):
        """Schedule a debounced scan for a newly created txt file."""
        # Check if song already exists in collection
        existing = self._songs_get_by_txt_file(txt_file)
        if existing:
            logger.debug(f"Song already exists in collection, skipping creation scan: {txt_file}")
            return

        now = datetime.now()

        # Check if already pending
        if txt_file in self._pending_creations:
            pending = self._pending_creations[txt_file]

            # Update last event time
            pending.last_event_time = now

            # Restart timer
            pending.timer.stop()
            pending.timer.start(self._debounce_ms)

            logger.debug(f"Debouncing creation scan for {txt_file}")
        else:
            # Create new pending creation
            timer = QTimer()
            timer.setSingleShot(True)
            timer.timeout.connect(lambda: self._execute_creation_scan(txt_file))

            pending = _PendingCreation(txt_file=txt_file, last_event_time=now, timer=timer, file_size=0)

            self._pending_creations[txt_file] = pending
            timer.start(self._debounce_ms)

            logger.debug(f"Scheduled creation scan for {txt_file} (debounce {self._debounce_ms}ms)")

    def _execute_creation_scan(self, txt_file: str):
        """Execute scan after debounce period, ensuring file is stable."""
        if txt_file not in self._pending_creations:
            return

        pending = self._pending_creations[txt_file]

        # Check if file is stable (size hasn't changed)
        try:
            if not os.path.exists(txt_file):
                logger.warning(f"File disappeared before scan: {txt_file}")
                del self._pending_creations[txt_file]
                return

            current_size = os.path.getsize(txt_file)

            # If file size changed since last check, reschedule
            if pending.file_size > 0 and current_size != pending.file_size:
                logger.debug(f"File size changed ({pending.file_size} -> {current_size}), rescheduling: {txt_file}")
                pending.file_size = current_size
                pending.last_event_time = datetime.now()
                pending.timer.start(self._debounce_ms)
                return

            # First check or file stable - update size and check again
            if pending.file_size == 0:
                pending.file_size = current_size
                pending.last_event_time = datetime.now()
                pending.timer.start(self._debounce_ms)
                logger.debug(f"Initial file size recorded ({current_size} bytes), waiting for stability: {txt_file}")
                return

            # File is stable - proceed with scan
            logger.info(f"File stable, scanning: {txt_file}")
            del self._pending_creations[txt_file]

            # Schedule targeted rescan
            worker = RescanSingleSongWorker(song_path=txt_file)
            self._worker_queue_add_task(worker)
            self.song_added.emit(worker)

        except Exception as e:
            logger.error(f"Error checking file stability for {txt_file}: {e}", exc_info=True)
            # Clean up and try scanning anyway
            if txt_file in self._pending_creations:
                del self._pending_creations[txt_file]

            worker = RescanSingleSongWorker(song_path=txt_file)
            self._worker_queue_add_task(worker)
            self.song_added.emit(worker)

    def _scan_directory_for_songs(self, directory: str):
        """Scan a directory for .txt files and schedule rescans."""
        try:
            for root, dirs, files in os.walk(directory):
                for filename in files:
                    if filename.lower().endswith(".txt"):
                        txt_path = os.path.join(root, filename)

                        # Check if song already exists in collection
                        existing = self._songs_get_by_txt_file(txt_path)
                        if existing:
                            logger.debug(f"Song already exists in collection, skipping: {txt_path}")
                            continue

                        logger.info(f"Found .txt file in new directory: {txt_path}")

                        worker = RescanSingleSongWorker(song_path=txt_path)
                        self._worker_queue_add_task(worker)
                        self.song_added.emit(worker)

        except Exception as e:
            logger.error(f"Error scanning directory {directory}: {e}", exc_info=True)

    def _remove_songs_in_directory(self, directory: str):
        """Remove all songs cached under a directory."""
        try:
            # Get all cached entries (returns list of tuples when deserialize=False)
            from common.database import get_all_cache_entries

            cached_entries = get_all_cache_entries(deserialize=False)

            directory_norm = os.path.normpath(directory)

            for txt_path, _ in cached_entries:
                txt_norm = os.path.normpath(txt_path)

                # Check if song is under deleted directory
                if txt_norm.startswith(directory_norm):
                    logger.info(f"Removing song from deleted directory: {txt_path}")

                    try:
                        remove_cache_entry(txt_path)
                    except Exception as e:
                        logger.warning(f"Failed to remove cache entry for {txt_path}: {e}")

                    self.song_removed.emit(txt_path)

        except Exception as e:
            logger.error(f"Error removing songs in directory {directory}: {e}", exc_info=True)

    def _handle_directory_moved(self, src_dir: str, dest_dir: str):
        """Handle directory move/rename by updating all songs inside."""
        try:
            from common.database import get_all_cache_entries

            cached_entries = get_all_cache_entries(deserialize=False)

            src_norm = os.path.normpath(src_dir)
            dest_norm = os.path.normpath(dest_dir)

            for txt_path, _ in cached_entries:
                txt_norm = os.path.normpath(txt_path)

                # Check if song is under moved directory
                if txt_norm.startswith(src_norm):
                    # Calculate new path
                    relative = os.path.relpath(txt_norm, src_norm)
                    new_txt_path = os.path.join(dest_norm, relative)

                    logger.info(f"Updating moved song: {txt_path} -> {new_txt_path}")

                    # Remove old
                    try:
                        remove_cache_entry(txt_path)
                    except Exception as e:
                        logger.warning(f"Failed to remove old cache entry for {txt_path}: {e}")

                    self.song_removed.emit(txt_path)

                    # Check if song already exists at new location (prevents duplicates)
                    existing = self._songs_get_by_txt_file(new_txt_path)
                    if not existing:
                        # Rescan at new location
                        worker = RescanSingleSongWorker(song_path=new_txt_path)
                        self._worker_queue_add_task(worker)
                        self.song_added.emit(worker)
                    else:
                        logger.debug(f"Song already exists at new location, skipping rescan: {new_txt_path}")

                    self.song_moved.emit(txt_path, new_txt_path)

        except Exception as e:
            logger.error(f"Error handling directory move {src_dir} -> {dest_dir}: {e}", exc_info=True)
