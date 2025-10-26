import os
import logging
from pathlib import Path
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
    vocals_validation_failed = Signal()  # NEW: Emitted when vocals file validation fails

    def __init__(self, config):
        super().__init__()
        self._config = config
        self._audioFileStatus = AudioFileStatus.AUDIO
        self._media_is_loaded = False
        self._is_playing = False
        self.old_source = None
        self.old_checksum = None

        # Setup audio components
        self.audio_output = QAudioOutput()
        self.audio_output.setVolume(50)

        self.media_player = QMediaPlayer()
        self.media_player.setAudioOutput(self.audio_output)
        self.media_player_loader = MediaPlayerLoader(self.media_player)

        # Connect media player events
        self.media_player.playbackStateChanged.connect(self._on_playback_state_changed)
        self.media_player.mediaStatusChanged.connect(self._on_media_status_changed)
        self.media_player.errorOccurred.connect(self._on_media_error)

    def play(self):
        """Toggle play/pause"""
        logger.debug(f"Play button clicked. Is playing: {self.media_player.isPlaying()}")
        if self.media_player.isPlaying():
            self.media_player.pause()
            logger.debug("Media player paused")
        else:
            self.media_player.play()
            logger.debug("Media player started playing")

    def stop(self):
        """Stop playback"""
        self.media_player.stop()

    def audio_mode(self):
        """Switch to audio mode"""
        self._audioFileStatus = AudioFileStatus.AUDIO
        self.audio_file_status_changed.emit(self._audioFileStatus)

    def vocals_mode(self):
        """Switch to vocals mode"""
        self._audioFileStatus = AudioFileStatus.VOCALS
        self.audio_file_status_changed.emit(self._audioFileStatus)

    def load_media(self, file: str | None):
        """Load a media file into the player with pre-validation"""
        old_source = self.media_player.source()

        if not file:
            logger.debug("No media file to load")
            self.media_player.stop()
            self.media_player.setSource(QUrl())
            return

        new_source = QUrl.fromLocalFile(file)
        logger.debug(f"Loading media file: {file}, exists: {os.path.exists(file)}")

        if old_source.toString() == new_source.toString() and self.old_checksum == get_file_checksum(file):
            logger.debug("Media source unchanged - not reloading")
            return

        # Pre-validate the media file before loading
        if not self._validate_media_file(file):
            logger.error(f"Media file validation failed: {file}")
            # Don't load invalid file - switch to audio mode if in vocals mode
            if self._audioFileStatus == AudioFileStatus.VOCALS:
                logger.info("Switching to audio mode due to invalid vocals file")
                self.vocals_validation_failed.emit()
                self.audio_mode()
            return

        logger.debug(f"Setting new media source: {new_source}")
        self.media_player.stop()
        self.media_player_loader.load(file)
        self.old_source = new_source
        self.old_checksum = get_file_checksum(file)

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
        if "vocals" in file.lower() and file.lower().endswith('.mp3'):
            if not TORCHAUDIO_AVAILABLE or torchaudio is None:
                logger.debug("torchaudio not available, using basic validation only")
                return True  # Fall back to basic validation when torchaudio unavailable

            try:
                info = torchaudio.info(file)  # type: ignore[attr-defined]

                logger.info(f"Vocals file validation - Format: {info.num_channels}ch @ {info.sample_rate}Hz, "
                           f"Frames: {info.num_frames}, Encoding: {getattr(info, 'encoding', 'N/A')}")

                # Check for reasonable audio properties
                if info.num_channels == 0 or info.sample_rate == 0 or info.num_frames == 0:
                    logger.error("Invalid audio properties detected")
                    return False

                # Check for reasonable sample rate (8kHz - 192kHz)
                if info.sample_rate < 8000 or info.sample_rate > 192000:
                    logger.warning(f"Unusual sample rate: {info.sample_rate}Hz")
                    return False

                logger.info("Vocals file validation passed")
                return True

            except Exception as e:
                logger.error(f"torchaudio validation failed for {file}: {e}", exc_info=True)
                return False

        # For other files (audio.mp3), basic validation only
        logger.debug(f"Basic validation passed for {file}")
        return True

    def unload_all_media(self):
        """Unload all media from the player"""
        self.media_player.stop()
        self.media_player.setSource(QUrl())
        # Clear internal tracking to prevent re-validation from loading
        self.old_source = None
        self.old_checksum = None

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
        self._is_playing = self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
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
