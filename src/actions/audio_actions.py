import logging
from typing import Callable, Optional

from actions.base_actions import BaseActions
from actions.song_actions import SongActions
from model.song import Song, SongStatus
from workers.detect_audio_length import DetectAudioLengthWorker
from workers.normalize_audio import NormalizeAudioWorker

logger = logging.getLogger(__name__)


class AudioActions(BaseActions):
    """Audio processing actions like normalization and waveform generation"""

    def __init__(self, data):
        super().__init__(data)
        self.song_actions = SongActions(data)

    def _get_audio_length(self, song: Song):
        worker = DetectAudioLengthWorker(song)
        worker.signals.lengthDetected.connect(lambda song: self.data.songs.updated.emit(song))
        worker.signals.error.connect(lambda e: self._on_song_worker_error(song, e))
        self.worker_queue.add_task(worker, True)

    def normalize_song(self):
        selected_songs = self.data.selected_songs
        if not selected_songs:
            logger.error("No songs selected for normalization.")
            return

        logger.info(f"Queueing normalization for {len(selected_songs)} songs.")

        # Use async queuing to prevent UI freeze
        # self._queue_tasks_non_blocking(selected_songs, self._normalize_song_if_valid)

        if len(selected_songs) == 1:
            # If only one song is selected, normalize it immediately
            self._normalize_song_if_valid(selected_songs[0], True)
        else:
            for song in selected_songs:
                self._normalize_song_if_valid(song, False)

    def _normalize_song_if_valid(self, song, is_first):
        if song.audio_file:
            self._normalize_song(song, is_first)
        else:
            logger.warning(f"Skipping normalization for {song}: No audio file.")

    def _normalize_song(self, song: Song, start_now=False, auto_normalize_chain=False):
        worker = NormalizeAudioWorker(song)
        # Early-bind song using default args to avoid late-binding closure bugs
        worker.signals.started.connect(lambda s=song: self._on_song_worker_started(s))
        worker.signals.error.connect(lambda e, s=song: self._on_song_worker_error(s, e))
        worker.signals.finished.connect(lambda s=song: self._on_song_worker_finished(s))

        # Defer reload only on success; skip when status is ERROR to preserve the error display
        def _reload_if_success():
            try:
                if getattr(song, "status", None) != SongStatus.ERROR:
                    self._schedule_deferred_reload(song)
                else:
                    logger.debug(f"Skipping reload due to error status for song: {song}")
            except Exception as e:
                # Log exceptions for debugging
                logger.debug(f"Exception in reload guard for {song}: {e}", exc_info=True)

        worker.signals.finished.connect(_reload_if_success)

        self._hold_lane_for_worker(worker, f"normalize:{song.path}")

        # Lock audio file to prevent UI from reloading it or instant tasks from accessing it during normalization
        try:
            if hasattr(song, "audio_file") and song.audio_file:
                self.data.lock_file(song.audio_file)
        except Exception:
            pass

        # Ensure locks are cleared when the worker finishes or errors
        try:
            worker.signals.finished.connect(lambda: self.data.clear_file_locks_for_song(song))
            worker.signals.error.connect(lambda e: self.data.clear_file_locks_for_song(song))
        except Exception:
            pass

        # Request media unload to prevent Windows file locks from QMediaPlayer during os.replace().
        if hasattr(self.data, "media_unload_requested"):
            try:
                self.data.media_unload_requested.emit()
            except Exception:
                # If signal wiring fails, proceed without emit
                pass

        song.status = SongStatus.QUEUED
        self.data.songs.updated.emit(song)

        # Auto-normalize chains (called from gap detection finish) should start immediately
        # without delay to ensure per-song chaining, not batch processing
        if auto_normalize_chain:
            # Skip the 800ms delay for auto-normalize chains - media is already unloaded
            # from gap detection, and we want immediate chaining per song
            self.worker_queue.add_task(worker, start_now=True, priority=True)
            logger.debug(f"Auto-normalize chained immediately (no delay) for {song.path}")
        else:
            # Manual normalization needs delay to allow QMediaPlayer to fully release file handles
            try:
                from PySide6.QtCore import QTimer

                # Increase delay to 800 ms to ensure QMediaPlayer has released file handles
                # on all systems including network drives
                # Use priority=True when start_now is True to ensure it runs after current task
                QTimer.singleShot(800, lambda: self.worker_queue.add_task(worker, start_now, priority=start_now))
            except Exception:
                # If QTimer unavailable, fallback to immediate add
                self.worker_queue.add_task(worker, start_now)

    def _schedule_deferred_reload(self, song: Song):
        """Schedule a deferred reload to prevent UI thread blocking."""
        from PySide6.QtCore import QTimer

        # Defer reload by 100ms to allow UI to update first
        # This prevents cascading reloads from blocking the UI
        QTimer.singleShot(100, lambda: self.song_actions.reload_song(specific_song=song))

    def _create_waveforms(
        self,
        song: Song,
        overwrite: bool = False,
        use_queue: bool = True,
        emit_on_finish: bool = True,
        finished_callback: Optional[Callable[[Song], None]] = None,
    ):
        if song is None:
            raise Exception("No song given")
        manager = getattr(self.data, "waveform_manager", None)
        if not manager:
            logger.warning("WaveformManager is not initialized; skipping waveform queue request")
            return
        manager.ensure_waveforms(
            song,
            overwrite=overwrite,
            use_queue=use_queue,
            emit_on_finish=emit_on_finish,
            finished_callback=finished_callback,
            requester="audio-actions",
        )
