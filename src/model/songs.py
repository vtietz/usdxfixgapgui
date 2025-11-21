import logging
from typing import List
from PySide6.QtCore import QObject, Signal  # Updated import
from model.song import Song, SongStatus

logger = logging.getLogger(__name__)


class Songs(QObject):

    cleared = Signal()  # Updated
    added = Signal(Song)  # Updated
    updated = Signal(Song)  # Updated
    deleted = Signal(Song)  # Updated
    error = Signal(Song, Exception)  # Updated
    filterChanged = Signal()  # Updated
    listChanged = Signal()  # Signal for when the list structure changes

    _filter: List[SongStatus] = []
    _filter_text: str = ""

    songs: List[Song] = []

    def clear(self):
        self.songs.clear()
        self.cleared.emit()
        self.listChanged.emit()  # Emit list changed signal

    def add(self, song: Song):
        # Check for duplicate before adding (if txt_file is available)
        if hasattr(song, 'txt_file') and song.txt_file:
            existing = self.get_by_txt_file(song.txt_file)
            if existing:
                song_desc = f"{getattr(song, 'artist', 'Unknown')} - {getattr(song, 'title', 'Unknown')}"
                logger.info(f"Prevented duplicate: song already exists, updating instead of adding: {song_desc} ({song.txt_file})")
                # Update the existing song's data rather than adding duplicate
                existing.__dict__.update(song.__dict__)
                self.updated.emit(existing)
                return

        song_desc = f"{getattr(song, 'artist', 'Unknown')} - {getattr(song, 'title', 'Unknown')}"
        txt_file = getattr(song, 'txt_file', 'no_txt_file')
        logger.debug(f"Adding new song to collection: {song_desc} ({txt_file})")
        self.songs.append(song)
        self.added.emit(song)
        self.listChanged.emit()  # Emit list changed signal

    def add_batch(self, songs: List[Song]):
        """Add multiple songs at once - more efficient than adding one by one."""
        if not songs:
            return

        added_count = 0
        updated_count = 0
        for song in songs:
            if hasattr(song, 'txt_file') and song.txt_file:
                existing = self.get_by_txt_file(song.txt_file)
                if existing:
                    # Update existing song instead of adding duplicate
                    existing.__dict__.update(song.__dict__)
                    updated_count += 1
                    continue

            self.songs.append(song)
            added_count += 1

        if added_count > 0 or updated_count > 0:
            logger.debug(f"Batch operation: added {added_count}, updated {updated_count} songs")
            # Don't emit individual 'added' signals in batch mode - only emit once at the end
            # This prevents N UI updates for N songs (massive performance win)
            # Only emit list changed once at the end
            self.listChanged.emit()

    def remove(self, song: Song):
        self.songs.remove(song)
        self.deleted.emit(song)  # Changed from updated to deleted signal
        self.listChanged.emit()  # Emit list changed signal

    def get_by_txt_file(self, txt_file: str) -> Song | None:
        """Get song by txt file path."""
        # Normalize paths for comparison (handle Z:/path vs Z:\\path)
        txt_file_normalized = txt_file.replace('\\', '/')
        for song in self.songs:
            song_txt_normalized = song.txt_file.replace('\\', '/')
            if song_txt_normalized == txt_file_normalized:
                return song
        return None

    def get_by_path(self, path: str) -> Song | None:
        """Get song by folder path."""
        # Normalize paths for comparison (handle Z:/path vs Z:\\path)
        path_normalized = path.replace('\\', '/')
        for song in self.songs:
            song_path_normalized = song.path.replace('\\', '/')
            if song_path_normalized == path_normalized:
                return song
        return None

    def remove_by_txt_file(self, txt_file: str) -> bool:
        """Remove song by txt file path. Returns True if removed."""
        song = self.get_by_txt_file(txt_file)
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
    def filter(self):
        return self._filter

    @filter.setter
    def filter(self, value):
        self._filter = value
        self.filterChanged.emit()

    @property
    def filter_text(self):
        return self._filter_text

    @filter_text.setter
    def filter_text(self, value):
        self._filter_text = value
        self.filterChanged.emit()
