"""
USDX Tag Parser Module

Strategy pattern implementation for parsing USDX file tags and notes.
Provides Protocol-based TagHandler interface with registry-based dispatch.
"""

from services.usdx.parsers.base import TagHandler
from services.usdx.parsers.registry import TagRegistry
from services.usdx.parsers.handlers import (
    GapTagHandler,
    TitleTagHandler,
    ArtistTagHandler,
    Mp3TagHandler,
    AudioTagHandler,
    BpmTagHandler,
    StartTagHandler,
    RelativeTagHandler,
    NoteLineHandler
)


def create_registry() -> TagRegistry:
    """
    Create and configure a TagRegistry with all standard USDX tag handlers.

    Returns:
        TagRegistry: Configured registry ready for parsing USDX content
    """
    registry = TagRegistry()
    registry.register_all([
        GapTagHandler(),
        TitleTagHandler(),
        ArtistTagHandler(),
        Mp3TagHandler(),      # Legacy #MP3: tag
        AudioTagHandler(),    # Modern #AUDIO: tag
        BpmTagHandler(),
        StartTagHandler(),
        RelativeTagHandler(),
        NoteLineHandler()     # Handles non-tag lines with note data
    ])
    return registry


__all__ = [
    'TagHandler',
    'TagRegistry',
    'create_registry',
    'GapTagHandler',
    'TitleTagHandler',
    'ArtistTagHandler',
    'Mp3TagHandler',
    'AudioTagHandler',
    'BpmTagHandler',
    'StartTagHandler',
    'RelativeTagHandler',
    'NoteLineHandler'
]
