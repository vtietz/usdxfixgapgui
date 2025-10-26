"""
Base Protocol for USDX Tag Handlers

Defines the interface for parsing individual USDX tags.
"""

from typing import Protocol
from model.usdx_file import Tags


class TagHandler(Protocol):
    """Protocol for USDX tag parsing strategies.

    Each handler is responsible for parsing one specific tag type
    or line pattern from a USDX file.
    """

    @property
    def tag_prefix(self) -> str:
        """Return the tag prefix this handler recognizes (e.g., '#GAP:').

        For note handlers, return empty string to indicate non-tag lines.
        """
        ...

    def parse(self, line: str, tags: Tags, notes: list) -> None:
        """Parse a line and update tags or notes accordingly.

        Args:
            line: The line to parse
            tags: Tags object to update
            notes: List of notes to append to
        """
        ...