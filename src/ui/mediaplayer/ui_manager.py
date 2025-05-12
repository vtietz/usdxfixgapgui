import logging
from PySide6.QtWidgets import QPushButton, QLabel
from model.song import Song, SongStatus
import utils.audio as audio
import utils.usdx as usdx

from views.mediaplayer.constants import AudioFileStatus

logger = logging.getLogger(__name__)

class UIManager:
    def __init__(self, config):
        self._config = config
        self._play_position = 0
    
    def setup(self, buttons, labels, waveform_widget):
        """Set up references to UI elements"""
        self.play_btn = buttons['play']
        self.audio_btn = buttons['audio']
        self.vocals_btn = buttons['vocals']
        self.save_current_play_position_btn = buttons['save_position']
        self.save_detected_gap_btn = buttons['save_detected']
        self.keep_original_gap_btn = buttons['keep_original']
        self.revert_btn = buttons['revert']
        
        self.position_label = labels['position']
        self.syllable_label = labels['syllable']
        
        self.waveform_widget = waveform_widget
    
    def update_button_states(self, song, audio_status, is_media_loaded, is_playing):
        """Update all button states based on current conditions"""
        is_enabled = song is not None and not (song.status == SongStatus.PROCESSING)
        
        self.save_current_play_position_btn.setEnabled(is_enabled and self._play_position > 0)
        self.save_detected_gap_btn.setEnabled(is_enabled and song.gap_info.detected_gap > 0 if song else False)
        self.keep_original_gap_btn.setEnabled(is_enabled)
        self.play_btn.setEnabled(is_enabled and (is_media_loaded or is_playing))
        self.vocals_btn.setEnabled(is_enabled)
        self.audio_btn.setEnabled(is_enabled)
        self.revert_btn.setEnabled(is_enabled and song.gap != song.gap_info.original_gap if song else False)
        
        if song:
            self.save_detected_gap_btn.setText(f"Save detected gap ({song.gap_info.detected_gap} ms)")
            self.keep_original_gap_btn.setText(f"Keep gap ({song.gap} ms)")
            self.revert_btn.setText(f"Revert gap ({song.gap_info.original_gap} ms)")
        else:
            self.save_detected_gap_btn.setText(f"Save detected gap (0 ms)")
            self.keep_original_gap_btn.setText(f"Save gap (0 ms)")
            self.revert_btn.setText(f"Revert gap (0 ms)")
            
        self.audio_btn.setChecked(audio_status == AudioFileStatus.AUDIO)
        self.vocals_btn.setChecked(audio_status == AudioFileStatus.VOCALS)
        self.waveform_widget.overlay.setVisible(is_enabled and (is_media_loaded or is_playing))
    
    def set_playback_state(self, is_playing):
        """Update UI for play/pause state"""
        self.play_btn.setChecked(is_playing)
        # Update button text based on playback state
        self.play_btn.setText("Stop" if is_playing else "Play")
    
    def update_position_label(self, position, is_media_loaded, is_playing):
        """Update the position label with the current playback position"""
        self._play_position = position
        
        if not is_media_loaded and not is_playing:
            self.position_label.setText("")
            return
        
        playposition_text = audio.milliseconds_to_str(position)
        self.position_label.setText(playposition_text)
        self.save_current_play_position_btn.setText(f"Save play position ({position} ms)")
    
    def update_syllable_label(self, position, song):
        """Update the syllable label with the current lyric"""
        if not song or song.status == SongStatus.PROCESSING:
            self.syllable_label.setText("")
            return
        
        # Check if song has notes attribute
        if not hasattr(song, 'notes') or song.notes is None:
            self.syllable_label.setText("")
            return
            
        syllable = usdx.get_syllable(song.notes, position, song.bpm, song.gap)
        self.syllable_label.setText(syllable)
    
    def handle_multiple_selection(self, is_multiple):
        """Handle UI state for multiple song selection"""
        if is_multiple:
            self.position_label.setText("Player disabled (multiple songs selected)")
            self.syllable_label.setText("")
        else:
            self.position_label.setText("")
