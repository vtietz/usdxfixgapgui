import os
from PySide6.QtCore import QObject, Signal, Property
from typing import List, Optional # Import List and Optional
from common.config import Config  # This was from config import Config
from model.song import Song
from model.songs import Songs
from utils import files
from managers.worker_queue_manager import WorkerQueueManager

class AppData(QObject):

    # Added missing signal
    selected_song_changed = Signal(object)

    # Lazy-loaded to avoid creating Config() at module import time
    # (prevents creating config.ini with defaults during test runs)
    _config_instance: Optional[Config] = None

    songs: Songs = Songs()

    _selected_songs: List[Song] = [] # Use List[Song] for type hint
    _is_loading_songs: bool = False

    selected_songs_changed = Signal(list)  # Signal still uses list
    is_loading_songs_changed = Signal(bool)

    # Track B: State facades for selected song
    gap_state: Optional['GapState'] = None  # Forward ref to avoid circular import
    audio_service: Optional['AudioService'] = None

    # Add these new signals to support manager communication
    gap_detection_finished = Signal(object)  # Emits the song when gap detection is finished
    gap_updated = Signal(object)             # Emits the song when gap value is updated
    gap_reverted = Signal(object)            # Emits the song when gap value is reverted
    selection_changed = Signal()             # Emits when song selection changes

    # Add this signal
    media_files_refreshed = Signal()
    # New: request UI to unload any loaded media (prevents Windows file locks during normalization)
    media_unload_requested = Signal()

    _directory = None  # Will be set in __init__ after config is loaded
    _tmp_path = None   # Will be set in __init__ after config is loaded

    @property
    def config(self) -> Config:
        """Lazy-load config to avoid creating it at module import time."""
        if AppData._config_instance is None:
            AppData._config_instance = Config()
        return AppData._config_instance

    @config.setter
    def config(self, value: Config):
        """Allow setting config (used by tests)."""
        AppData._config_instance = value

    def __init__(self, config=None):
        super().__init__()  # Add this line if it's missing
        # Use provided config or the lazy-loaded class attribute
        if config is not None:
            self.config = config

        # Initialize directory from config (now that config is loaded)
        if self._directory is None:
            self._directory = self.config.default_directory
            self._tmp_path = files.generate_directory_hash(self._directory)

        # Initialize the worker queue
        self.worker_queue = WorkerQueueManager()

        # Track files locked for processing to prevent UI from reloading them (Windows file-lock mitigation)
        self._processing_locked_files = set()

    @Property(list, notify=selected_songs_changed)  # Property still uses list
    def selected_songs(self):
        return self._selected_songs

    @selected_songs.setter
    def selected_songs(self, value: List[Song]): # Use List[Song] for type hint
        if self._selected_songs != value:
            old_first = self._selected_songs[0] if self._selected_songs else None
            new_first = value[0] if value else None
            self._selected_songs = value
            self.selected_songs_changed.emit(self._selected_songs)
            # Emit selected_song_changed when the first song changes
            if old_first != new_first:
                self.selected_song_changed.emit(new_first)

    @Property(Song, notify=selected_songs_changed) # New property for first selected song
    def first_selected_song(self):
        return self._selected_songs[0] if self._selected_songs else None

    @Property(bool, notify=is_loading_songs_changed)  # Updated
    def is_loading_songs(self):
        return self._is_loading_songs

    @is_loading_songs.setter
    def is_loading_songs(self, value: bool):
        if self._is_loading_songs != value:
            self._is_loading_songs = value
            self.is_loading_songs_changed.emit(self._is_loading_songs)

    @property
    def directory(self):
        return self._directory

    @directory.setter
    def directory(self, value: str):
        self._directory = value
        path_hash = files.generate_directory_hash(value)
        self._tmp_path = os.path.join(self.config.tmp_root, path_hash)

    @property
    def tmp_path(self):
        return self._tmp_path

    # Processing lock management (prevents media player from re-opening files during background operations)
    def lock_file(self, path: str):
        """Mark a file as locked for processing to prevent UI reloads."""
        if not path:
            return
        try:
            abs_path = os.path.abspath(path)
        except Exception:
            abs_path = path
        self._processing_locked_files.add(abs_path)

    def unlock_file(self, path: str):
        """Remove a file from the processing lock set."""
        if not path:
            return
        try:
            abs_path = os.path.abspath(path)
        except Exception:
            abs_path = path
        self._processing_locked_files.discard(abs_path)

    def is_file_locked(self, path: str) -> bool:
        """Check if a file is currently locked for processing."""
        if not path:
            return False
        try:
            abs_path = os.path.abspath(path)
        except Exception:
            abs_path = path
        return abs_path in self._processing_locked_files

    def clear_file_locks_for_song(self, song: Song):
        """Convenience: clear locks for all media files associated with a song."""
        if not song:
            return
        # Audio file
        if hasattr(song, "audio_file") and song.audio_file:
            self.unlock_file(song.audio_file)
        # Vocals file may exist depending on processing pipeline
        # Avoid strict dependency on services here; let callers supply more specific paths if needed.
