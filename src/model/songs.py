import logging
import os
from typing import Dict, List, Optional, Tuple, Union
from PySide6.QtCore import QObject, Signal  # Updated import
from model.song import Song, SongStatus as _SongStatus

SongStatus = _SongStatus  # Re-export for legacy imports

logger = logging.getLogger(__name__)


def normalize_path(path: str) -> str:
    """Normalize path for consistent comparison across platforms.

    - Normalizes case (Windows case-insensitive)
    - Normalizes separators (unified forward slashes)
    - Resolves relative paths
    """
    return os.path.normcase(os.path.normpath(path)).replace('\\', '/')


class Songs(QObject):

    cleared = Signal()  # Updated
    added = Signal(Song)  # Updated
    updated = Signal(Song)  # Updated
    deleted = Signal(Song)  # Updated
    error = Signal(Song, Exception)  # Updated
    filterChanged = Signal()  # Updated
    listChanged = Signal()  # Signal for when the list structure changes
    loadingFinished = Signal()  # Signal when bulk song loading is complete

    def __init__(self):
        super().__init__()
        self.songs: List[Song] = []
        self._filter: List[str] = []
        self._filter_text: str = ""
        self._songs_by_txt: Dict[str, Song] = {}
        self._songs_by_path: Dict[str, Song] = {}

    def clear(self):
        self.songs.clear()
        self._songs_by_txt.clear()
        self._songs_by_path.clear()
        self.cleared.emit()
        self.listChanged.emit()  # Emit list changed signal

    def add(self, song: Song):
        # Check for duplicate before adding (if txt_file is available)
        existing = self._find_existing(song)
        if existing:
            song_desc = f"{getattr(song, 'artist', 'Unknown')} - {getattr(song, 'title', 'Unknown')}"
            logger.info(
                "Prevented duplicate: song already exists, updating instead of adding: %s (%s)",
                song_desc,
                song.txt_file,
            )
            self._update_song(existing, song)
            self.updated.emit(existing)
            return

        song_desc = f"{getattr(song, 'artist', 'Unknown')} - {getattr(song, 'title', 'Unknown')}"
        txt_file = getattr(song, 'txt_file', 'no_txt_file')
        logger.debug("Single add (added signal only, no listChanged): %s (%s)", song_desc, txt_file)
        self.songs.append(song)
        self._prepare_song(song)
        self.added.emit(song)
        # Don't emit listChanged for single add - prevents UI double-insert

    def add_batch(self, songs: List[Song]):
        """Add multiple songs at once - more efficient than adding one by one."""
        if not songs:
            return

        added_count = 0
        updated_count = 0
        for song in songs:
            existing = self._find_existing(song)
            if existing:
                self._update_song(existing, song)
                updated_count += 1
                continue

            self.songs.append(song)
            self._prepare_song(song)
            added_count += 1

        if added_count > 0 or updated_count > 0:
            # Don't emit individual 'added' signals in batch mode - only emit once at the end
            # This prevents N UI updates for N songs (massive performance win)
            # Only emit list changed once at the end
            self.listChanged.emit()

    def remove(self, song: Song):
        self.songs.remove(song)
        self._remove_index_keys(*self._snapshot_keys(song))
        self.deleted.emit(song)  # Changed from updated to deleted signal
        # Don't emit listChanged for single remove - prevents UI inconsistency

    def get_by_txt_file(self, txt_file: str) -> Song | None:
        """Get song by txt file path."""
        key = self._normalize_key(txt_file)
        if not key:
            return None
        return self._songs_by_txt.get(key)

    def get_by_path(self, path: str) -> Song | None:
        """Get song by folder path."""
        key = self._normalize_key(path)
        if not key:
            return None
        return self._songs_by_path.get(key)

    def remove_by_txt_file(self, txt_file: str) -> bool:
        """Remove song by txt file path. Returns True if removed."""
        key = self._normalize_key(txt_file)
        if key:
            song = self._songs_by_txt.get(key)
            if song:
                self.remove(song)
                return True
        return False

    def list_changed(self):
        """Manually trigger list changed signal"""
        self.listChanged.emit()

    def __len__(self):
        return len(self.songs)

    def __getitem__(self, index):
        return self.songs[index]

    @property
    def filter(self) -> List[str]:
        """Get status filter as list of status names (strings)."""
        return self._filter

    @filter.setter
    def filter(self, value: List[str]):
        """Set status filter using list of status names (strings)."""
        self._filter = value
        self.filterChanged.emit()

    @property
    def filter_text(self):
        return self._filter_text

    @filter_text.setter
    def filter_text(self, value):
        self._filter_text = value
        self.filterChanged.emit()

    def _normalize_key(self, value: Optional[Union[str, os.PathLike]]) -> Optional[str]:
        if not value:
            return None
        if isinstance(value, os.PathLike):
            value = os.fspath(value)
        if not isinstance(value, str):
            return None
        return normalize_path(value)

    def _snapshot_keys(self, song: Song) -> Tuple[Optional[str], Optional[str]]:
        txt_file = getattr(song, "txt_file", None)
        song_path = getattr(song, "path", None)
        return self._normalize_key(txt_file), self._normalize_key(song_path)

    def _remove_index_keys(self, txt_key: Optional[str], path_key: Optional[str]):
        if txt_key:
            self._songs_by_txt.pop(txt_key, None)
        if path_key:
            self._songs_by_path.pop(path_key, None)

    def _index_song(self, song: Song):
        txt_key, path_key = self._snapshot_keys(song)
        if txt_key:
            self._songs_by_txt[txt_key] = song
        if path_key:
            self._songs_by_path[path_key] = song

    def _prepare_song(self, song: Song):
        song.update_title_sort_key()
        self._index_song(song)

    def _find_existing(self, song: Song) -> Optional[Song]:
        if hasattr(song, 'txt_file') and song.txt_file:
            return self.get_by_txt_file(song.txt_file)
        return None

    def _update_song(self, target: Song, source: Song):
        old_txt_key, old_path_key = self._snapshot_keys(target)
        target.__dict__.update(source.__dict__)
        target.update_title_sort_key()
        self._rebind_gap_info_owner(target)
        self._remove_index_keys(old_txt_key, old_path_key)
        self._index_song(target)

    def _rebind_gap_info_owner(self, song: Song):
        """Ensure gap_info.owner points to the live Song instance after updates."""
        gap_info = getattr(song, "_gap_info", None)
        if not gap_info:
            return

        gap_info.owner = song
        # Re-run status mapping so UI reflects the latest gap_info.status
        song._gap_info_updated()
