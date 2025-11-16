import logging
import os
import threading
from actions.base_actions import BaseActions
from actions.song_actions import SongActions
from model.song import Song, SongStatus
from services.waveform_path_service import WaveformPathService
from workers.detect_audio_length import DetectAudioLengthWorker
from workers.normalize_audio import NormalizeAudioWorker
from workers.create_waveform import CreateWaveform
from utils.waveform import create_waveform_image, draw_silence_periods, draw_notes

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

    def _normalize_song(self, song: Song, start_now=False):
        worker = NormalizeAudioWorker(song)
        worker.signals.started.connect(lambda: self._on_song_worker_started(song))
        worker.signals.error.connect(lambda e: self._on_song_worker_error(song, e))
        worker.signals.finished.connect(lambda: self._on_song_worker_finished(song))

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

        # Defer adding the task to allow QMediaPlayer to fully release file handles on Windows
        try:
            from PySide6.QtCore import QTimer

            # Increase delay to 800 ms to ensure QMediaPlayer has released file handles
            # on all systems including network drives
            QTimer.singleShot(800, lambda: self.worker_queue.add_task(worker, start_now))
        except Exception:
            # If QTimer unavailable, fallback to immediate add
            self.worker_queue.add_task(worker, start_now)

    def _schedule_deferred_reload(self, song: Song):
        """Schedule a deferred reload to prevent UI thread blocking."""
        from PySide6.QtCore import QTimer

        # Defer reload by 100ms to allow UI to update first
        # This prevents cascading reloads from blocking the UI
        QTimer.singleShot(100, lambda: self.song_actions.reload_song(specific_song=song))

    def _create_waveforms(self, song: Song, overwrite: bool = False, use_queue: bool = True):
        """Create waveforms for both audio and vocals tracks.

        Args:
            song: The song object
            overwrite: Whether to overwrite existing waveforms
            use_queue: If True, uses WorkerQueueManager (for batch operations).
                      If False, runs in background threads without queueing (for single-song selection).
        """
        if not song:
            raise Exception("No song given")

        # Check if audio file exists
        if not hasattr(song, "audio_file") or not song.audio_file:
            title = song.title if hasattr(song, "title") else "Unknown"
            logger.warning(f"Cannot create waveforms for '{title}': Missing audio file")
            # Don't trigger reload - missing audio file is a data issue, not a loading issue
            return

        # Notes will be loaded asynchronously by reload_song_light if needed.
        # Don't block waveform creation waiting for notes - waveforms can be drawn without note overlays.
        # If notes are missing, they'll be added later after async reload completes.

        # Use the WaveformPathService to get all paths
        paths = WaveformPathService.get_paths(song, self.data.tmp_path)
        if not paths:
            logger.error(
                f"Could not get waveform paths for song: {song.title if hasattr(song, 'title') else 'Unknown'}"
            )
            return

        self._create_waveform(song, paths["audio_file"], paths["audio_waveform_file"], overwrite, use_queue)
        self._create_waveform(song, paths["vocals_file"], paths["vocals_waveform_file"], overwrite, use_queue)

    def _create_waveform(
        self, song: Song, audio_file: str, waveform_file: str, overwrite: bool = False, use_queue: bool = True
    ):
        """Create a waveform image for the given audio file.

        Args:
            song: The song object
            audio_file: Path to the audio file
            waveform_file: Path where the waveform image will be saved
            overwrite: Whether to overwrite existing waveform
            use_queue: If True, uses WorkerQueueManager (for batch operations).
                      If False, runs in background thread without queueing (for single-song selection).
        """
        if not os.path.exists(audio_file):
            logger.warning(f"Audio file does not exist: {audio_file}")
            return

        if os.path.exists(waveform_file) and not overwrite:
            logger.info(f"Waveform file already exists and overwrite is False: {waveform_file}")
            return

        if use_queue:
            # Original behavior: queue worker for batch operations
            logger.debug(f"Creating waveform creation task (queued) for {song}")
            worker = CreateWaveform(
                song,
                self.config,
                audio_file,
                waveform_file,
                is_instant=True,  # Mark as instant task - runs in parallel with standard tasks
            )
            worker.signals.error.connect(lambda e: self._on_song_worker_error(song, e))
            worker.signals.finished.connect(lambda song=song: self.data.songs.updated.emit(song))
            self.worker_queue.add_task(worker, True)  # start_now=True for instant tasks
        else:
            # New behavior: run in background thread without queueing (for selected song only)
            logger.debug(f"Creating waveform directly (non-queued) for {song}")

            def create_waveform_direct():
                """Background thread function to create waveform without WorkerQueueManager."""
                try:
                    # Generate the waveform image directly
                    waveform_color = self.config.waveform_color if hasattr(self.config, "waveform_color") else "gray"
                    create_waveform_image(audio_file, waveform_file, waveform_color)

                    # Apply overlays if gap_info is available
                    if hasattr(song, "gap_info") and song.gap_info:
                        # Draw silence periods
                        if hasattr(song.gap_info, "silence_periods") and song.gap_info.silence_periods:
                            silence_color = (
                                self.config.silence_periods_color
                                if hasattr(self.config, "silence_periods_color")
                                else (105, 105, 105, 128)
                            )
                            draw_silence_periods(
                                waveform_file, song.gap_info.silence_periods, song.duration_ms, silence_color
                            )

                    # Draw notes overlay
                    if hasattr(song, "notes") and song.notes:
                        note_color = "white"  # Standard note color
                        draw_notes(waveform_file, song.notes, song.duration_ms, note_color)

                    logger.debug(f"Waveform created successfully (non-queued): {waveform_file}")

                    # Emit update signal (thread-safe)
                    self.data.songs.updated.emit(song)

                except Exception as e:
                    logger.error(f"Error creating waveform (non-queued) for {song}: {e}", exc_info=True)

            # Start background thread
            thread = threading.Thread(target=create_waveform_direct, daemon=True)
            thread.start()
