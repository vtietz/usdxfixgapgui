import logging
import os
from actions.base_actions import BaseActions
from model.song import Song, SongStatus
from workers.load_usdx_files import LoadUsdxFilesWorker

logger = logging.getLogger(__name__)


class CoreActions(BaseActions):
    """Core application actions like directory management and song loading"""

    def auto_load_last_directory(self):
        """Check and auto-load songs from the last directory if available"""
        if self.config.last_directory and os.path.isdir(self.config.last_directory):
            logger.info(f"Auto-loading songs from last directory: {self.config.last_directory}")
            # Set the directory in the data model first
            self.data.directory = self.config.last_directory
            # Then load songs from it
            self._clear_songs()
            self._load_songs()
            return True
        else:
            if self.config.last_directory:
                logger.warning(
                    f"Last directory in config is invalid or no longer exists: '{self.config.last_directory}'"
                )
            else:
                logger.info("No previous directory found in configuration")
            return False

    def set_directory(self, directory: str):
        if not directory or not os.path.isdir(directory):
            logger.error(f"Cannot set invalid directory: {directory}")
            return

        logger.info(f"Setting directory to: {directory}")
        old_directory = self.data.directory
        self.data.directory = directory

        # Save this directory as the last used directory in config
        logger.debug(f"Before save: config.last_directory = '{self.config.last_directory}'")
        self.config.last_directory = directory
        logger.debug(f"After assignment: config.last_directory = '{self.config.last_directory}'")
        self.config.save()
        logger.info(f"Saved last directory to config: {directory}")

        # Don't clear songs - keep them in cache
        # Instead, trigger filter update to show only songs from new directory
        self.data.songs.filterChanged.emit()

        # Only load songs if they're not already in cache
        self._load_songs_if_needed()

    def _clear_songs(self):  # Fixed typo in method name
        logger.debug("Clearing song list")
        self.data.songs.clear()

    def _load_songs_if_needed(self):
        """Load songs from current directory, but only if not already in cache"""
        import os

        current_dir = self.data.directory
        if not current_dir:
            logger.warning("No directory set, cannot load songs")
            return

        # Check which songs from current directory are already cached
        cached_paths = {os.path.normpath(song.path).lower() for song in self.data.songs.songs}
        logger.debug(f"Found {len(cached_paths)} songs already in cache")

        # Quick check: if we have songs from this directory, we might not need to scan
        current_dir_normalized = os.path.normpath(current_dir).lower()
        has_songs_from_dir = any(path.startswith(current_dir_normalized) for path in cached_paths)

        if has_songs_from_dir:
            logger.info(f"Songs from {current_dir} already in cache, skipping full scan")
            # Still load to catch any new songs, but mark as incremental
            self._load_songs(incremental=True)
        else:
            logger.info(f"No cached songs from {current_dir}, loading all")
            self._load_songs(incremental=False)

    def _load_songs(self, incremental=False):
        logger.info(f"Loading songs from directory: {self.data.directory} (incremental: {incremental})")
        self.data.is_loading_songs = True  # Set loading flag immediately
        worker = LoadUsdxFilesWorker(self.data.directory, self.data.tmp_path, self.data.config)
        worker.signals.songLoaded.connect(self._on_song_loaded)
        worker.signals.songsLoadedBatch.connect(self._on_songs_batch_loaded)  # Connect batch handler
        worker.signals.error.connect(lambda e: logger.error(f"Error loading songs: {e}"))
        worker.signals.finished.connect(self._on_loading_songs_finished)
        self.worker_queue.add_task(worker, True)

    def _on_songs_batch_loaded(self, songs: list):
        """Handle batch of songs loaded - much faster than one-by-one."""
        logger.debug(f"Batch loading {len(songs)} songs")

        # Filter out songs already in cache (by txt_file path)
        existing_paths = {song.txt_file for song in self.data.songs.songs if hasattr(song, 'txt_file')}
        new_songs = [song for song in songs if song.txt_file not in existing_paths]

        if len(new_songs) < len(songs):
            logger.debug(f"Skipped {len(songs) - len(new_songs)} songs already in cache")

        if not new_songs:
            logger.debug("All songs already in cache, nothing to add")
            return

        # Set original gap for new songs only
        for song in new_songs:
            if song.status == SongStatus.NOT_PROCESSED and song.gap_info:
                if hasattr(song.gap_info, "original_gap"):  # Type guard
                    song.gap_info.original_gap = song.gap

        # Use bulk add for better performance
        self.data.songs.add_batch(new_songs)
        logger.debug(f"Added {len(new_songs)} new songs to cache")

    def _on_song_loaded(self, song: Song):
        """Handle individual song loaded (for single file reloads)."""
        self.data.songs.add(song)
        if song.status == SongStatus.NOT_PROCESSED and song.gap_info:
            if hasattr(song.gap_info, "original_gap"):  # Type guard
                song.gap_info.original_gap = song.gap
        # Only run auto-detection for single file loads, not bulk loads
        # Auto-detection uses MDX (only supported method)
        is_bulk_load = getattr(self, "_is_bulk_load", False)  # Safe attribute access
        if not is_bulk_load:
            from actions.gap_actions import GapActions

            gap_actions = GapActions(self.data)
            gap_actions._detect_gap(song)

    def _on_loading_songs_finished(self):
        self.data.is_loading_songs = False
