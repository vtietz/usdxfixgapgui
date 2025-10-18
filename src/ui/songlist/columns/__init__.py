"""
Column Strategy Pattern for Song List Display and Sorting

Eliminates switch-statement complexity by delegating column-specific
logic to dedicated strategy classes.

Complexity reduction: CCN 19→2 (format), CCN 27→2 (sort)
"""

from .base import ColumnStrategy
from .registry import ColumnRegistry
from .strategies import (
    PathColumn,
    ArtistColumn,
    TitleColumn,
    DurationColumn,
    BPMColumn,
    GapColumn,
    DetectedGapColumn,
    DiffColumn,
    NotesOverlapColumn,
    ProcessedTimeColumn,
    NormalizedColumn,
    StatusColumn
)


def create_registry(base_directory: str) -> ColumnRegistry:
    """Factory function to create a configured ColumnRegistry.

    Args:
        base_directory: Base directory for relative path calculation

    Returns:
        Configured ColumnRegistry with all column strategies registered
    """
    registry = ColumnRegistry()
    registry.register_all([
        PathColumn(base_directory),
        ArtistColumn(),
        TitleColumn(),
        DurationColumn(),
        BPMColumn(),
        GapColumn(),
        DetectedGapColumn(),
        DiffColumn(),
        NotesOverlapColumn(),
        ProcessedTimeColumn(),
        NormalizedColumn(),
        StatusColumn()
    ])
    return registry


__all__ = [
    'ColumnStrategy',
    'ColumnRegistry',
    'create_registry',
    'PathColumn',
    'ArtistColumn',
    'TitleColumn',
    'DurationColumn',
    'BPMColumn',
    'GapColumn',
    'DetectedGapColumn',
    'DiffColumn',
    'NotesOverlapColumn',
    'ProcessedTimeColumn',
    'NormalizedColumn',
    'StatusColumn',
]
