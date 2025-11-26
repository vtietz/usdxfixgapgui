import logging
import itertools
from contextlib import contextmanager
from PySide6.QtCore import QObject, QTimer
from typing import List, Callable, Optional
from app.app_data import AppData
from model.song import Song

logger = logging.getLogger(__name__)


class BaseActions(QObject):
    """Base class for all action modules"""

    _lane_hold_counter = itertools.count(1)

    def __init__(self, data: AppData):
        """
        Initialize with application data

        Args:
            data: Application data instance
        """
        super().__init__()
        self.data = data
        self.config = data.config
        self.worker_queue = data.worker_queue  # Use the shared worker queue from AppData
        self._lane_hold_prefix = self.__class__.__name__

    # TODO: currently not sure if this is helpful
    def _queue_tasks_non_blocking(self, songs: List[Song], callback: Callable):
        """Queue tasks with a small delay between them to avoid UI freeze"""
        if not songs:
            return

        # Create a copy of the songs list to avoid modification issues
        songs_to_process = list(songs)

        # Process the first song immediately
        first_song = songs_to_process.pop(0)
        callback(first_song, True)  # True = is first song

        # If there are more songs, queue them with a small delay
        if songs_to_process:
            QTimer.singleShot(100, lambda: self._process_next_song(songs_to_process, callback))

    def _process_next_song(self, remaining_songs: List[Song], callback: Callable):
        """Process the next song in the queue with a delay"""
        if not remaining_songs:
            return

        # Process the next song
        next_song = remaining_songs.pop(0)
        callback(next_song, False)  # False = not first song

        # If there are more songs, queue the next one with a delay
        if remaining_songs:
            QTimer.singleShot(50, lambda: self._process_next_song(remaining_songs, callback))

    # ------------------------------------------------------------------
    # Worker queue standard-lane coordination helpers
    # ------------------------------------------------------------------

    def _acquire_lane_hold(self, reason: Optional[str] = None) -> Optional[str]:
        queue = getattr(self, "worker_queue", None)
        if not queue or not hasattr(queue, "hold_standard_lane"):
            return None
        token = f"{self._lane_hold_prefix}:{reason or 'lane-hold'}#{next(BaseActions._lane_hold_counter)}"
        try:
            queue.hold_standard_lane(token)
            return token
        except Exception:
            logger.debug("Failed to acquire lane hold", exc_info=True)
            return None

    def _release_lane_hold(self, token: Optional[str]):
        if not token:
            return
        queue = getattr(self, "worker_queue", None)
        if not queue or not hasattr(queue, "release_standard_lane"):
            return
        try:
            queue.release_standard_lane(token)
        except Exception:
            logger.debug("Failed to release lane hold", exc_info=True)

    @contextmanager
    def _lane_hold(self, reason: str):
        token = self._acquire_lane_hold(reason)
        try:
            yield token
        finally:
            self._release_lane_hold(token)

    def _hold_lane_for_worker(self, worker, reason: str):
        token = self._acquire_lane_hold(reason)
        if not token:
            return
        released = {"done": False}

        def release_once(*_args, **_kwargs):
            if released["done"]:
                return
            released["done"] = True
            self._release_lane_hold(token)

        try:
            worker.signals.finished.connect(release_once)
            worker.signals.error.connect(release_once)
            worker.signals.canceled.connect(release_once)
        except Exception:
            logger.debug("Failed to attach lane hold release hooks", exc_info=True)
            release_once()

    def _on_song_worker_started(self, song: Song):
        from model.song import SongStatus

        song.status = SongStatus.PROCESSING
        self.data.songs.updated.emit(song)

    def _on_song_worker_error(self, song: Song, error: Exception = None):
        """Handle worker error - use set_error for non-gap errors"""
        error_msg = str(error) if error else "Unknown error occurred"
        song.set_error(error_msg)
        self.data.songs.updated.emit(song)

    def _on_song_worker_finished(self, song: Song):
        """Default finish handler: restore status from gap_info and emit update.

        This prevents status from staying stuck in PROCESSING after background
        operations (normalization, waveform creation, etc.) that don't change
        the detection result.

        Workers that modify gap_info (gap detection) should NOT use this handler
        as they set their own status.
        """
        self._restore_status_from_gap_info(song)
        self.data.songs.updated.emit(song)

    def _restore_status_from_gap_info(self, song: Song):
        """Restore song status from gap_info after background operation.

        This method is called after workers finish to prevent status from
        staying stuck in PROCESSING when the worker didn't change the
        detection result.

        Args:
            song: The song to restore status for
        """
        try:
            from model.song import SongStatus

            # Skip restoration if song is in ERROR state
            # (error handler already set it)
            if getattr(song, "status", None) == SongStatus.ERROR:
                logger.debug(f"Skipping status restoration for {song}: status is ERROR")
                return

            # Restore status based on gap_info
            if hasattr(song, "gap_info") and song.gap_info:
                # Trigger owner mapping by re-assigning the current GapInfo
                # status. This forces the GapInfo.status.setter to call
                # song._gap_info_updated() which maps GapInfo.status to
                # Song.status
                current_status = song.gap_info.status
                song.gap_info.status = current_status
                logger.debug(f"Restored status for {song} from gap_info: " f"{current_status}")
            else:
                # No gap_info available, reset to NOT_PROCESSED
                song.status = SongStatus.NOT_PROCESSED
                logger.debug(f"Reset status for {song} to NOT_PROCESSED (no gap_info)")

        except Exception as e:
            # Log but don't crash; status will stay as-is
            logger.warning(f"Failed to restore status for {song}: {e}", exc_info=True)
