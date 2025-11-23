"""
Concrete Column Strategy Implementations

Each class handles formatting and sorting for one specific column.
"""

from typing import Any, Optional
from model.song import Song, SongStatus
from utils import files


class PathColumn:
    """Column 0: Relative path to song file."""

    def __init__(self, base_directory: str):
        """Initialize with the base directory for relative path calculation."""
        self.base_directory = base_directory

    @property
    def column_index(self) -> int:
        return 0

    def format_display(self, song: Song, cache_entry: Optional[dict]) -> str:
        if cache_entry:
            return cache_entry["relative_path"]
        # Cache miss - compute on demand
        return files.get_relative_path(self.base_directory, song.path)

    def get_sort_key(self, song: Song, cache_entry: Optional[dict]) -> Any:
        if cache_entry:
            return cache_entry["relative_path"]
        return files.get_relative_path(self.base_directory, song.path)


class ArtistColumn:
    """Column 1: Artist name."""

    @property
    def column_index(self) -> int:
        return 1

    def format_display(self, song: Song, cache_entry: Optional[dict]) -> str:
        return song.artist

    def get_sort_key(self, song: Song, cache_entry: Optional[dict]) -> Any:
        return song.artist.lower()


class TitleColumn:
    """Column 2: Song title."""

    @property
    def column_index(self) -> int:
        return 2

    def format_display(self, song: Song, cache_entry: Optional[dict]) -> str:
        return song.title

    def get_sort_key(self, song: Song, cache_entry: Optional[dict]) -> Any:
        if cache_entry and "title_sort_key" in cache_entry:
            return cache_entry["title_sort_key"]
        return song.title_sort_key


class DurationColumn:
    """Column 3: Song duration."""

    @property
    def column_index(self) -> int:
        return 3

    def format_display(self, song: Song, cache_entry: Optional[dict]) -> str:
        return song.duration_str

    def get_sort_key(self, song: Song, cache_entry: Optional[dict]) -> Any:
        return song.duration_ms if song.duration_ms else 0


class BPMColumn:
    """Column 4: Beats per minute."""

    @property
    def column_index(self) -> int:
        return 4

    def format_display(self, song: Song, cache_entry: Optional[dict]) -> str:
        return str(song.bpm)

    def get_sort_key(self, song: Song, cache_entry: Optional[dict]) -> Any:
        return song.bpm if song.bpm else 0


class GapColumn:
    """Column 5: Current gap value."""

    @property
    def column_index(self) -> int:
        return 5

    def format_display(self, song: Song, cache_entry: Optional[dict]) -> str:
        return str(song.gap)

    def get_sort_key(self, song: Song, cache_entry: Optional[dict]) -> Any:
        return song.gap if song.gap else 0


class DetectedGapColumn:
    """Column 6: Gap detected by analysis."""

    @property
    def column_index(self) -> int:
        return 6

    def format_display(self, song: Song, cache_entry: Optional[dict]) -> str:
        if song.gap_info:
            return str(song.gap_info.detected_gap)
        return ""

    def get_sort_key(self, song: Song, cache_entry: Optional[dict]) -> Any:
        if song.gap_info and song.gap_info.detected_gap:
            return song.gap_info.detected_gap
        return 0


class DiffColumn:
    """Column 7: Difference between current and detected gap."""

    @property
    def column_index(self) -> int:
        return 7

    def format_display(self, song: Song, cache_entry: Optional[dict]) -> str:
        if song.gap_info:
            return str(song.gap_info.diff)
        return ""

    def get_sort_key(self, song: Song, cache_entry: Optional[dict]) -> Any:
        if song.gap_info and song.gap_info.diff:
            return song.gap_info.diff
        return 0


class NotesOverlapColumn:
    """Column 8: Notes overlap amount."""

    @property
    def column_index(self) -> int:
        return 8

    def format_display(self, song: Song, cache_entry: Optional[dict]) -> str:
        if song.gap_info:
            return str(song.gap_info.notes_overlap)
        return ""

    def get_sort_key(self, song: Song, cache_entry: Optional[dict]) -> Any:
        if song.gap_info and song.gap_info.notes_overlap:
            return song.gap_info.notes_overlap
        return 0


class ProcessedTimeColumn:
    """Column 9: Processing timestamp."""

    @property
    def column_index(self) -> int:
        return 9

    def format_display(self, song: Song, cache_entry: Optional[dict]) -> str:
        if song.gap_info:
            return song.gap_info.processed_time
        return ""

    def get_sort_key(self, song: Song, cache_entry: Optional[dict]) -> Any:
        if song.gap_info and song.gap_info.processed_time:
            return song.gap_info.processed_time
        return ""


class NormalizedColumn:
    """Column 10: Normalization status."""

    @property
    def column_index(self) -> int:
        return 10

    def format_display(self, song: Song, cache_entry: Optional[dict]) -> str:
        return song.normalized_str

    def get_sort_key(self, song: Song, cache_entry: Optional[dict]) -> Any:
        if song.gap_info and song.gap_info.is_normalized:
            return 1
        return 0


class StatusColumn:
    """Column 11: Processing status."""

    @property
    def column_index(self) -> int:
        return 11

    def format_display(self, song: Song, cache_entry: Optional[dict]) -> str:
        return song.status.name

    def get_sort_key(self, song: Song, cache_entry: Optional[dict]) -> Any:
        return song.status.name
