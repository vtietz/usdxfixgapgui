"""
Column Strategy Registry

Central registry for mapping column indices to strategies.
"""

from typing import Dict, List, Optional, Any
from model.song import Song
from .base import ColumnStrategy


class ColumnRegistry:
    """Registry for column strategies."""

    def __init__(self):
        self._strategies: Dict[int, ColumnStrategy] = {}

    def register(self, strategy: ColumnStrategy) -> None:
        """Register a column strategy."""
        self._strategies[strategy.column_index] = strategy

    def register_all(self, strategies: List[ColumnStrategy]) -> None:
        """Register multiple strategies at once."""
        for strategy in strategies:
            self.register(strategy)

    def format_display(
        self,
        song: Song,
        column: int,
        cache_entry: Optional[dict] = None
    ) -> str:
        """
        Format display for column using registered strategy.

        Args:
            song: Song to format
            column: Column index
            cache_entry: Optional cached data

        Returns:
            Formatted display string, empty if no strategy registered
        """
        strategy = self._strategies.get(column)
        if strategy:
            return strategy.format_display(song, cache_entry)
        return ""

    def get_sort_key(
        self,
        song: Song,
        column: int,
        cache_entry: Optional[dict] = None
    ) -> Any:
        """
        Get sort key for column using registered strategy.

        Args:
            song: Song to sort
            column: Column index
            cache_entry: Optional cached data

        Returns:
            Sort key, empty string if no strategy registered
        """
        strategy = self._strategies.get(column)
        if strategy:
            return strategy.get_sort_key(song, cache_entry)
        return ""
