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
                logger.warning(f"Last directory in config is invalid or no longer exists: '{self.config.last_directory}'")
            else:
                logger.info("No previous directory found in configuration")
            return False

    def set_directory(self, directory: str):
        if not directory or not os.path.isdir(directory):
            logger.error(f"Cannot set invalid directory: {directory}")
            return
            
        logger.info(f"Setting directory to: {directory}")
        self.data.directory = directory
        
        # Save this directory as the last used directory in config
        self.config.last_directory = directory
        self.config.save()
        logger.debug(f"Saved last directory to config: {directory}")
        
        self._clear_songs()
        self._load_songs()

    def _clear_songs(self):  # Fixed typo in method name
        logger.debug("Clearing song list")
        self.data.songs.clear()

    def _load_songs(self):
        logger.info(f"Loading songs from directory: {self.data.directory}")
        worker = LoadUsdxFilesWorker(self.data.directory, self.data.tmp_path)
        worker.signals.songLoaded.connect(self._on_song_loaded)
        worker.signals.songsLoadedBatch.connect(self._on_songs_batch_loaded)  # Connect batch handler
        worker.signals.error.connect(lambda e: logger.error(f"Error loading songs: {e}"))
        worker.signals.finished.connect(self._on_loading_songs_finished)
        self.worker_queue.add_task(worker, True)
    
    def _on_songs_batch_loaded(self, songs: list):
        """Handle batch of songs loaded - much faster than one-by-one."""
        logger.info(f"Batch loading {len(songs)} songs")
        # Set original gap for all songs
        for song in songs:
            if song.status == SongStatus.NOT_PROCESSED and song.gap_info:
                song.gap_info.original_gap = song.gap
        
        # Use bulk add for better performance
        self.data.songs.add_batch(songs)

    def _on_song_loaded(self, song: Song):
        """Handle individual song loaded (for single file reloads)."""
        self.data.songs.add(song)
        if song.status == SongStatus.NOT_PROCESSED:
            song.gap_info.original_gap = song.gap
            # Only run auto-detection for single file loads, not bulk loads
            # Auto-detection works with any configured method (spleeter, vad_preview, etc.)
            if hasattr(self, '_is_bulk_load') and not self._is_bulk_load:
                from actions.gap_actions import GapActions
                gap_actions = GapActions(self.data)
                gap_actions._detect_gap(song)
    
    def _on_loading_songs_finished(self):
        self.data.is_loading_songs = False
