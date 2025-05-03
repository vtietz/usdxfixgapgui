import logging
import os
from typing import List
from common.actions.base_actions import BaseActions
from common.actions.audio_actions import AudioActions
from model.song import Song
from utils.run_async import run_sync
from workers.reload_song_worker import ReloadSongWorker
from workers.load_usdx_files import LoadUsdxFilesWorker

logger = logging.getLogger(__name__)

class SongActions(BaseActions):
    """Song selection and management actions"""

    def set_selected_songs(self, songs: List[Song]):
        logger.debug(f"Setting selected songs: {[s.title for s in songs]}")
        self.data.selected_songs = songs
        if songs:
            # Create waveforms for the first selected song for preview
            audio_actions = AudioActions(self.data)
            audio_actions._create_waveforms(songs[0])

    def reload_song(self):
        selected_songs = self.data.selected_songs
        if not selected_songs:
            logger.error("No songs selected to reload.")
            return
        logger.info(f"Reloading {len(selected_songs)} selected songs.")
        
        for song in selected_songs:
            logger.info(f"Reloading song {song.path}")
            try:
                # Extract directory from song.path (which should be the full file path)
                song_directory = os.path.dirname(song.path)
                
                # Get the tmp_root from the data object or use a default
                tmp_root = None
                if hasattr(self.data, 'tmp_directory'):
                    tmp_root = self.data.tmp_directory
                elif hasattr(song, 'tmp_root'):
                    tmp_root = song.tmp_root
                else:
                    # Use a default temporary directory if none is found
                    tmp_root = os.path.join(os.path.dirname(song_directory), "tmp")
                
                # Create the new ReloadSongWorker for this specific song reload
                worker = ReloadSongWorker(song.path, song_directory, tmp_root)
                worker.signals.songReloaded.connect(self._on_song_reloaded)
                
                # Add the task to the worker queue
                self.worker_queue.add_task(worker, True)  # True to start immediately
                
            except Exception as e:
                song.error_message = str(e)
                logger.exception(f"Error setting up song reload: {e}")
                self.data.songs.updated.emit(song)

    def _on_song_reloaded(self, reloaded_song):
        """Handle a reloaded song from the worker"""
        # Find the matching song in our data model
        for i, song in enumerate(self.data.songs):
            if song.path == reloaded_song.path:
                # Instead of replacing the song object, update its attributes
                # This avoids 'Songs' object does not support item assignment error
                self._update_song_attributes(song, reloaded_song)
                
                # Recreate waveforms for the reloaded song
                audio_actions = AudioActions(self.data)
                audio_actions._create_waveforms(song, True)
                
                # Notify update after successful reload
                self.data.songs.updated.emit(song)
                
                # If this was a selected song, update the selection
                if song in self.data.selected_songs:
                    # No need to replace in the selection array since we modified the object in-place
                    # Just refresh the selection to trigger UI updates
                    self.set_selected_songs(self.data.selected_songs)
                
                logger.info(f"Successfully reloaded song: {song.title}")
                break

    def _update_song_attributes(self, target_song, source_song):
        """Transfer all relevant attributes from source_song to target_song"""
        # Copy all attributes from source to target song object
        attributes_to_copy = [
            'title', 'artist', 'audio', 'gap', 'bpm', 'start', 'is_relative',
            'path', 'txt_file', 'audio_file', 'relative_path', 'tmp_path',
            'duration_ms', 'audio_waveform_file', 'vocals_file', 'vocals_waveform_file', 
            'vocals_duration_ms', 'status', 'error_message', 'usdb_id'
        ]
        
        for attr in attributes_to_copy:
            if hasattr(source_song, attr):
                setattr(target_song, attr, getattr(source_song, attr))
        
        # Handle special objects like gap_info
        if hasattr(source_song, 'gap_info') and source_song.gap_info:
            target_song.gap_info = source_song.gap_info

    def delete_selected_song(self):
        selected_songs = self.data.selected_songs
        if not selected_songs:
            logger.error("No songs selected to delete.")
            return
        logger.info(f"Attempting to delete {len(selected_songs)} songs.")
        # Confirmation should happen in the UI layer (MenuBar) before calling this
        songs_to_remove = list(selected_songs) # Copy list as we modify the source
        for song in songs_to_remove:
            logger.info(f"Deleting song {song.path}")
            try:
                song.delete() # Assuming song.delete() handles file/folder removal
                self.data.songs.remove(song) # Remove from the model's list
            except Exception as e:
                logger.error(f"Failed to delete song {song.path}: {e}")

        # After attempting deletion, clear the selection
        self.set_selected_songs([])
        # Explicitly trigger a list change signal
        self.data.songs.list_changed()
