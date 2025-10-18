"""
Tag Handler Registry for USDX Parser

Provides O(1) dispatch to appropriate tag handler based on line prefix.
"""

from typing import Dict, List
from .base import TagHandler
from model.usdx_file import Tags


class TagRegistry:
    """Registry for dispatching lines to appropriate tag handlers."""

    def __init__(self):
        self._handlers: Dict[str, TagHandler] = {}
        self._note_handler: TagHandler | None = None

    def register(self, handler: TagHandler) -> None:
        """Register a single tag handler.

        Args:
            handler: TagHandler instance to register
        """
        prefix = handler.tag_prefix
        if prefix:
            self._handlers[prefix] = handler
        else:
            # Empty prefix indicates note handler
            self._note_handler = handler

    def register_all(self, handlers: List[TagHandler]) -> None:
        """Register multiple handlers at once.

        Args:
            handlers: List of TagHandler instances
        """
        for handler in handlers:
            self.register(handler)

    def parse_line(self, line: str, tags: Tags, notes: list) -> None:
        """Parse a line using the appropriate handler.

        Args:
            line: Line to parse
            tags: Tags object to update
            notes: List to append notes to
        """
        # Check for tag handlers first
        for prefix, handler in self._handlers.items():
            if line.startswith(prefix):
                handler.parse(line, tags, notes)
                return

        # If not a tag and we have a note handler, try note parsing
        if self._note_handler and not line.startswith('#'):
            self._note_handler.parse(line, tags, notes)
