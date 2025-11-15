import logging
import os
from actions.base_actions import BaseActions
from model.song import Song, SongStatus
from workers.load_usdx_files import LoadUsdxFilesWorker
from common.database import clear_cache

logger = logging.getLogger(__name__)


class CoreActions(BaseActions):
    """Core application actions like directory management and song loading"""

    def auto_load_last_directory(self):
        """Check and auto-load songs from the last directory if available"""
        dir_to_load = None
        if self.config.last_directory and os.path.isdir(self.config.last_directory):
            dir_to_load = self.config.last_directory
            logger.info("Auto-loading songs from last directory: %s", dir_to_load)
        elif self.config.default_directory and os.path.isdir(self.config.default_directory):
            dir_to_load = self.config.default_directory
            logger.info("Auto-loading songs from default directory: %s", dir_to_load)
        else:
            if self.config.last_directory:
                logger.warning(
                    "Last directory in config is invalid or no longer exists: '%s'", self.config.last_directory
                )
            if self.config.default_directory:
                logger.warning(
                    "Default directory in config is invalid or no longer exists: '%s'", self.config.default_directory
                )
            logger.info("No valid directory found in configuration")
            return False

        self.data.directory = dir_to_load
        self._clear_songs()
        self._load_songs()
        return True

    def set_directory(self, directory: str):
        if not directory or not os.path.isdir(directory):
            logger.error(f"Cannot set invalid directory: {directory}")
            return

        logger.info(f"Setting directory to: {directory}")
        self.data.directory = directory

        # Save this directory as the last used directory in config
        logger.debug(f"Before save: config.last_directory = '{self.config.last_directory}'")
        self.config.last_directory = directory
        logger.debug(f"After assignment: config.last_directory = '{self.config.last_directory}'")
        self.config.save()
        logger.info(f"Saved last directory to config: {directory}")

        # Clear songs and reload from new directory
        self._clear_songs()
        self._load_songs()

    def rescan_directory(self):
        """
        Re-scan the current directory with full cache invalidation.

        This clears all cached data and reloads songs fresh from disk,
        useful when files have been modified externally.
        """
        if not self.data.directory or not os.path.isdir(self.data.directory):
            logger.error("Cannot re-scan: no valid directory loaded")
            return

        logger.info(f"Re-scanning directory with cache invalidation: {self.data.directory}")

        # Clear the entire cache to force fresh parsing
        clear_cache()
        logger.info("Cache cleared for re-scan")

        # Clear songs and reload
        self._clear_songs()
        self._load_songs()

    def _clear_songs(self):  # Fixed typo in method name
        logger.debug("Clearing song list")
        self.data.songs.clear()

    def _load_songs(self):
        logger.info(f"Loading songs from directory: {self.data.directory}")
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

        # Set original gap for new songs
        for song in songs:
            if song.status == SongStatus.NOT_PROCESSED and song.gap_info:
                if hasattr(song.gap_info, "original_gap"):  # Type guard
                    song.gap_info.original_gap = song.gap

        # Use bulk add for better performance
        self.data.songs.add_batch(songs)

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
        logger.debug("Song loading finished")
