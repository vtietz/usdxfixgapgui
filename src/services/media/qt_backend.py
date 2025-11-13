"""
Qt-based media backend adapter.

Wraps QMediaPlayer to implement the unified MediaBackend interface.
"""

import os
import logging
from typing import Optional
from PySide6.QtCore import QObject, Signal, QUrl
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

from services.media.backend import MediaBackend, PlaybackState, MediaStatus
from ui.mediaplayer.loader import MediaPlayerLoader

logger = logging.getLogger(__name__)


class QtBackendAdapter(QObject):
    """
    Qt QMediaPlayer backend adapter.

    Implements the MediaBackend protocol using Qt's QMediaPlayer.
    Reuses the MediaPlayerLoader for debounced setSource operations.
    """

    # Signals
    position_changed = Signal(int)  # position in ms
    playback_state_changed = Signal(object)  # PlaybackState
    media_status_changed = Signal(object)  # MediaStatus
    error_occurred = Signal(str)  # error message

    def __init__(self):
        """Initialize Qt backend with QMediaPlayer."""
        super().__init__()

        # Create QMediaPlayer with audio output
        self._audio_output = QAudioOutput()
        self._audio_output.setVolume(0.5)  # Default 50%

        self._player = QMediaPlayer()
        self._player.setAudioOutput(self._audio_output)

        # Create debounced loader
        self._loader = MediaPlayerLoader(self._player)

        # State tracking
        self._playback_state = PlaybackState.STOPPED
        self._media_status = MediaStatus.NO_MEDIA

        # Connect Qt signals to our unified signals
        self._player.playbackStateChanged.connect(self._on_playback_state_changed)
        self._player.mediaStatusChanged.connect(self._on_media_status_changed)
        self._player.positionChanged.connect(self._on_position_changed)
        self._player.errorOccurred.connect(self._on_error_occurred)

        # Detect which Qt multimedia backend is active
        backend_name = self._detect_qt_backend()
        logger.info(f"QtBackendAdapter initialized with {backend_name}")

    def _detect_qt_backend(self) -> str:
        """
        Detect which Qt multimedia backend is being used.

        Returns:
            Backend name (e.g., "Qt/WMF", "Qt/AVFoundation", "Qt/GStreamer")
        """
        import sys

        # Check environment variable
        env_backend = os.environ.get("QT_MEDIA_BACKEND", "")
        if env_backend:
            return f"Qt/{env_backend}"

        # Platform-specific defaults
        if sys.platform == "win32":
            return "Qt/WMF"  # Windows Media Foundation
        elif sys.platform == "darwin":
            return "Qt/AVFoundation"  # macOS
        else:
            return "Qt/GStreamer"  # Linux

    # Lifecycle

    def load(self, file_path: str) -> None:
        """Load a media file using the debounced loader."""
        logger.debug(f"QtBackend: loading {file_path}")
        self._loader.load(file_path)

    def unload(self) -> None:
        """Clear media source."""
        logger.debug("QtBackend: unloading media")
        self._loader.unload()
        self._playback_state = PlaybackState.STOPPED
        self._media_status = MediaStatus.NO_MEDIA

    # Playback control

    def play(self) -> None:
        """Start or resume playback."""
        # Check if media is ready
        if self._media_status in (MediaStatus.LOADED, MediaStatus.BUFFERED):
            logger.debug("QtBackend: play()")
            self._player.play()
        elif self._playback_state == PlaybackState.PAUSED:
            logger.debug("QtBackend: resume from pause")
            self._player.play()
        else:
            logger.debug(f"QtBackend: play() ignored (status={self._media_status})")

    def pause(self) -> None:
        """Pause playback."""
        if self._playback_state == PlaybackState.PLAYING:
            logger.debug("QtBackend: pause()")
            self._player.pause()

    def stop(self) -> None:
        """Stop playback."""
        logger.debug("QtBackend: stop()")
        self._player.stop()
        self._playback_state = PlaybackState.STOPPED

    # Position/seeking

    def seek(self, position_ms: int) -> None:
        """Seek to position."""
        logger.debug(f"QtBackend: seek to {position_ms}ms")
        self._player.setPosition(position_ms)

    def get_position(self) -> int:
        """Get current position in milliseconds."""
        return self._player.position()

    def get_duration(self) -> int:
        """Get duration in milliseconds."""
        return self._player.duration()

    # State queries

    def is_playing(self) -> bool:
        """Check if currently playing."""
        return self._playback_state == PlaybackState.PLAYING

    def is_loaded(self) -> bool:
        """Check if media is loaded."""
        return self._media_status in (MediaStatus.LOADED, MediaStatus.BUFFERED)

    def get_playback_state(self) -> PlaybackState:
        """Get current playback state."""
        return self._playback_state

    def get_media_status(self) -> MediaStatus:
        """Get current media status."""
        return self._media_status

    # Audio settings

    def set_volume(self, volume: int) -> None:
        """Set volume (0-100)."""
        # Qt uses 0.0-1.0 range
        self._audio_output.setVolume(volume / 100.0)

    def get_volume(self) -> int:
        """Get volume (0-100)."""
        # Convert from Qt's 0.0-1.0 to 0-100
        return int(self._audio_output.volume() * 100)

    # Backend info

    def get_backend_name(self) -> str:
        """Get backend name."""
        return self._detect_qt_backend()

    def get_backend_version(self) -> Optional[str]:
        """Get Qt version."""
        from PySide6 import __version__
        return f"PySide6 {__version__}"

    def get_current_file(self) -> Optional[str]:
        """Get the currently loaded file path."""
        source = self._player.source()
        if source.isEmpty():
            return None
        # Convert QUrl to local file path
        return source.toLocalFile() if source.isLocalFile() else source.toString()

    # Signal handlers (map Qt signals to unified signals)

    def _on_playback_state_changed(self, qt_state: QMediaPlayer.PlaybackState) -> None:
        """Handle Qt playback state changes."""
        # Map Qt state to unified state
        if qt_state == QMediaPlayer.PlaybackState.PlayingState:
            self._playback_state = PlaybackState.PLAYING
        elif qt_state == QMediaPlayer.PlaybackState.PausedState:
            self._playback_state = PlaybackState.PAUSED
        else:  # StoppedState
            self._playback_state = PlaybackState.STOPPED

        logger.debug(f"QtBackend: playback state -> {self._playback_state.value}")
        self.playback_state_changed.emit(self._playback_state)

    def _on_media_status_changed(self, qt_status: QMediaPlayer.MediaStatus) -> None:
        """Handle Qt media status changes."""
        # Map Qt status to unified status
        status_map = {
            QMediaPlayer.MediaStatus.NoMedia: MediaStatus.NO_MEDIA,
            QMediaPlayer.MediaStatus.LoadingMedia: MediaStatus.LOADING,
            QMediaPlayer.MediaStatus.LoadedMedia: MediaStatus.LOADED,
            QMediaPlayer.MediaStatus.BufferingMedia: MediaStatus.BUFFERING,
            QMediaPlayer.MediaStatus.BufferedMedia: MediaStatus.BUFFERED,
            QMediaPlayer.MediaStatus.StalledMedia: MediaStatus.STALLED,
            QMediaPlayer.MediaStatus.InvalidMedia: MediaStatus.INVALID,
        }

        self._media_status = status_map.get(qt_status, MediaStatus.NO_MEDIA)
        logger.debug(f"QtBackend: media status -> {self._media_status.value}")
        self.media_status_changed.emit(self._media_status)

    def _on_position_changed(self, position: int) -> None:
        """Forward position changes."""
        self.position_changed.emit(position)

    def _on_error_occurred(self, error: QMediaPlayer.Error, error_string: str) -> None:
        """Handle Qt media player errors."""
        error_msg = f"QMediaPlayer error: {error.name if hasattr(error, 'name') else error} - {error_string}"
        logger.error(error_msg)
        self.error_occurred.emit(error_msg)

        # Reset state on error
        self._playback_state = PlaybackState.STOPPED
        self._media_status = MediaStatus.INVALID
