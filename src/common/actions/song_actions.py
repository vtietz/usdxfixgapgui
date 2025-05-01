import logging
import os
from typing import List
from common.actions.base_actions import BaseActions
from common.actions.audio_actions import AudioActions
from model.song import Song
from utils.run_async import run_sync

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

    def select_song(self, path: str):
        logger.warning("select_song(path) called, consider using set_selected_songs(list[Song])")
        song: Song = next((s for s in self.data.songs if s.path == path), None)
        if song:
            self.set_selected_songs([song])
        else:
            self.set_selected_songs([])

    def reload_song(self):
        selected_songs = self.data.selected_songs
        if not selected_songs:
            logger.error("No songs selected to reload.")
            return
        logger.info(f"Reloading {len(selected_songs)} selected songs.")
        
        audio_actions = AudioActions(self.data)
        
        for song in selected_songs:
            logger.info(f"Reloading song {song.path}")
            try:
                # Force reload to bypass cache and ensure all data is refreshed
                run_sync(song.load(force_reload=True))
                
                # Make sure audio durations are correct
                if song.audio_file and os.path.exists(song.audio_file):
                    audio_actions._get_audio_length(song)
                
                # Recreate waveform after reload
                audio_actions._create_waveforms(song, True)
                
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
