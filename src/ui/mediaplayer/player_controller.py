import os
import logging
from PySide6.QtCore import QObject, Signal, QUrl
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from utils.files import get_file_checksum

from ui.mediaplayer.constants import AudioFileStatus
from ui.mediaplayer.loader import MediaPlayerLoader

logger = logging.getLogger(__name__)

# Try to import torchaudio for validation, but make it optional
torchaudio: object | None = None
try:
    import torchaudio

    TORCHAUDIO_AVAILABLE = True
except (ImportError, OSError) as e:
    logger.warning(f"torchaudio not available for media validation: {e}")
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

        # Create separate players for audio and vocals
        # This prevents WMF deadlock when switching between sources
        logger.info("Creating dual media players (audio + vocals)")

        # Audio player
        self.audio_output_audio = QAudioOutput()
        self.audio_output_audio.setVolume(50)
        self.audio_player = QMediaPlayer()
        self.audio_player.setAudioOutput(self.audio_output_audio)
        self.audio_player_loader = MediaPlayerLoader(self.audio_player)

        # Vocals player
        self.audio_output_vocals = QAudioOutput()
        self.audio_output_vocals.setVolume(50)
        self.vocals_player = QMediaPlayer()
        self.vocals_player.setAudioOutput(self.audio_output_vocals)
        self.vocals_player_loader = MediaPlayerLoader(self.vocals_player)

        # Connect signals for both players
        self.audio_player.playbackStateChanged.connect(self._on_playback_state_changed)
        self.audio_player.mediaStatusChanged.connect(self._on_media_status_changed)
        self.audio_player.errorOccurred.connect(self._on_media_error)

        self.vocals_player.playbackStateChanged.connect(self._on_playback_state_changed)
        self.vocals_player.mediaStatusChanged.connect(self._on_media_status_changed)
        self.vocals_player.errorOccurred.connect(self._on_media_error)

        logger.info("Dual media players created successfully")

    @property
    def media_player(self):
        """Get the currently active media player based on mode"""
        return self.audio_player if self._audioFileStatus == AudioFileStatus.AUDIO else self.vocals_player

    @property
    def media_player_loader(self):
        """Get the currently active media player loader based on mode"""
        return self.audio_player_loader if self._audioFileStatus == AudioFileStatus.AUDIO else self.vocals_player_loader

    def play(self):
        """Toggle play/pause - uses active player based on mode"""
        # Stop the inactive player first
        inactive_player = self.vocals_player if self._audioFileStatus == AudioFileStatus.AUDIO else self.audio_player
        if inactive_player.isPlaying():
            inactive_player.stop()

        # Now control the active player
        active_player = self.media_player
        if active_player.isPlaying():
            active_player.pause()
        else:
            # Allow play if media is loaded or buffered (paused state)
            status = active_player.mediaStatus()
            if status in (QMediaPlayer.MediaStatus.LoadedMedia, QMediaPlayer.MediaStatus.BufferedMedia):
                active_player.play()

    def stop(self):
        """Stop both players"""
        self.audio_player.stop()
        self.vocals_player.stop()

    def audio_mode(self):
        """Switch to audio mode"""
        # Stop vocals player if playing
        if self.vocals_player.isPlaying():
            self.vocals_player.stop()
        self._audioFileStatus = AudioFileStatus.AUDIO
        self.audio_file_status_changed.emit(self._audioFileStatus)

    def vocals_mode(self):
        """Switch to vocals mode"""
        # Stop audio player if playing
        if self.audio_player.isPlaying():
            self.audio_player.stop()
        self._audioFileStatus = AudioFileStatus.VOCALS
        self.audio_file_status_changed.emit(self._audioFileStatus)

    def load_media(self, file: str | None):
        """Load a media file into the active player (audio or vocals)"""
        active_player = self.media_player  # Property returns correct player based on mode
        active_loader = self.media_player_loader

        if not file:
            logger.debug(f"No media file to load for {self._audioFileStatus} player")
            active_player.stop()
            active_player.setSource(QUrl())
            return

        new_source = QUrl.fromLocalFile(file)
        logger.debug(f"Loading {self._audioFileStatus} media: {file}")

        # Check if already loaded
        current_source = active_player.source()
        if current_source.toString() == new_source.toString():
            logger.debug(f"Media source unchanged for {self._audioFileStatus} player - not reloading")
            return

        # Pre-validate the media file before loading
        if not self._validate_media_file(file):
            logger.error(f"Media file validation failed: {file}")
            if self._audioFileStatus == AudioFileStatus.VOCALS:
                logger.info("Switching to audio mode due to invalid vocals file")
                self.vocals_validation_failed.emit()
                self.audio_mode()
            return

        logger.debug(f"Setting new media source for {self._audioFileStatus} player: {new_source}")
        active_player.stop()
        active_loader.load(file)

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
        """Unload media from both players"""
        logger.debug("Unloading all media from both players")
        self.audio_player.stop()
        self.audio_player.setSource(QUrl())
        self.vocals_player.stop()
        self.vocals_player.setSource(QUrl())

    def adjust_position_left(self):
        """Move playback position backwards"""
        if self._audioFileStatus == AudioFileStatus.AUDIO:
            ms = self._config.adjust_player_position_step_audio
        else:
            ms = self._config.adjust_player_position_step_vocals
        newPosition = max(0, self.media_player.position() - ms)
        self.media_player.setPosition(newPosition)

    def adjust_position_right(self):
        """Move playback position forwards"""
        if self._audioFileStatus == AudioFileStatus.AUDIO:
            ms = self._config.adjust_player_position_step_audio
        else:
            ms = self._config.adjust_player_position_step_vocals
        newPosition = max(0, self.media_player.position() + ms)
        self.media_player.setPosition(newPosition)

    def set_position(self, relative_position):
        """Set position as a percentage of media duration"""
        if self.media_player.duration() > 0:
            new_position = int(relative_position * self.media_player.duration())
            self.media_player.setPosition(new_position)
            self.position_changed.emit(new_position)

    def get_position(self):
        """Get current position in milliseconds"""
        return self.media_player.position()

    def get_duration(self):
        """Get media duration in milliseconds"""
        return self.media_player.duration()

    def get_audio_status(self):
        """Get current audio status (AUDIO or VOCALS)"""
        return self._audioFileStatus

    def is_media_loaded(self):
        """Check if media is loaded"""
        return self._media_is_loaded

    def is_playing(self):
        """Check if media is currently playing"""
        return self._is_playing

    def _on_playback_state_changed(self):
        """Internal handler for playback state changes"""
        old_state = self._is_playing
        self._is_playing = self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        logger.debug(f"Playback state changed: {old_state} -> {self._is_playing} (state={self.media_player.playbackState()})")
        self.is_playing_changed.emit(self._is_playing)

    def _on_media_status_changed(self, status):
        """Internal handler for media status changes"""
        # Handle invalid or stalled media
        if status == QMediaPlayer.MediaStatus.InvalidMedia:
            logger.error("Media player encountered invalid media - recovering")
            self._media_is_loaded = False
            self.media_player.stop()
            self.media_player.setSource(QUrl())
            self.media_status_changed.emit(False)
            self.is_playing_changed.emit(False)
            # Switch back to audio mode to show proper hint
            if self._audioFileStatus == AudioFileStatus.VOCALS:
                logger.info("Switching back to audio mode due to invalid vocals file")
                self.audio_mode()
            return

        if status == QMediaPlayer.MediaStatus.StalledMedia:
            logger.warning("Media player stalled - attempting recovery")
            self._media_is_loaded = False
            self.media_player.stop()
            self.media_status_changed.emit(False)
            return

        # Normal status handling
        self._media_is_loaded = status == QMediaPlayer.MediaStatus.LoadedMedia
        logger.debug(f"Media status changed: {status}, loaded: {self._media_is_loaded}")
        self.media_status_changed.emit(self._media_is_loaded)

    def _on_media_error(self, error, error_string):
        """Internal handler for media player errors"""
        logger.error(f"QMediaPlayer error occurred: {error} - {error_string}")
        logger.error(f"Error code: {error.name if hasattr(error, 'name') else error}")

        # Stop playback and clear source to prevent freeze
        self._media_is_loaded = False
        self._is_playing = False
        self.media_player.stop()
        self.media_player.setSource(QUrl())

        # Emit signals to update UI
        self.media_status_changed.emit(False)
        self.is_playing_changed.emit(False)

        # If vocals mode caused the error, switch back to audio mode
        if self._audioFileStatus == AudioFileStatus.VOCALS:
            logger.info("Switching back to audio mode due to vocals file error")
            self.audio_mode()
