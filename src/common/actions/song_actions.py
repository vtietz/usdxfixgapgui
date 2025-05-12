import logging
import os
from typing import List
from common.actions.base_actions import BaseActions
from app.app_data import AppData
from model.song import Song
from utils import audio
from workers.reload_song_worker import ReloadSongWorker
from services.usdx_file_service import USDXFileService
from model.usdx_file import USDXFile
from utils.run_async import run_async
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices

logger = logging.getLogger(__name__)

class SongActions(BaseActions):
    """Song selection, management, and UI interaction actions"""

    def __init__(self, data: AppData):
        super().__init__(data)
        self.data.songs.updated.connect(self.reload_song)

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
                worker.signals.songReloaded.connect(self._on_song_reloaded)
                
                # Add the task to the worker queue
                self.worker_queue.add_task(worker, True)  # True to start immediately
                
            except Exception as e:
                song.error_message = str(e)
                logger.exception(f"Error setting up song reload: {e}")
                self.data.songs.updated.emit(song)

    def load_notes_for_song(self, song: Song):
        """Load just the notes for a song without fully reloading it"""
        if not song:
            logger.error("No song provided to load notes for")
            return
            
        logger.info(f"Loading notes for {song}")
        
        async def load_notes_async():
            try:
                # Use USDXFile and USDXFileService directly to load just the notes
                usdx_file = USDXFile(song.txt_file)
                notes = await USDXFileService.load_notes_only(usdx_file)
                
                # Update the song with the loaded notes
                song.notes = notes
                logger.debug(f"Notes loaded for song: {song.title}, count: {len(song.notes) if song.notes else 0}")
                
                # Notify that the song was updated
                self.data.songs.updated.emit(song)
                
            except Exception as e:
                logger.error(f"Error loading notes for song {song.title}: {e}", exc_info=True)
                song.error_message = str(e)
                self.data.songs.updated.emit(song)
        
        # Run the async function properly
        run_async(load_notes_async())

    def _on_song_reloaded(self, reloaded_song):
        """Handle a reloaded song from the worker"""
        logging.debug(f"Reloaded song: {reloaded_song}")
        # Find the matching song in our data model
        for i, song in enumerate(self.data.songs):
            if song.path == reloaded_song.path:
                # Instead of replacing the song object, update its attributes
                self._update_song_attributes(song, reloaded_song)
                
                # Ensure note timings are properly calculated with the current gap value
                self._ensure_note_times_calculated(song)
                
                # Always recreate waveforms after reload to ensure they reflect current state
                self._create_waveforms_for_song(song)
                
                # Notify update after successful reload
                self.data.songs.updated.emit(song)
                
                logger.info(f"Successfully reloaded {song}")
                break
    
    def _ensure_note_times_calculated(self, song: Song):
        """Ensure note timings are properly calculated"""
        if hasattr(song, 'usdx_file') and song.usdx_file:
            try:
                # Recalculate note timings based on current gap value
                logger.debug(f"Recalculating note times with gap: {song.gap}")
                song.usdx_file.calculate_note_times()
            except Exception as e:
                logger.error(f"Error calculating note times: {e}")
    
    def _create_waveforms_for_song(self, song: Song):
        """Create waveforms for the given song"""
        try:
            # Import here to avoid circular imports
            from common.actions.audio_actions import AudioActions
            audio_actions = AudioActions(self.data)
            
            # Force waveform recreation
            logger.debug(f"Creating waveforms for {song}")
            audio_actions._create_waveforms(song, True)
        except Exception as e:
            logger.error(f"Error creating waveforms: {e}")

    def _update_song_attributes(self, target_song: Song, source_song: Song):
        """Transfer all relevant attributes from source_song to target_song"""
        # Copy all attributes from source to target song object
        attributes_to_copy = [
            'title', 'artist', 'audio', 'gap', 'bpm', 'start', 'is_relative',
            'path', 'txt_file', 'audio_file', 'relative_path', 'usdb_id', 'notes'
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
                target_song.duration_ms = audio.get_audio_duration_ms(target_song.audio_file)
                logger.info(f"Fallback method: set duration to {target_song.duration_ms}ms from audio file")
            except Exception as e:
                logger.warning(f"Could not load duration from audio file: {e}")

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

    # UI-related actions moved from ui_actions.py
    def open_usdx(self):
        # Should only work for a single selected song
        if len(self.data.selected_songs) != 1:
            logger.error("Please select exactly one song to open in USDB.")
            return
        song: Song = self.data.first_selected_song
        if not song:
            logger.error("No song selected")
            return
        
        # More robust check for usdb_id validity
        if not song.usdb_id or song.usdb_id == "0" or song.usdb_id == "":
            logger.error(f"Song '{song.title}' has no valid USDB ID.")
            return
            
        logger.info(f"Opening USDB in web browser for {song.txt_file} with ID {song.usdb_id}")
        url = QUrl(f"https://usdb.animux.de/index.php?link=detail&id={song.usdb_id}")
        success = QDesktopServices.openUrl(url)
        
        if not success:
            logger.error(f"Failed to open URL: {url.toString()}")

    def open_folder(self):
        # Opens the folder of the first selected song
        song: Song = self.data.first_selected_song
        if not song:
            logger.error("No song selected to open folder.")
            return
        logger.info(f"Opening folder for {song.path}")
        url = QUrl.fromLocalFile(song.path)
        if not QDesktopServices.openUrl(url):
            logger.error("Failed to open the folder.")
            return False
        return True
