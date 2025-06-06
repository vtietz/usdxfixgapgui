from app.app_data import AppData
from common.actions.base_actions import BaseActions
from common.actions.core_actions import CoreActions
from common.actions.song_actions import SongActions
from common.actions.gap_actions import GapActions
from common.actions.audio_actions import AudioActions
from common.actions.ui_actions import UiActions

class Actions(BaseActions):
    """Main actions class that combines all action modules"""
    
    def __init__(self, data: AppData):
        super().__init__(data)
        
        # Create specialized action instances
        self._core_actions = CoreActions(data)
        self._song_actions = SongActions(data)
        self._gap_actions = GapActions(data)
        self._audio_actions = AudioActions(data)
        self._ui_actions = UiActions(data)
        
    # Core Actions
    def auto_load_last_directory(self):
        return self._core_actions.auto_load_last_directory()
    
    def set_directory(self, directory: str):
        self._core_actions.set_directory(directory)
    
    # Song Actions    
    def set_selected_songs(self, songs):
        self._song_actions.set_selected_songs(songs)
        
    def reload_song(self, specific_song=None):
        self._song_actions.reload_song(specific_song)

    def delete_selected_song(self):
        self._song_actions.delete_selected_song()
    
    # Gap Actions
    def detect_gap(self, overwrite=False):
        self._gap_actions.detect_gap(overwrite)
        
    def get_notes_overlap(self, song, silence_periods, detection_time):
        self._gap_actions.get_notes_overlap(song, silence_periods, detection_time)
    
    def update_gap_value(self, song, gap):
        self._gap_actions.update_gap_value(song, gap)
        
    def revert_gap_value(self, song):
        self._gap_actions.revert_gap_value(song)
        
    def keep_gap_value(self, song):
        self._gap_actions.keep_gap_value(song)
    
    # Audio Actions
    def normalize_song(self):
        self._audio_actions.normalize_song()
    
    # UI Actions
    def open_usdx(self):
        self._ui_actions.open_usdx()
        
    def open_folder(self):
        return self._ui_actions.open_folder()
