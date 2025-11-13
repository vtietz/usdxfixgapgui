"""
VLC-based media backend adapter.

Wraps python-vlc to implement the unified MediaBackend interface.
This backend is preferred on Windows to avoid WMF deadlocks.

Note: Local VLC runtime setup is handled in backend_factory.py before import.
"""

import logging
from typing import Optional
from PySide6.QtCore import QObject, Signal, QTimer

from services.media.backend import MediaBackend, PlaybackState, MediaStatus

logger = logging.getLogger(__name__)

# Try to import VLC
try:
    import vlc
    VLC_AVAILABLE = True
    logger.debug("python-vlc module imported successfully")
except ImportError as e:
    VLC_AVAILABLE = False
    vlc = None  # type: ignore
    logger.warning(f"python-vlc not available: {e}")
except OSError as e:
    VLC_AVAILABLE = False
    vlc = None  # type: ignore
    if "libvlc" in str(e).lower():
        logger.error(f"VLC DLLs not found: {e}")
        logger.error("Install VLC system-wide OR extract portable VLC to vlc_runtime/")
        logger.error("See docs/VLC_RUNTIME_SETUP.md for instructions")
    else:
        logger.warning(f"python-vlc load error: {e}")


class VlcBackendAdapter(QObject):
    """
    VLC backend adapter.

    Implements the MediaBackend protocol using python-vlc (libVLC).
    Emits Qt signals for UI compatibility.
    """

    # Signals
    position_changed = Signal(int)  # position in ms
    playback_state_changed = Signal(object)  # PlaybackState
    media_status_changed = Signal(object)  # MediaStatus
    error_occurred = Signal(str)  # error message

    def __init__(self):
        """Initialize VLC backend."""
        super().__init__()

        if not VLC_AVAILABLE or vlc is None:
            raise RuntimeError("python-vlc is not available - cannot use VLC backend")

        # Create VLC instance with quiet logging
        # --quiet: Suppress console output
        # --no-xlib: Headless mode for Linux
        # --no-video: We only play audio
        vlc_args = ['--quiet', '--no-xlib', '--no-video']
        self._instance = vlc.Instance(vlc_args)
        self._player = self._instance.media_player_new()

        # State tracking
        self._playback_state = PlaybackState.STOPPED
        self._media_status = MediaStatus.NO_MEDIA
        self._current_file: Optional[str] = None
        self._current_media = None  # Keep reference to VLC media object
        self._duration_ms = 0

        # Position polling timer (VLC doesn't emit position signals)
        self._position_timer = QTimer()
        self._position_timer.setInterval(100)  # Poll every 100ms
        self._position_timer.timeout.connect(self._poll_position)

        # Status polling timer (monitor VLC state changes)
        # Start only when media is loaded to reduce idle CPU usage
        self._status_timer = QTimer()
        self._status_timer.setInterval(200)  # Check status every 200ms
        self._status_timer.timeout.connect(self._poll_status)

        # Get VLC version
        try:
            version = vlc.libvlc_get_version().decode('utf-8')
            logger.info(f"VlcBackendAdapter initialized with libVLC {version}")
        except Exception as e:
            logger.warning(f"Could not get VLC version: {e}")
            logger.info("VlcBackendAdapter initialized")

    # Lifecycle

    def load(self, file_path: str) -> None:
        """Load a media file."""
        logger.debug(f"VlcBackend: loading {file_path}")

        try:
            # Create media from file
            media = self._instance.media_new(file_path)
            if media is None:
                raise RuntimeError(f"Failed to create VLC media from {file_path}")

            # Keep reference to prevent garbage collection
            self._current_media = media

            # Set media to player
            self._player.set_media(media)
            self._current_file = file_path

            # Parse media to get duration (synchronous)
            media.parse()
            self._duration_ms = media.get_duration()

            # Update status
            self._media_status = MediaStatus.LOADED
            self.media_status_changed.emit(self._media_status)

            # Start status polling now that media is loaded
            if not self._status_timer.isActive():
                self._status_timer.start()

            logger.debug(f"VlcBackend: loaded {file_path}, duration={self._duration_ms}ms")

        except Exception as e:
            error_msg = f"VLC load error: {e}"
            logger.error(error_msg)
            self.error_occurred.emit(error_msg)
            self._media_status = MediaStatus.INVALID
            self.media_status_changed.emit(self._media_status)

    def unload(self) -> None:
        """Clear media source."""
        logger.debug("VlcBackend: unloading media")

        # Stop polling timers to reduce CPU usage
        self._status_timer.stop()
        self._position_timer.stop()

        # Stop playback
        self._player.stop()

        # Clear media
        self._player.set_media(None)
        self._current_media = None  # Release media reference
        self._current_file = None
        self._duration_ms = 0

        # Update state
        self._playback_state = PlaybackState.STOPPED
        self._media_status = MediaStatus.NO_MEDIA

        # Stop position polling
        if self._position_timer.isActive():
            self._position_timer.stop()

    # Playback control

    def play(self) -> None:
        """Start or resume playback."""
        if self._media_status in (MediaStatus.LOADED, MediaStatus.BUFFERED) or \
           self._playback_state == PlaybackState.PAUSED:
            logger.debug("VlcBackend: play()")
            self._player.play()

            # Start position polling
            if not self._position_timer.isActive():
                self._position_timer.start()
        else:
            logger.debug(f"VlcBackend: play() ignored (status={self._media_status})")

    def pause(self) -> None:
        """Pause playback."""
        if self._playback_state == PlaybackState.PLAYING:
            logger.debug("VlcBackend: pause()")
            self._player.pause()

    def stop(self) -> None:
        """Stop playback."""
        logger.debug("VlcBackend: stop()")
        self._player.stop()

        # Stop position polling
        if self._position_timer.isActive():
            self._position_timer.stop()

        self._playback_state = PlaybackState.STOPPED
        self.playback_state_changed.emit(self._playback_state)

    # Position/seeking

    def seek(self, position_ms: int) -> None:
        """Seek to position with millisecond precision."""
        if self._duration_ms > 0:
            # Use set_time for precise millisecond seeking (preferred for gap editing)
            logger.debug(f"VlcBackend: seek to {position_ms}ms")
            result = self._player.set_time(position_ms)
            if result == -1:
                # Fallback to ratio-based seek if set_time fails
                position_ratio = position_ms / self._duration_ms
                logger.debug(f"VlcBackend: set_time failed, using ratio={position_ratio:.3f}")
                self._player.set_position(position_ratio)
        else:
            logger.warning("VlcBackend: cannot seek (duration unknown)")

    def get_position(self) -> int:
        """Get current position in milliseconds."""
        return int(self._player.get_time())

    def get_duration(self) -> int:
        """Get duration in milliseconds."""
        # Try to get from player first
        duration = self._player.get_length()
        if duration > 0:
            self._duration_ms = duration
        return self._duration_ms

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
        self._player.audio_set_volume(volume)

    def get_volume(self) -> int:
        """Get volume (0-100)."""
        return self._player.audio_get_volume()

    # Backend info

    def get_backend_name(self) -> str:
        """Get backend name."""
        return "VLC"

    def get_backend_version(self) -> Optional[str]:
        """Get VLC version."""
        try:
            return vlc.libvlc_get_version().decode('utf-8')
        except Exception:
            return None

    def get_current_file(self) -> Optional[str]:
        """Get the currently loaded file path."""
        return self._current_file

    # Polling (VLC doesn't have Qt signals)

    def _poll_position(self) -> None:
        """Poll current position and emit signal if changed."""
        if self._playback_state == PlaybackState.PLAYING:
            position = self.get_position()
            if position >= 0:  # Valid position
                self.position_changed.emit(position)

    def _poll_status(self) -> None:
        """Poll VLC state and emit signals if changed."""
        # Check playback state
        vlc_state = self._player.get_state()

        # Map VLC state to unified state
        new_playback_state = self._playback_state

        if vlc_state == vlc.State.Playing:
            new_playback_state = PlaybackState.PLAYING
        elif vlc_state == vlc.State.Paused:
            new_playback_state = PlaybackState.PAUSED
        elif vlc_state in (vlc.State.Stopped, vlc.State.Ended):
            new_playback_state = PlaybackState.STOPPED
            # Stop position polling when stopped
            if self._position_timer.isActive():
                self._position_timer.stop()
        elif vlc_state == vlc.State.Error:
            logger.error("VLC player error state detected")
            self.error_occurred.emit("VLC playback error")
            new_playback_state = PlaybackState.STOPPED

        # Emit if changed
        if new_playback_state != self._playback_state:
            self._playback_state = new_playback_state
            logger.debug(f"VlcBackend: playback state -> {self._playback_state.value}")
            self.playback_state_changed.emit(self._playback_state)

        # Map VLC state to media status
        new_media_status = self._media_status

        if vlc_state in (vlc.State.Opening, vlc.State.Buffering):
            new_media_status = MediaStatus.LOADING
        elif vlc_state in (vlc.State.Playing, vlc.State.Paused):
            new_media_status = MediaStatus.LOADED
        elif vlc_state == vlc.State.Error:
            new_media_status = MediaStatus.INVALID
        elif vlc_state == vlc.State.NothingSpecial:
            # NothingSpecial can mean "loaded but not playing yet" or "no media"
            # Check if we have a media object to distinguish
            if self._current_media is not None:
                new_media_status = MediaStatus.LOADED  # Media loaded, just idle
            else:
                new_media_status = MediaStatus.NO_MEDIA
        elif vlc_state == vlc.State.Stopped:
            # Stopped can mean "stopped playback" or "no media"
            # Keep current status if media is loaded, otherwise set NO_MEDIA
            if self._current_media is None:
                new_media_status = MediaStatus.NO_MEDIA

        # Emit if changed
        if new_media_status != self._media_status:
            self._media_status = new_media_status
            logger.debug(f"VlcBackend: media status -> {self._media_status.value}")
            self.media_status_changed.emit(self._media_status)

    def cleanup(self):
        """Explicit cleanup method - call before app shutdown."""
        try:
            if hasattr(self, '_position_timer') and self._position_timer is not None:
                self._position_timer.stop()
                self._position_timer = None
            if hasattr(self, '_status_timer') and self._status_timer is not None:
                self._status_timer.stop()
                self._status_timer = None
            if hasattr(self, '_player') and self._player is not None:
                self._player.stop()
                self._player.release()
                self._player = None
            if hasattr(self, '_instance') and self._instance is not None:
                self._instance.release()
                self._instance = None
        except Exception:
            pass  # Ignore cleanup errors during shutdown

    def __del__(self):
        """Cleanup VLC resources on deletion."""
        # Don't log during shutdown - Python logging may be gone
        try:
            if hasattr(self, '_player') and self._player is not None:
                self._player.stop()
                self._player.release()
            if hasattr(self, '_instance') and self._instance is not None:
                self._instance.release()
        except (RuntimeError, ImportError):
            pass  # Qt/Python already shutting down
