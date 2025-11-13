"""
Abstract media backend interface.

Defines the protocol that all media backends must implement.
"""

from typing import Protocol, Optional
from enum import Enum
from PySide6.QtCore import Signal


class PlaybackState(Enum):
    """Unified playback state across all backends."""
    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED = "paused"


class MediaStatus(Enum):
    """Unified media status across all backends."""
    NO_MEDIA = "no_media"
    LOADING = "loading"
    LOADED = "loaded"
    BUFFERING = "buffering"
    BUFFERED = "buffered"
    STALLED = "stalled"
    INVALID = "invalid"


class MediaBackend(Protocol):
    """
    Protocol defining the interface that all media backends must implement.

    This abstraction allows swapping between Qt, VLC, or other backends
    while keeping the UI layer unchanged.
    """

    # Signals (Qt signals for UI compatibility)
    position_changed: Signal  # Signal[int] - position in milliseconds
    playback_state_changed: Signal  # Signal[PlaybackState]
    media_status_changed: Signal  # Signal[MediaStatus]
    error_occurred: Signal  # Signal[str] - error message

    # Lifecycle
    def load(self, file_path: str) -> None:
        """
        Load a media file for playback.

        Args:
            file_path: Absolute path to the media file
        """
        ...

    def unload(self) -> None:
        """Clear the current media source and reset to idle state."""
        ...

    # Playback control
    def play(self) -> None:
        """Start or resume playback."""
        ...

    def pause(self) -> None:
        """Pause playback."""
        ...

    def stop(self) -> None:
        """Stop playback and reset position to beginning."""
        ...

    # Position/seeking
    def seek(self, position_ms: int) -> None:
        """
        Seek to a specific position.

        Args:
            position_ms: Position in milliseconds
        """
        ...

    def get_position(self) -> int:
        """
        Get current playback position.

        Returns:
            Position in milliseconds
        """
        ...

    def get_duration(self) -> int:
        """
        Get total media duration.

        Returns:
            Duration in milliseconds, or 0 if unknown
        """
        ...

    # State queries
    def is_playing(self) -> bool:
        """
        Check if media is currently playing.

        Returns:
            True if playing, False otherwise
        """
        ...

    def is_loaded(self) -> bool:
        """
        Check if media is loaded and ready.

        Returns:
            True if loaded, False otherwise
        """
        ...

    def get_playback_state(self) -> PlaybackState:
        """
        Get current playback state.

        Returns:
            Current PlaybackState
        """
        ...

    def get_media_status(self) -> MediaStatus:
        """
        Get current media status.

        Returns:
            Current MediaStatus
        """
        ...

    # Audio settings
    def set_volume(self, volume: int) -> None:
        """
        Set playback volume.

        Args:
            volume: Volume level (0-100)
        """
        ...

    def get_volume(self) -> int:
        """
        Get current volume.

        Returns:
            Volume level (0-100)
        """
        ...

    # Backend info
    def get_backend_name(self) -> str:
        """
        Get the name of this backend.

        Returns:
            Backend identifier (e.g., "Qt/WMF", "Qt/AVFoundation", "VLC")
        """
        ...

    def get_backend_version(self) -> Optional[str]:
        """
        Get backend version information.

        Returns:
            Version string if available, None otherwise
        """
        ...

    def get_current_file(self) -> Optional[str]:
        """
        Get the currently loaded file path.

        Returns:
            File path if media is loaded, None otherwise
        """
        ...
