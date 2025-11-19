import os
import logging
from PySide6.QtCore import QObject, Signal

from ui.mediaplayer.constants import AudioFileStatus
from services.media import create_backend, MediaStatus, PlaybackState

logger = logging.getLogger(__name__)

# torchaudio not needed for playback anymore - VLC/Qt handles validation
TORCHAUDIO_AVAILABLE = False


class PlayerController(QObject):
    position_changed = Signal(int)
    is_playing_changed = Signal(bool)
    audio_file_status_changed = Signal(AudioFileStatus)
    media_status_changed = Signal(bool)
    vocals_validation_failed = Signal()

    def __init__(self, config):
        super().__init__()
        self._config = config
        self._audioFileStatus = AudioFileStatus.AUDIO
        self._media_is_loaded = False
        self._is_playing = False
        self._original_audio_duration_ms = 0  # For vocals mode position mapping

        # Create separate backends for audio and vocals
        # This allows instant mode switching without reloading media
        logger.info("Creating dual media backends (audio + vocals)")

        # Audio backend (VLC on Windows, Qt elsewhere)
        self.audio_backend = create_backend()
        self.audio_backend.set_volume(50)

        # Vocals backend (VLC on Windows, Qt elsewhere)
        self.vocals_backend = create_backend()
        self.vocals_backend.set_volume(50)

        # Log the active backend type
        backend_type = type(self.audio_backend).__name__
        logger.info(f"Media backend: {backend_type}")

        # Connect signals for both backends (sender-anchored)
        self.audio_backend.playback_state_changed.connect(
            lambda state: self._on_playback_state_changed(self.audio_backend, state)
        )
        self.audio_backend.media_status_changed.connect(
            lambda status: self._on_media_status_changed(self.audio_backend, status)
        )
        self.audio_backend.error_occurred.connect(lambda error_msg: self._on_media_error(self.audio_backend, error_msg))
        self.audio_backend.position_changed.connect(
            lambda position: self._on_position_changed(self.audio_backend, position)
        )

        self.vocals_backend.playback_state_changed.connect(
            lambda state: self._on_playback_state_changed(self.vocals_backend, state)
        )
        self.vocals_backend.media_status_changed.connect(
            lambda status: self._on_media_status_changed(self.vocals_backend, status)
        )
        self.vocals_backend.error_occurred.connect(
            lambda error_msg: self._on_media_error(self.vocals_backend, error_msg)
        )
        self.vocals_backend.position_changed.connect(
            lambda position: self._on_position_changed(self.vocals_backend, position)
        )

        # Per-backend state maps
        self._is_loaded_map = {self.audio_backend: False, self.vocals_backend: False}
        self._is_playing_map = {self.audio_backend: False, self.vocals_backend: False}

        logger.info("Dual media backends created successfully")

    @property
    def media_backend(self):
        """Get the currently active media backend based on mode"""
        return self.audio_backend if self._audioFileStatus == AudioFileStatus.AUDIO else self.vocals_backend

    def play(self):
        """Toggle play/pause - uses active backend based on mode"""
        logger.debug("play() called")

        # Stop the inactive backend first
        inactive_backend = self.vocals_backend if self._audioFileStatus == AudioFileStatus.AUDIO else self.audio_backend
        if inactive_backend.is_playing():
            logger.debug("Stopping inactive backend")
            inactive_backend.stop()

        # Now control the active backend
        active_backend = self.media_backend
        logger.debug("Active backend: %s", type(active_backend).__name__)

        # Query backend's actual state for reliable toggle
        backend_is_playing = active_backend.is_playing()
        is_loaded = active_backend.is_loaded()
        current_file = active_backend.get_current_file()
        logger.debug(
            "Backend is_loaded: %s, is_playing: %s, has_file: %s, Controller _is_playing: %s",
            is_loaded,
            backend_is_playing,
            current_file is not None,
            self._is_playing,
        )

        # If playing, always allow pause (even if backend reports not loaded - Qt bug)
        if backend_is_playing:
            logger.debug("Calling backend.pause() (currently playing)")
            active_backend.pause()
            return

        # Check if we have media to play (use current_file as fallback for buggy is_loaded)
        if not is_loaded and current_file is None:
            logger.warning(
                "Play ignored: no media loaded (is_loaded=%s, has_file=%s)", is_loaded, current_file is not None
            )
            return

        # Start playback
        logger.debug("Calling backend.play() (currently stopped/paused)")
        active_backend.play()

    def stop(self):
        """Stop both backends"""
        self.audio_backend.stop()
        self.vocals_backend.stop()

    def audio_mode(self):
        """Switch to audio mode"""
        # Save current position and playing state from vocals backend
        was_playing = self.vocals_backend.is_playing()
        current_pos = self.vocals_backend.get_position() if self.vocals_backend.is_loaded() else 0

        # Stop vocals backend
        if was_playing:
            self.vocals_backend.stop()

        self._audioFileStatus = AudioFileStatus.AUDIO
        self.audio_file_status_changed.emit(self._audioFileStatus)

        # Restore position in audio backend (seek will trigger playhead update)
        if current_pos > 0 and self.audio_backend.is_loaded():
            self.audio_backend.seek(current_pos)
            self.position_changed.emit(current_pos)

        # Resume playing if we were playing before
        if was_playing and self.audio_backend.is_loaded():
            self.audio_backend.play()

    def vocals_mode(self):
        """Switch to vocals mode"""
        # Save current position and playing state from audio backend
        was_playing = self.audio_backend.is_playing()
        current_pos = self.audio_backend.get_position() if self.audio_backend.is_loaded() else 0

        # Stop audio backend
        if was_playing:
            self.audio_backend.stop()

        self._audioFileStatus = AudioFileStatus.VOCALS
        self.audio_file_status_changed.emit(self._audioFileStatus)

        # Restore position in vocals backend (clamp to vocals duration)
        if current_pos > 0 and self.vocals_backend.is_loaded():
            vocals_duration = self.vocals_backend.get_duration()
            # Clamp position to vocals duration (vocals may be shorter)
            seek_pos = min(current_pos, vocals_duration) if vocals_duration > 0 else current_pos
            self.vocals_backend.seek(seek_pos)
            self.position_changed.emit(seek_pos)

        # Resume playing if we were playing before
        if was_playing and self.vocals_backend.is_loaded():
            self.vocals_backend.play()

    def load_media(self, file: str | None):
        """Load a media file into the active backend (audio or vocals)"""
        active_backend = self.media_backend  # Property returns correct backend based on mode

        if not file:
            logger.debug(f"No media file to load for {self._audioFileStatus} backend")
            active_backend.unload()
            return

        logger.debug(f"Loading {self._audioFileStatus} media: {file}")

        # Check if already loaded
        if active_backend.get_current_file() == file:
            logger.debug(f"Media source unchanged for {self._audioFileStatus} backend - not reloading")
            return

        # Pre-validate the media file before loading
        if not self._validate_media_file(file):
            logger.error(f"Media file validation failed: {file}")
            if self._audioFileStatus == AudioFileStatus.VOCALS:
                logger.info("Switching to audio mode due to invalid vocals file")
                self.vocals_validation_failed.emit()
                self.audio_mode()
            return

        logger.debug(f"Setting new media source for {self._audioFileStatus} backend: {file}")
        active_backend.stop()
        active_backend.load(file)

    def _validate_media_file(self, file: str) -> bool:
        """Validate media file before loading to prevent QMediaPlayer freezes

        Args:
            file: Path to media file

        Returns:
            True if file is valid and can be loaded safely, False otherwise
        """
        if not os.path.exists(file):
            logger.warning(f"Media file does not exist: {file}")
            return False

        # Check file size - reject empty files
        file_size = os.path.getsize(file)
        if file_size == 0:
            logger.warning(f"Media file is empty: {file}")
            return False

        # For vocals files (MP3), use torchaudio to validate IF available
        if "vocals" in file.lower() and file.lower().endswith(".mp3"):
            # SKIP torchaudio validation to avoid UI freeze
            # QMediaPlayer will validate when loading, and we handle errors there
            logger.debug(f"Skipping torchaudio validation for vocals file (prevent UI freeze): {file}")
            return True  # Let QMediaPlayer validate during load

        # For other files (audio.mp3), basic validation only
        logger.debug(f"Basic validation passed for {file}")
        return True

    def unload_all_media(self):
        """Unload media from both backends"""
        logger.debug("Unloading all media from both backends")
        self.audio_backend.stop()
        self.audio_backend.unload()
        self.vocals_backend.stop()
        self.vocals_backend.unload()

    def adjust_position_left(self):
        """Move playback position backwards"""
        if self._audioFileStatus == AudioFileStatus.AUDIO:
            ms = self._config.adjust_player_position_step_audio
        else:
            ms = self._config.adjust_player_position_step_vocals
        newPosition = max(0, self.media_backend.get_position() - ms)
        self.media_backend.seek(newPosition)

    def adjust_position_right(self):
        """Move playback position forwards"""
        if self._audioFileStatus == AudioFileStatus.AUDIO:
            ms = self._config.adjust_player_position_step_audio
        else:
            ms = self._config.adjust_player_position_step_vocals
        newPosition = max(0, self.media_backend.get_position() + ms)
        self.media_backend.seek(newPosition)

    def set_position(self, relative_position, duration_ms=None):
        """Set position as a percentage of media duration.

        Args:
            relative_position: Position as 0.0-1.0 ratio
            duration_ms: Optional accurate duration in ms (from ffprobe). If not provided,
                        will use backend duration which may be inaccurate for some MP3s.
        """
        # Use provided duration or fallback to backend duration
        backend_duration = self.media_backend.get_duration()
        duration = duration_ms if duration_ms is not None else backend_duration
        if duration <= 0:
            logger.warning(f"Cannot seek - duration is {duration}ms")
            return

        new_position = int(relative_position * duration)
        logger.debug(
            f"Click seek: relative={relative_position:.3f}, provided_duration={duration_ms}ms, "
            f"backend_duration={backend_duration}ms, using={duration}ms, "
            f"seeking to {new_position}ms, mode={self._audioFileStatus.name}"
        )
        self.media_backend.seek(new_position)
        self.position_changed.emit(new_position)

    def get_position(self):
        """Get current position in milliseconds"""
        return self.media_backend.get_position()

    def get_duration(self):
        """Get media duration in milliseconds"""
        return self.media_backend.get_duration()

    def get_audio_status(self):
        """Get current audio status (AUDIO or VOCALS)"""
        return self._audioFileStatus

    def is_media_loaded(self):
        """Check if media is loaded"""
        return self._media_is_loaded

    def is_playing(self):
        """Check if media is currently playing"""
        return self._is_playing

    def _is_active_backend(self, backend) -> bool:
        """Check if given backend is the currently active backend based on mode"""
        return (self._audioFileStatus == AudioFileStatus.AUDIO and backend is self.audio_backend) or (
            self._audioFileStatus == AudioFileStatus.VOCALS and backend is self.vocals_backend
        )

    def _on_playback_state_changed(self, backend, state):
        """Internal handler for playback state changes (sender-anchored)"""
        is_playing = state == PlaybackState.PLAYING
        self._is_playing_map[backend] = is_playing

        if self._is_active_backend(backend):
            old_state = self._is_playing
            self._is_playing = is_playing
            # Only emit if state actually changed (prevent duplicate emissions from optimistic updates)
            if old_state != self._is_playing:
                logger.debug(
                    "Playback state changed (active=%s): %s -> %s (state=%s)",
                    backend is self.media_backend,
                    old_state,
                    self._is_playing,
                    state,
                )
                self.is_playing_changed.emit(self._is_playing)

    def _on_position_changed(self, backend, position):
        """Internal handler for position changes - forwards to external signal (only from active backend)"""
        # Only forward position updates from the currently active backend
        if self._is_active_backend(backend):
            self.position_changed.emit(position)

    def _on_media_status_changed(self, backend, status):
        """Internal handler for media status changes (sender-anchored)"""
        # Handle invalid or stalled media on the emitting backend
        if status == MediaStatus.INVALID:
            logger.error("Media backend encountered invalid media - recovering (sender-anchored)")
            self._is_loaded_map[backend] = False
            backend.stop()
            backend.unload()
            if self._is_active_backend(backend):
                self._media_is_loaded = False
                self.media_status_changed.emit(False)
                self.is_playing_changed.emit(False)
                # Switch back to audio mode to show proper hint
                if self._audioFileStatus == AudioFileStatus.VOCALS:
                    logger.info("Switching back to audio mode due to invalid vocals file")
                    self.audio_mode()
            return

        if status == MediaStatus.STALLED:
            logger.warning("Media backend stalled - attempting recovery (sender-anchored)")
            self._is_loaded_map[backend] = False
            backend.stop()
            if self._is_active_backend(backend):
                self._media_is_loaded = False
                self.media_status_changed.emit(False)
            return

        # Normal status handling: update per-backend loaded flag
        is_loaded = status == MediaStatus.LOADED or status == MediaStatus.BUFFERED
        self._is_loaded_map[backend] = is_loaded
        if self._is_active_backend(backend):
            self._media_is_loaded = is_loaded
            logger.debug(f"Media status changed (active backend): {status}, loaded: {self._media_is_loaded}")
            self.media_status_changed.emit(self._media_is_loaded)

    def _on_media_error(self, backend, error_string):
        """Internal handler for media backend errors (sender-anchored)"""
        logger.error(f"Media backend error occurred: {error_string}")

        # Stop playback and clear source on the emitting backend
        backend.stop()
        backend.unload()

        # Update controller state if this is the active backend
        if self._is_active_backend(backend):
            self._media_is_loaded = False
            self._is_playing = False
            self.media_status_changed.emit(False)
            self.is_playing_changed.emit(False)

        # If vocals mode caused the error, switch back to audio mode
        if self._audioFileStatus == AudioFileStatus.VOCALS and self._is_active_backend(backend):
            logger.info("Switching back to audio mode due to vocals file error")
            self.audio_mode()
