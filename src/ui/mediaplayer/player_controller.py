import os
import logging
from PySide6.QtCore import QObject, Signal, QUrl
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from utils.files import get_file_checksum

from ui.mediaplayer.constants import AudioFileStatus
from ui.mediaplayer.loader import MediaPlayerLoader

logger = logging.getLogger(__name__)

class PlayerController(QObject):
    position_changed = Signal(int)
    is_playing_changed = Signal(bool)
    audio_file_status_changed = Signal(AudioFileStatus)
    media_status_changed = Signal(bool)

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

    def load_media(self, file: str):
        """Load a media file into the player"""
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

        logger.debug(f"Setting new media source: {new_source}")
        self.media_player.stop()
        self.media_player_loader.load(file)
        self.old_source = new_source
        self.old_checksum = get_file_checksum(file)

    def unload_all_media(self):
        """Unload all media from the player"""
        self.media_player.stop()
        self.media_player.setSource(QUrl())

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
        self._media_is_loaded = status == QMediaPlayer.MediaStatus.LoadedMedia
        logger.debug(f"Media status changed: {status}, loaded: {self._media_is_loaded}")
        self.media_status_changed.emit(self._media_is_loaded)
