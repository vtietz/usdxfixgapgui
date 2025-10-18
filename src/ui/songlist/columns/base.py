"""
Base Protocol for Column Strategy Pattern

Defines the interface for column-specific formatting and sorting.
"""

from typing import Protocol, Any, Optional
from model.song import Song


class ColumnStrategy(Protocol):
    """Protocol defining column behavior interface."""

    @property
    def column_index(self) -> int:
        """The column index this strategy handles."""
        ...

    def format_display(self, song: Song, cache_entry: Optional[dict]) -> str:
        """
        Format display text for this column.

        Args:
            song: The song to format
            cache_entry: Optional cached data (e.g., relative path)

        Returns:
            Formatted string for display
        """
        ...

    def get_sort_key(self, song: Song, cache_entry: Optional[dict]) -> Any:
        """
        Get sort key for this column.

        Args:
            song: The song to sort
            cache_entry: Optional cached data

        Returns:
            Comparable value for sorting
        """
        ...
