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
from services.file_mutation_guard import FileMutationGuard
from services.song_signature_service import SongSignatureService
from model.gap_info import GapInfoStatus
from model.song import Song, SongStatus
from model.songs import normalize_path

logger = logging.getLogger(__name__)


@dataclass
class _PendingDetection:
    """Track a pending gap detection task"""

    song_path: str
    txt_file: str
    last_event_time: datetime
    timer: QTimer
    original_path: str
    retry_count: int = 0  # Track reschedule attempts


class GapDetectionScheduler(QObject):
    """
    Schedules gap detection tasks with debouncing and coalescing.

    Prevents task storms by:
    - Debouncing: Wait for file modifications to stop before scheduling
    - Coalescing: Combine multiple events for the same song into one task
    - Idempotency: Track in-flight tasks to avoid duplicates

    Signals:
        detection_scheduled: Emitted when gap detection is scheduled (Song)
        reload_requested: Emitted when song should be reloaded due to gap_info change (str: song_path)
    """

    detection_scheduled = Signal(object)  # Song
    reload_requested = Signal(str)  # song_path

    def __init__(
        self,
        debounce_ms: int,
        start_gap_detection: Callable,
        songs_get_by_txt_file: Callable,
        songs_get_by_path: Callable,
        cache_scheduler=None,
    ):
        """
        Initialize GapDetectionScheduler.

        Args:
            debounce_ms: Milliseconds to wait after last event before scheduling
            start_gap_detection: Callable(song) to start gap detection
            songs_get_by_txt_file: Callable(txt_path) to get Song by txt file
            songs_get_by_path: Callable(path) to get Song by folder path
            cache_scheduler: Optional CacheUpdateScheduler to check for recent creations
        """
        super().__init__()
        self._debounce_ms = debounce_ms
        self._start_gap_detection = start_gap_detection
        self._songs_get_by_txt_file = songs_get_by_txt_file
        self._songs_get_by_path = songs_get_by_path
        self._cache_scheduler = cache_scheduler

        # Track pending detections by song folder path
        self._pending: Dict[str, _PendingDetection] = {}

        # Track in-flight detection tasks by song folder path
        self._in_flight: Set[str] = set()

        # File extensions to watch for changes
        # - txt/audio files: reload song + conditionally trigger gap detection (if NOT_PROCESSED)
        # - .info files: reload song only (gap detection results)
        self._watched_extensions = {".txt", ".mp3", ".m4a", ".ogg", ".flac", ".wav", ".info"}

        # Maximum retry attempts when files aren't ready
        self._max_retries = 5

    @staticmethod
    def _normalize_song_path(song_path: str) -> str:
        return normalize_path(song_path) if song_path else ""

    def handle_event(self, event: WatchEvent):
        """
        Handle a filesystem event and schedule gap detection or reload if appropriate.

        Args:
            event: The filesystem event to handle
        """
        try:
            logger.debug(f"GapDetectionScheduler received event: {event.event_type.name} for {event.path}")

            # Only handle MODIFIED and DELETED events
            if event.event_type not in [WatchEventType.MODIFIED, WatchEventType.DELETED]:
                logger.debug(f"Ignoring event type {event.event_type.name}")
                return

            if event.is_directory:
                logger.debug("Ignoring directory event")
                return

            # Check file extension
            _, ext = os.path.splitext(event.path)
            logger.debug(f"File extension: {ext}")

            # Only process watched extensions
            if ext.lower() not in self._watched_extensions:
                logger.debug(f"Ignoring unwatched extension: {ext}")
                return

            # Handle .info files (MODIFIED or DELETED) → reload only
            if ext.lower() == ".info":
                logger.info(f"Detected gap_info file change: {event.event_type.name} {event.path}")
                self._handle_gap_info_change(event)
                return

            # Handle txt/audio files (MODIFIED only) → reload + conditional gap detection
            if event.event_type == WatchEventType.MODIFIED:
                logger.info(f"Detected song file modification: {event.path}")
                self._handle_file_modified(event)
                return

            logger.debug(f"No action for {ext} file with event {event.event_type.name}")

        except Exception as e:
            logger.error(f"Error handling gap detection event: {e}", exc_info=True)

    def _handle_file_modified(self, event: WatchEvent):
        """Handle txt/audio file modification → reload song + conditionally schedule gap detection."""
        # Ignore events triggered by in-app mutations (normalization, gap writes, etc.)
        if FileMutationGuard.is_guarded(event.path):
            logger.debug("Skipping guarded modification event for %s", event.path)
            return

        # Determine song folder and txt file
        song_path = os.path.dirname(event.path)
        txt_file = self._find_txt_file(song_path)

        if not txt_file:
            logger.warning(f"No txt file found in {song_path}, cannot process modification")
            return

        # Skip ONLY if the .txt file itself was recently created (prevents duplicate .txt processing)
        # Don't skip audio MODIFIED events - they need to trigger reload + detection
        event_path_normalized = normalize_path(event.path)
        txt_file_normalized = normalize_path(txt_file)

        if (event_path_normalized == txt_file_normalized and
            self._cache_scheduler and
            self._cache_scheduler.is_recently_created(txt_file)):
            logger.debug(f"Skipping MODIFIED event for recently created .txt file (normalized match): {txt_file_normalized}")
            return

        logger.info(
            "Text/audio file modified, reloading song at %s (event: %s)",
            song_path,
            os.path.basename(event.path),
        )

        # Emit reload signal to update song metadata from disk
        self.reload_requested.emit(song_path)

        # After reload signal is emitted, check if we should schedule gap detection
        # Get the song to check its status
        song = self._songs_get_by_txt_file(txt_file)
        if not song:
            song = self._songs_get_by_path(song_path)

        if not song:
            logger.debug(f"Song not found for {song_path}, will schedule detection for when it's added")
            # Schedule detection anyway - song will be added/reloaded
            self._schedule_detection(song_path, txt_file)
            return

        # Always honor existing NOT_PROCESSED state (legacy behavior)
        if song.status == SongStatus.NOT_PROCESSED:
            logger.info(
                "Song already marked NOT_PROCESSED, scheduling gap detection for %s - %s",
                song.artist,
                song.title,
            )
            self._schedule_detection(song_path, txt_file)
            return

        # For processed songs, compare signatures to detect real content changes
        if SongSignatureService.has_meaningful_change(song, event.path):
            logger.info(
                "Detected content change for %s - %s (%s), resetting status",
                song.artist,
                song.title,
                os.path.basename(event.path),
            )
            self._mark_song_as_stale(song)
            self._schedule_detection(song_path, txt_file)
        else:
            logger.debug(
                "Skipped gap detection for %s - %s: signature unchanged",
                song.artist,
                song.title,
            )

    def _mark_song_as_stale(self, song: Song):
        """Reset song + gap info status to NOT_PROCESSED when content changed."""
        if not song:
            return

        try:
            if song.gap_info and song.gap_info.status != GapInfoStatus.NOT_PROCESSED:
                song.gap_info.error_message = None
                song.gap_info.status = GapInfoStatus.NOT_PROCESSED
            elif not song.gap_info:
                song.status = SongStatus.NOT_PROCESSED

            song.error_message = None
        except Exception as exc:
            logger.debug("Failed to mark %s as stale: %s", song.path, exc)

    def _handle_gap_info_change(self, event: WatchEvent):
        """Handle usdxfixgap.info modification/deletion → trigger song reload."""
        song_path = os.path.dirname(event.path)

        logger.info(f"Gap info file changed: {event.path}, requesting reload for {song_path}")

        # Emit signal to trigger song reload
        self.reload_requested.emit(song_path)

    def _find_txt_file(self, folder: str) -> Optional[str]:
        """Find .txt file in folder."""
        try:
            for filename in os.listdir(folder):
                if filename.lower().endswith(".txt"):
                    return os.path.join(folder, filename)
        except Exception as e:
            logger.debug(f"Error listing {folder}: {e}")

        return None

    def _validate_song_files_ready(self, song: Song) -> tuple[bool, str]:
        """
        Validate that song has both txt and audio files that are ready.

        Args:
            song: The song to validate

        Returns:
            Tuple of (is_ready, reason)
        """
        # Check if txt file exists
        if not song.txt_file or not os.path.exists(song.txt_file):
            return False, "txt file missing"

        # Check if audio file exists
        if not song.audio_file:
            return False, "no audio file found"

        if not os.path.exists(song.audio_file):
            return False, "audio file missing"

        # Check if audio file is stable (not currently being written)
        # Try to open it to ensure it's accessible and not locked
        try:
            # Check if file is readable
            with open(song.audio_file, "rb") as f:
                # Try to read first byte to ensure file is not locked
                f.read(1)

            # File seems ready
            return True, "ready"

        except (OSError, IOError) as e:
            return False, f"audio file not ready: {e}"

    def _cancel_pending_detection(self, song_path: str):
        """Cancel any pending detection timers for the given song path."""
        normalized_path = self._normalize_song_path(song_path)
        pending = self._pending.pop(normalized_path, None)
        if pending:
            pending.timer.stop()
            logger.debug("Cancelled pending gap detection for %s", song_path)

    def _schedule_detection(self, song_path: str, txt_file: str):
        """Schedule detection with debouncing."""
        now = datetime.now()
        normalized_path = self._normalize_song_path(song_path)

        # Check if already in-flight
        if normalized_path in self._in_flight:
            logger.debug(f"Gap detection already in-flight for {song_path}, skipping")
            return

        # Check if already pending
        if normalized_path in self._pending:
            pending = self._pending[normalized_path]

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
            timer.timeout.connect(lambda path=normalized_path: self._execute_detection(path))

            pending = _PendingDetection(
                song_path=normalized_path,
                txt_file=txt_file,
                last_event_time=now,
                timer=timer,
                original_path=song_path,
            )

            self._pending[normalized_path] = pending
            timer.start(self._debounce_ms)

            logger.debug(f"Scheduled gap detection for {song_path} (debounce {self._debounce_ms}ms)")

    def _schedule_detection_with_retry(self, song_path: str, txt_file: str, retry_count: int):
        """Schedule detection with specific retry count (used for rescheduling)."""
        normalized_path = self._normalize_song_path(song_path)
        # Check if already in-flight
        if normalized_path in self._in_flight:
            logger.debug(f"Gap detection already in-flight for {song_path}, skipping reschedule")
            return

        # Cancel existing pending if any
        self._cancel_pending_detection(song_path)

        # Create new pending detection with retry count
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(lambda path=normalized_path: self._execute_detection(path))

        pending = _PendingDetection(
            song_path=normalized_path,
            txt_file=txt_file,
            last_event_time=datetime.now(),
            timer=timer,
            original_path=song_path,
            retry_count=retry_count,
        )

        self._pending[normalized_path] = pending
        timer.start(self._debounce_ms)

        logger.debug(f"Rescheduled gap detection for {song_path} (retry {retry_count}, debounce {self._debounce_ms}ms)")

    def start_detection_immediately(self, song: Song) -> bool:
        """Start gap detection immediately for the provided song."""
        if not song or not song.path:
            logger.debug("Cannot start immediate detection: invalid song reference")
            return False

        song_path = song.path
        normalized_path = self._normalize_song_path(song_path)
        self._cancel_pending_detection(song_path)

        if normalized_path in self._in_flight:
            logger.debug("Gap detection already in-flight for %s, skipping immediate start", song_path)
            return False

        self._in_flight.add(normalized_path)

        try:
            self._start_gap_detection(song)
            self.detection_scheduled.emit(song)
            return True
        except Exception:
            self._in_flight.discard(normalized_path)
            raise

    def _execute_detection(self, song_path: str):
        """Execute gap detection after debounce period."""
        if song_path not in self._pending:
            return

        pending = self._pending[song_path]
        actual_song_path = pending.original_path or pending.song_path

        # Remove from pending
        del self._pending[song_path]

        # Mark as in-flight
        if song_path in self._in_flight:
            logger.debug("Gap detection already in-flight for %s, skipping queued execution", actual_song_path)
            return

        self._in_flight.add(song_path)

        try:
            # Get song object
            song = self._songs_get_by_txt_file(pending.txt_file)

            if not song:
                # Try by path
                song = self._songs_get_by_path(actual_song_path)

            if not song:
                if pending.retry_count >= self._max_retries:
                    logger.warning(
                        "Song not found for gap detection after %s retries: %s",
                        pending.retry_count,
                        actual_song_path,
                    )
                    self._in_flight.discard(song_path)
                    return

                logger.info(
                    "Song not ready in collection for %s, rescheduling gap detection (retry %s/%s)",
                    actual_song_path,
                    pending.retry_count + 1,
                    self._max_retries,
                )
                self._in_flight.discard(song_path)
                self._schedule_detection_with_retry(actual_song_path, pending.txt_file, pending.retry_count + 1)
                return

            # Skip songs with ERROR status (failed to load)
            if song.status and song.status.name == "ERROR":
                logger.warning(f"Skipping gap detection for song with ERROR status: {actual_song_path}")
                self._in_flight.discard(song_path)
                return

            # Validate that both txt and audio files exist and are ready
            is_ready, reason = self._validate_song_files_ready(song)
            if not is_ready:
                # Check retry limit
                if pending.retry_count >= self._max_retries:
                    logger.error(
                        f"Giving up on gap detection for {song.artist} - {song.title} after "
                        f"{pending.retry_count} retries: {reason}"
                    )
                    self._in_flight.discard(song_path)
                    return

                logger.info(
                    f"Song files not ready for {song.artist} - {song.title}: {reason}, "
                    f"rescheduling (retry {pending.retry_count + 1}/{self._max_retries})..."
                )
                self._in_flight.discard(song_path)

                # Reschedule with incremented retry count
                # This handles the race condition where txt is detected before audio is fully written
                self._schedule_detection_with_retry(actual_song_path, pending.txt_file, pending.retry_count + 1)
                return

            logger.info(f"Starting gap detection for {song.artist} - {song.title}")

            # Start gap detection
            self._start_gap_detection(song)

            # Emit signal
            self.detection_scheduled.emit(song)

        except Exception as e:
            logger.error(f"Error executing gap detection for {actual_song_path}: {e}", exc_info=True)
            self._in_flight.discard(song_path)

    def mark_detection_complete(self, song: Song):
        """
        Mark gap detection as complete for a song.

        Should be called when gap detection finishes (success or error).

        Args:
            song: The song that finished detection
        """
        if song and song.path:
            normalized_path = self._normalize_song_path(song.path)
            self._in_flight.discard(normalized_path)
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
