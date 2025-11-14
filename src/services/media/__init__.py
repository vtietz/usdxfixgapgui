"""
Media playback backend abstraction layer.

Provides a unified interface for different media backends (Qt, VLC, etc.)
with automatic selection of the most reliable backend per OS.
"""

from services.media.backend import MediaBackend, PlaybackState, MediaStatus
from services.media.backend_factory import create_backend, get_backend_info

__all__ = [
    "MediaBackend",
    "PlaybackState",
    "MediaStatus",
    "create_backend",
    "get_backend_info",
]
