import os
import logging
from PySide6.QtCore import Signal
from model.song import Song
from services.song_service import SongService
from managers.worker_queue_manager import IWorker, IWorkerSignals
from common.database import get_all_cache_entries, cleanup_stale_entries

logger = logging.getLogger(__name__)

class WorkerSignals(IWorkerSignals):
    songLoaded = Signal(Song)
    songsLoadedBatch = Signal(list)  # Batch signal for better performance
    cacheCleanup = Signal(int)  # Signal to report stale cache entries cleaned up

class LoadUsdxFilesWorker(IWorker):
    def __init__(self, directory, tmp_root):
        super().__init__()
        self.signals = WorkerSignals()
        self.directory = directory
        self.tmp_root = tmp_root
        self.description = f"Loading songs from cache and searching in {directory}."
        self.path_usdb_id_map = {}
        self.loaded_paths = set()  # Track files we've loaded to detect stale cache entries
        self.reload_single_file = None  # Path to single file to reload (when used for reload)
        self.song_service = SongService()  # Create song service

        # Batching for performance
        self.batch_size = 50  # Emit songs in batches of 50
        self.current_batch = []

    def _add_to_batch(self, song: Song):
        """Add song to batch and emit if batch is full."""
        self.current_batch.append(song)
        if len(self.current_batch) >= self.batch_size:
            self._flush_batch()

    def _flush_batch(self):
        """Emit current batch of songs."""
        if self.current_batch:
            self.signals.songsLoadedBatch.emit(self.current_batch.copy())
            self.current_batch.clear()

    async def load(self, txt_file_path, force_reload=False) -> Song:
        """Load a song from file, optionally forcing reload."""
        self.description = f"Loading file {txt_file_path}"

        # Check for cancellation before loading
        if self.is_cancelled():
            return None

        try:
            # Use the service to load the song with proper argument order:
            # load_song(txt_file, force_reload, cancel_check)
            song = await self.song_service.load_song(txt_file_path, force_reload, self.is_cancelled)
            song.usdb_id = self.path_usdb_id_map.get(song.path, None)
            return song

        except Exception as e:
            # Create minimal song data for error reporting
            song = Song(txt_file_path)
            song.set_error(str(e))
            logger.error(f"Error loading song '{txt_file_path}")
            logger.exception(e)
            return song

    async def load_from_cache(self):
        """Load all songs from the cache database first."""
        self.description = f"Loading songs from cache."
        logger.info("Loading songs from cache")

        deserialized_songs = get_all_cache_entries(deserialize=True)
        logger.info(f"Found {len(deserialized_songs)} cached songs")

        for file_path, song in deserialized_songs.items():
            if self.is_cancelled():
                self._flush_batch()  # Flush any remaining songs
                return

            # Ensure path exists and song is valid
            if not hasattr(song, 'path') or not os.path.exists(file_path):
                continue

            # Update USDB ID if needed
            song.usdb_id = self.path_usdb_id_map.get(song.path, song.usdb_id)

            # Add to batch instead of emitting individually
            self._add_to_batch(song)
            self.loaded_paths.add(file_path)
            self.signals.progress.emit()

        # Flush any remaining songs in batch
        self._flush_batch()

    async def scan_directory(self):
        """Scan directory for new or changed songs."""
        self.description = f"Scanning for new or changed songs in {self.directory}"
        logger.info(f"Scanning directory {self.directory} for new or changed songs")

        for root, dirs, files in os.walk(self.directory):
            self.description = f"Searching song files in {root}"
            if self.is_cancelled():
                self._flush_batch()  # Flush any remaining songs
                return

            # First, check if this directory has a .usdb file to extract song_id
            for file in files:
                if file.endswith(".usdb") and root not in self.path_usdb_id_map:
                    # Parse .usdb JSON file to extract song_id
                    usdb_file_path = os.path.join(root, file)
                    try:
                        import json
                        with open(usdb_file_path, 'r', encoding='utf-8') as f:
                            usdb_data = json.load(f)
                            if 'song_id' in usdb_data:
                                self.path_usdb_id_map[root] = usdb_data['song_id']
                                logger.debug(f"Found USDB ID {usdb_data['song_id']} in {root}")
                    except Exception as e:
                        logger.warning(f"Failed to parse .usdb file {usdb_file_path}: {e}")
                    break  # Only process one .usdb file per directory

            # Then, process .txt files
            for file in files:
                # Check for cancellation on every file
                if self.is_cancelled():
                    self._flush_batch()  # Flush any remaining songs
                    return

                if file.endswith(".txt"):
                    # Check for cancellation again before heavy operation
                    if self.is_cancelled():
                        self._flush_batch()  # Flush any remaining songs
                        return

                    song_path = os.path.join(root, file)

                    # If already loaded from cache, skip
                    if song_path in self.loaded_paths:
                        continue

                    song = await self.load(song_path)
                    if song:
                        self._add_to_batch(song)  # Add to batch instead of emitting
                        self.loaded_paths.add(song_path)

                self.signals.progress.emit()

            self.signals.progress.emit()

        # Flush any remaining songs in batch
        self._flush_batch()

    async def cleanup_cache(self):
        """Clean up stale cache entries."""
        self.description = "Cleaning up stale cache entries"
        logger.info("Cleaning up stale cache entries")

        stale_entries_removed = cleanup_stale_entries(self.loaded_paths)
        self.signals.cacheCleanup.emit(stale_entries_removed)

    async def run(self):
        logger.debug(self.description)

        # If this is a single file reload operation
        if self.reload_single_file:
            self.description = f"Reloading song {self.reload_single_file}"
            logger.info(f"Reloading song: {self.reload_single_file}")

            song = await self.load(self.reload_single_file, force_reload=True)
            if song:
                self.signals.songLoaded.emit(song)
                self.loaded_paths.add(song.txt_file)  # Changed from song.path to song.txt_file

            self.signals.finished.emit()
            return

        # Regular operation - loading all songs
        # First scan directory (also populates usdb_id map incrementally)
        await self.scan_directory()

        # Then load from cache for songs that were already scanned
        await self.load_from_cache()

        # Finally clean up stale cache entries
        await self.cleanup_cache()

        # Flush any remaining songs in batch (safety net)
        self._flush_batch()

        # Always emit finished signal, even if cancelled
        self.signals.finished.emit()
        if self.is_cancelled():
            logger.debug("Song loading cancelled.")
        else:
            logger.debug("Finished loading songs.")
