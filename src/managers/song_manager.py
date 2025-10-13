import os
import logging
from typing import List
from base_manager import BaseManager
from model.song import Song, SongStatus
from workers.load_usdx_files import LoadUsdxFilesWorker
from utils.run_async import run_sync

logger = logging.getLogger(__name__)

class SongManager(BaseManager):
    """Manages song loading, selection, and manipulation"""

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

    def _clear_songs(self):
        logger.debug("Clearing song list")
        self.data.songs.clear()

    def _load_songs(self):
        logger.info(f"Loading songs from directory: {self.data.directory}")
        worker = LoadUsdxFilesWorker(self.data.directory, self.data.tmp_path)
        worker.signals.songLoaded.connect(self._on_song_loaded)
        worker.signals.finished.connect(self._on_loading_songs_finished)
        self.worker_queue.add_task(worker, True)

    def _on_song_loaded(self, song: Song):
        self.data.songs.add(song)
        if song.status == SongStatus.NOT_PROCESSED:
            song.gap_info.original_gap = song.gap
            # We'll let the GapProcessor handle detection logic

    def _on_loading_songs_finished(self):
        self.data.is_loading_songs = False

    def set_selected_songs(self, songs: List[Song]):
        logger.debug(f"Setting selected songs: {[s.title for s in songs]}")
        self.data.selected_songs = songs

        # Notify other components of selection change
        if hasattr(self.data, 'selection_changed'):
            self.data.selection_changed.emit()

    def reload_song(self):
        selected_songs = self.data.selected_songs
        if not selected_songs:
            logger.error("No songs selected to reload.")
            return
        logger.info(f"Reloading {len(selected_songs)} selected songs.")
        for song in selected_songs:
            logger.info(f"Reloading song {song.path}")
            try:
                # Force reload to bypass cache and ensure all data is refreshed
                run_sync(song.load(force_reload=True))

                # Notify update after successful reload
                self.data.songs.updated.emit(song)

                # Ensure UI gets refreshed
                if hasattr(self.data.songs, 'list_changed'):
                    self.data.songs.list_changed()

            except Exception as e:
                song.error_message = str(e)
                logger.exception(e)
                self.data.songs.updated.emit(song) # Notify update even on error

    def delete_selected_song(self):
        selected_songs = self.data.selected_songs
        if not selected_songs:
            logger.error("No songs selected to delete.")
            return
        logger.info(f"Attempting to delete {len(selected_songs)} songs.")
        # Confirmation should happen in the UI layer (MenuBar) before calling this
        songs_to_remove = list(selected_songs) # Copy list as we modify the source
        for song in songs_to_remove:
            logger.info(f"Deleting song {song}")
            try:
                song.delete() # Assuming song.delete() handles file/folder removal
                self.data.songs.remove(song) # Remove from the model's list
            except Exception as e:
                logger.error(f"Failed to delete song {song}: {e}")

        # After attempting deletion, clear the selection
        self.set_selected_songs([])
        # Explicitly trigger a list change signal if model doesn't auto-signal on remove
        self.data.songs.list_changed() # Assuming Songs model has such a signal or method
