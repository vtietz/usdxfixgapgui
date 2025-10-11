import logging
import os
from typing import List
from actions.base_actions import BaseActions
from model.song import Song, SongStatus
from workers.reload_song_worker import ReloadSongWorker
from services.usdx_file_service import USDXFileService
from services.song_service import SongService
from model.usdx_file import USDXFile
from utils.audio import get_audio_duration

logger = logging.getLogger(__name__)

class SongActions(BaseActions):
    """Song selection and management actions"""

    def set_selected_songs(self, songs: List[Song]):
        logger.debug(f"Setting selected songs: {[s.title for s in songs]}")
        self.data.selected_songs = songs
        # Removed waveform creation here - will be handled by MediaPlayerComponent

    def reload_song(self, specific_song=None):
        """
        Reload a song or songs from disk.
        If specific_song is provided, only loads that song.
        Otherwise loads all selected songs.
        """
        if specific_song:
            songs_to_load = [specific_song]
        else:
            songs_to_load = self.data.selected_songs
            
        if not songs_to_load:
            logger.error("No songs selected to reload.")
            return
        
        logger.info(f"Reloading {len(songs_to_load)} songs.")
        
        for song in songs_to_load:
            logger.info(f"Reloading song {song.path}")
            try:
                # Extract directory from song.path (which should be the full file path)
                song_directory = os.path.dirname(song.path)
                
                # Create the new ReloadSongWorker for this specific song reload
                worker = ReloadSongWorker(song.path, song_directory)
                worker.signals.songReloaded.connect(self._on_song_loaded)
                worker.signals.error.connect(lambda e, s=song: self._on_song_worker_error(s, e))
                
                # Add the task to the worker queue
                self.worker_queue.add_task(worker, True)  # True to start immediately
                
            except Exception as e:
                song.set_error(str(e))
                logger.exception(f"Error setting up song reload: {e}")
                self.data.songs.updated.emit(song)

    def load_notes_for_song(self, song: Song):
        """Load just the notes for a song without fully reloading it"""
        if not song:
            logger.error("No song provided to load notes for")
            return
            
        logger.info(f"Loading notes for {song}")
        
        try:
            # Use USDXFile and USDXFileService directly to load just the notes
            usdx_file = USDXFile(song.txt_file)
            song.notes = USDXFileService.load_notes_only(usdx_file)
            logger.debug(f"Notes loaded for song: {song.title}, count: {len(song.notes) if song.notes else 0}")
            
            # Notify that the song was updated
            self.data.songs.updated.emit(song)
            
        except Exception as e:
            logger.error(f"Error loading notes for song {song.title}: {e}", exc_info=True)
            song.error_message = str(e)
            self.data.songs.updated.emit(song)

    def _on_song_loaded(self, reloaded_song):
        """Handle a reloaded song from the worker"""
        # Find the matching song in our data model
        for i, song in enumerate(self.data.songs):
            if song.path == reloaded_song.path:
                # Instead of replacing the song object, update its attributes
                # This avoids 'Songs' object does not support item assignment error
                self._update_song_attributes(song, reloaded_song)
                
                # Recreate waveforms for the reloaded song
                from actions.audio_actions import AudioActions
                audio_actions = AudioActions(self.data)
                audio_actions._create_waveforms(song, True)
                
                # Notify update after successful reload
                self.data.songs.updated.emit(song)
                
                # If this was a selected song, update the selection
                if song in self.data.selected_songs:
                    # No need to replace in the selection array since we modified the object in-place
                    # Just refresh the selection to trigger UI updates
                    self.set_selected_songs(self.data.selected_songs)
                
                logger.info(f"Successfully reloaded {song}")
                break

    def _update_song_attributes(self, target_song: Song, source_song: Song):
        """Transfer all relevant attributes from source_song to target_song"""
        # Copy all attributes from source to target song object
        attributes_to_copy = [
            'title', 'artist', 'audio', 'gap', 'bpm', 'start', 'is_relative',
            'txt_file', 'audio_file', 'relative_path', 'usdb_id', 'notes'
        ]
              
        for attr in attributes_to_copy:
            if hasattr(source_song, attr):
                try:
                    # First check if the attribute is accessible via setattr
                    setattr(target_song, attr, getattr(source_song, attr))
                except AttributeError:
                    # If we can't set it directly, log this issue
                    logger.warning(f"Could not set attribute {attr} on song {target_song.title}")
        
        # Copy status and error_message after other attributes to ensure they're properly set
        if hasattr(source_song, 'status'):
            target_song.status = source_song.status
        if hasattr(source_song, 'error_message'):
            target_song.error_message = source_song.error_message
            
        # Handle special objects like gap_info
        if hasattr(source_song, 'gap_info') and source_song.gap_info:
            try:
                target_song.gap_info = source_song.gap_info
            except AttributeError:
                # If gap_info is a property with no setter, try to update its contents
                logger.warning(f"Could not set gap_info directly, attempting to update contents")
                if hasattr(target_song, 'gap_info') and target_song.gap_info is not None:
                    # Copy attributes from source gap_info to target gap_info
                    for gap_attr in dir(source_song.gap_info):
                        if not gap_attr.startswith('_') and gap_attr != 'owner':  # Skip private attributes and owner
                            try:
                                setattr(target_song.gap_info, gap_attr, 
                                        getattr(source_song.gap_info, gap_attr))
                            except AttributeError:
                                pass
                    
                    # Explicitly update duration from gap_info if available
                    if source_song.gap_info.duration:
                        target_song.duration_ms = source_song.gap_info.duration

        # Double-check duration after all other operations
        if target_song.duration_ms == 0 and target_song.audio_file and os.path.exists(target_song.audio_file):
            try:
                target_song.duration_ms = get_audio_duration(target_song.audio_file)
                logger.info(f"Fallback method: set duration to {target_song.duration_ms}ms from audio file")
            except Exception as e:
                logger.warning(f"Could not load duration from audio file: {e}")

    def delete_selected_song(self):
        """
        Delete selected songs following architecture principles:
        - Actions orchestrate between services and models
        - Services handle business logic
        - Models only update their own state via methods
        - Signals emitted through data model, not directly from actions
        """
        selected_songs = self.data.selected_songs
        if not selected_songs:
            logger.error("No songs selected to delete.")
            return
            
        logger.info(f"Attempting to delete {len(selected_songs)} songs.")
        # Confirmation should happen in the UI layer (MenuBar) before calling this
        songs_to_remove = list(selected_songs) # Copy list as we modify the source
        successfully_deleted = []
        
        # Use service for deletion logic
        song_service = SongService()
        
        for song in songs_to_remove:
            logger.info(f"Deleting song {song.path}")
            try:
                if song_service.delete_song(song):  # Service handles the deletion
                    successfully_deleted.append(song)
                    logger.info(f"Successfully deleted song {song.path}")
                else:
                    # Delete returned False - let model handle its state
                    song.set_error("Failed to delete song files")
                    self.data.songs.updated.emit(song)  # Signal via data model
                    logger.error(f"Failed to delete song {song.path}")
            except Exception as e:
                # Exception occurred - let model handle its state
                song.set_error(f"Delete error: {str(e)}")
                self.data.songs.updated.emit(song)  # Signal via data model
                logger.error(f"Exception deleting song {song.path}: {e}")
        
        # Only remove successfully deleted songs from the list
        for song in successfully_deleted:
            try:
                self.data.songs.remove(song)
            except ValueError:
                # Song was already removed somehow
                pass

        # After attempting deletion, clear the selection
        self.set_selected_songs([])
        # Explicitly trigger a list change signal
        self.data.songs.list_changed()
