"""
GapDetectionScheduler: Handles gap detection scheduling for Modified events.

Implements debouncing and coalescing to prevent task storms when files are
modified repeatedly in short succession.
"""

import logging
import os
from typing import Dict, Optional, Callable, Set
from dataclasses import dataclass
from datetime import datetime

from PySide6.QtCore import QObject, QTimer, Signal
from services.directory_watcher import WatchEvent, WatchEventType
from model.song import Song

logger = logging.getLogger(__name__)


@dataclass
class _PendingDetection:
    """Track a pending gap detection task"""
    song_path: str
    txt_file: str
    last_event_time: datetime
    timer: QTimer


class GapDetectionScheduler(QObject):
    """
    Schedules gap detection tasks with debouncing and coalescing.

    Prevents task storms by:
    - Debouncing: Wait for file modifications to stop before scheduling
    - Coalescing: Combine multiple events for the same song into one task
    - Idempotency: Track in-flight tasks to avoid duplicates

    Signals:
        detection_scheduled: Emitted when gap detection is scheduled (Song)
    """

    detection_scheduled = Signal(object)  # Song

    def __init__(
        self,
        debounce_ms: int,
        start_gap_detection: Callable,
        songs_get_by_txt_file: Callable,
        songs_get_by_path: Callable
    ):
        """
        Initialize GapDetectionScheduler.

        Args:
            debounce_ms: Milliseconds to wait after last event before scheduling
            start_gap_detection: Callable(song) to start gap detection
            songs_get_by_txt_file: Callable(txt_path) to get Song by txt file
            songs_get_by_path: Callable(path) to get Song by folder path
        """
        super().__init__()
        self._debounce_ms = debounce_ms
        self._start_gap_detection = start_gap_detection
        self._songs_get_by_txt_file = songs_get_by_txt_file
        self._songs_get_by_path = songs_get_by_path

        # Track pending detections by song folder path
        self._pending: Dict[str, _PendingDetection] = {}

        # Track in-flight detection tasks by song folder path
        self._in_flight: Set[str] = set()

        # Extensions that trigger gap detection
        self._trigger_extensions = {'.txt', '.mp3', '.wav', '.ogg', '.m4a', '.flac'}

    def handle_event(self, event: WatchEvent):
        """
        Handle a filesystem event and schedule gap detection if appropriate.

        Args:
            event: The filesystem event to handle
        """
        try:
            if event.event_type != WatchEventType.MODIFIED:
                return

            if event.is_directory:
                return

            # Check file extension
            _, ext = os.path.splitext(event.path)
            if ext.lower() not in self._trigger_extensions:
                return

            # Determine song folder and txt file
            song_path = os.path.dirname(event.path)

            # Find txt file in the folder
            txt_file = self._find_txt_file(song_path)
            if not txt_file:
                logger.debug(f"No .txt file found in {song_path}, skipping")
                return

            # Schedule detection with debouncing
            self._schedule_detection(song_path, txt_file)

        except Exception as e:
            logger.error(f"Error handling gap detection event: {e}", exc_info=True)

    def _find_txt_file(self, folder: str) -> Optional[str]:
        """Find .txt file in folder."""
        try:
            for filename in os.listdir(folder):
                if filename.lower().endswith('.txt'):
                    return os.path.join(folder, filename)
        except Exception as e:
            logger.debug(f"Error listing {folder}: {e}")

        return None

    def _schedule_detection(self, song_path: str, txt_file: str):
        """Schedule detection with debouncing."""
        now = datetime.now()

        # Check if already in-flight
        if song_path in self._in_flight:
            logger.debug(f"Gap detection already in-flight for {song_path}, skipping")
            return

        # Check if already pending
        if song_path in self._pending:
            pending = self._pending[song_path]

            # Update last event time
            pending.last_event_time = now

            # Restart timer
            pending.timer.stop()
            pending.timer.start(self._debounce_ms)

            logger.debug(f"Debouncing gap detection for {song_path}")

        else:
            # Create new pending detection
            timer = QTimer()
            timer.setSingleShot(True)
            timer.timeout.connect(lambda: self._execute_detection(song_path))

            pending = _PendingDetection(
                song_path=song_path,
                txt_file=txt_file,
                last_event_time=now,
                timer=timer
            )

            self._pending[song_path] = pending
            timer.start(self._debounce_ms)

            logger.debug(f"Scheduled gap detection for {song_path} (debounce {self._debounce_ms}ms)")

    def _execute_detection(self, song_path: str):
        """Execute gap detection after debounce period."""
        if song_path not in self._pending:
            return

        pending = self._pending[song_path]

        # Remove from pending
        del self._pending[song_path]

        # Mark as in-flight
        self._in_flight.add(song_path)

        try:
            # Get song object
            song = self._songs_get_by_txt_file(pending.txt_file)

            if not song:
                # Try by path
                song = self._songs_get_by_path(song_path)

            if not song:
                logger.warning(f"Song not found for gap detection: {song_path}")
                self._in_flight.discard(song_path)
                return

            logger.info(f"Starting gap detection for {song.artist} - {song.title}")

            # Start gap detection
            self._start_gap_detection(song)

            # Emit signal
            self.detection_scheduled.emit(song)

        except Exception as e:
            logger.error(f"Error executing gap detection for {song_path}: {e}", exc_info=True)
            self._in_flight.discard(song_path)

    def mark_detection_complete(self, song: Song):
        """
        Mark gap detection as complete for a song.

        Should be called when gap detection finishes (success or error).

        Args:
            song: The song that finished detection
        """
        if song and song.path:
            self._in_flight.discard(song.path)
            logger.debug(f"Gap detection completed for {song.path}")

    def clear_pending(self):
        """Clear all pending detections (used when stopping watch mode)."""
        for pending in self._pending.values():
            pending.timer.stop()

        self._pending.clear()
        logger.info("Cleared all pending gap detections")

    def clear_in_flight(self):
        """Clear in-flight tracking (use with caution)."""
        self._in_flight.clear()