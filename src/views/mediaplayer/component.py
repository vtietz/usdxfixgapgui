import logging
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Signal, Qt

from common.actions import Actions
from common.data import AppData
from model.song import Song, SongStatus
from services.waveform_path_service import WaveformPathService

from views.mediaplayer.constants import AudioFileStatus
from views.mediaplayer.event_filter import MediaPlayerEventFilter
from views.mediaplayer.waveform_widget import WaveformWidget
from views.mediaplayer.player_controller import PlayerController
from views.mediaplayer.ui_manager import UIManager

logger = logging.getLogger(__name__)

class MediaPlayerComponent(QWidget):
    position_changed = Signal(int)
    is_playing_changed = Signal(bool)
    audio_file_status_changed = Signal(AudioFileStatus)

    globalEventFilter = None

    def __init__(self, data: AppData, actions: Actions, parent=None):
        super().__init__(parent)
        self._data = data
        self._config = data.config
        self._actions = actions
        
        # Initialize state variables
        self._song = None
        
        # Initialize controllers
        self.player = PlayerController(self._config)
        self.ui_manager = UIManager(self._config)
        
        # Initialize UI
        self.initUI()
        
        # Create event filter
        self.globalEventFilter = MediaPlayerEventFilter(
            self,
            lambda: self.player.adjust_position_left(),
            lambda: self.player.adjust_position_right(),
            lambda: self.player.play()
        )
        
        # Connect signals from player to local handlers
        self.player.position_changed.connect(self.position_changed)
        self.player.is_playing_changed.connect(self.is_playing_changed)
        self.player.audio_file_status_changed.connect(self.audio_file_status_changed)
        self.player.media_player.positionChanged.connect(self.update_position)
        self.player.media_status_changed.connect(self.update_ui)
        
        # Connect signals from self to player
        self.is_playing_changed.connect(self.on_play_state_changed)
        self.audio_file_status_changed.connect(self.on_audio_file_status_changed)
        
        # Connect to the data signals
        self._data.selected_song_changed.connect(self.on_song_changed)
        self._data.selected_songs_changed.connect(self.on_selected_songs_changed)
        self._data.songs.updated.connect(self.on_song_updated)
        self._data.songs.deleted.connect(lambda: self.player.unload_all_media())

    def initUI(self):
        # Create control buttons
        self.play_btn = QPushButton("Play")
        self.play_btn.setCheckable(True)

        self.audio_btn = QPushButton("Original Audio")
        self.audio_btn.setCheckable(True)

        self.vocals_btn = QPushButton("Extracted Vocals")
        self.vocals_btn.setCheckable(True)

        # Setup waveform
        self.waveform_widget = WaveformWidget(self)
        
        # Setup action buttons
        self.position_label = QLabel('')
        self.position_label.setStyleSheet(f"color: {self._config.playback_position_color};")
        self.keep_original_gap_btn = QPushButton("Keep original gap (0 ms)")
        self.save_current_play_position_btn = QPushButton("Save play position (0 ms)")
        self.save_detected_gap_btn = QPushButton("Save detected gap (0 ms)")
        self.revert_btn = QPushButton("Revert")

        self.syllable_label = QLabel('')
        self.syllable_label.setStyleSheet(f"color: {self._config.playback_position_color};")

        # Create layouts
        play_and_waveform_layout = QHBoxLayout()
        play_and_waveform_layout.addWidget(self.play_btn)
        play_and_waveform_layout.addWidget(self.audio_btn)
        play_and_waveform_layout.addWidget(self.vocals_btn)
        
        waveform_layout = QVBoxLayout()
        waveform_layout.setContentsMargins(0, 0, 0, 0)
        waveform_layout.addWidget(self.waveform_widget)
        
        labels = QHBoxLayout()
        labels.addWidget(self.position_label)
        labels.addWidget(self.syllable_label)
        labels.addWidget(self.keep_original_gap_btn)
        labels.addWidget(self.save_current_play_position_btn)
        labels.addWidget(self.save_detected_gap_btn)
        labels.addWidget(self.revert_btn)

        main = QVBoxLayout()
        main.setContentsMargins(0, 0, 0, 0)
        main.addLayout(play_and_waveform_layout)
        main.addLayout(waveform_layout)
        main.addLayout(labels)
        self.setLayout(main)

        # Set up UI manager with references to UI elements
        button_dict = {
            'play': self.play_btn,
            'audio': self.audio_btn,
            'vocals': self.vocals_btn,
            'save_position': self.save_current_play_position_btn,
            'save_detected': self.save_detected_gap_btn,
            'keep_original': self.keep_original_gap_btn,
            'revert': self.revert_btn
        }
        
        label_dict = {
            'position': self.position_label,
            'syllable': self.syllable_label
        }
        
        self.ui_manager.setup(button_dict, label_dict, self.waveform_widget)

        # Connect events
        self.setup_event_connections()
        
        # Initial UI state
        self.update_ui()
        
        # Set focus policy
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def setup_event_connections(self):
        # Button events
        self.play_btn.clicked.connect(lambda: self.player.play())
        self.audio_btn.clicked.connect(lambda: self.player.audio_mode())
        self.vocals_btn.clicked.connect(lambda: self.player.vocals_mode())
        
        # Action button events
        self.save_current_play_position_btn.clicked.connect(self.on_save_current_play_position_clicked)
        self.revert_btn.clicked.connect(self.on_revert_btn_clicked)
        self.keep_original_gap_btn.clicked.connect(self.on_keep_original_gap_btn_clicked)
        self.save_detected_gap_btn.clicked.connect(self.on_save_detected_gap_btn_clicked)
        
        # Waveform events
        self.waveform_widget.position_clicked.connect(lambda pos: self.player.set_position(pos))

    def update_position(self, position):
        """Update UI elements when position changes"""
        self.ui_manager.update_position_label(
            position, 
            self.player.is_media_loaded(), 
            self.player.is_playing()
        )
        
        self.ui_manager.update_syllable_label(position, self._song)
        self.waveform_widget.update_position(position, self.player.get_duration())
        self.update_ui()

    def update_ui(self):
        """Update all UI elements based on current state"""
        self.ui_manager.update_button_states(
            self._song, 
            self.player.get_audio_status(), 
            self.player.is_media_loaded(),
            self.player.is_playing()
        )

    def on_play_state_changed(self, playing: bool):
        """Update UI when play state changes"""
        self.ui_manager.set_playback_state(playing)

    def on_audio_file_status_changed(self):
        """Handle change between audio/vocals mode"""
        self.player.stop()
        self.update_player_files()
        self.update_ui()
    
    def on_song_changed(self, song: Song):
        """Handle when a different song is selected"""
        logger.debug(f"Song changed in media player: {song}")
        
        # Only process if player is enabled (not multiple selection)
        if not self.isEnabled():
            return
            
        self._song = song
        if not song.notes or not WaveformPathService.waveforms_exists(song, self._data.tmp_path):
            self._actions.reload_song(song)
            
        self.update_ui()
        self.update_player_files()
    
    def on_song_updated(self):
        """Handle when the current song data is updated"""
        logger.debug(f"Current song updated")
        self.update_ui()
        self.update_player_files()
    
    def update_player_files(self):
        """Load the appropriate media files based on current state"""
        song: Song = self._song
        if not song or song.status == SongStatus.PROCESSING: 
            logger.debug("No song or song is processing - not loading media")
            self.player.load_media(None)
            self.waveform_widget.load_waveform(None)
            return
        
        # Check if song has notes attribute but don't prevent playback
        if not hasattr(song, 'notes') or song.notes is None:
            logger.warning(f"Song '{song.title}' does not have notes data, but will play audio anyway")
        
        # Get paths using WaveformPathService
        paths = WaveformPathService.get_paths(song, self._data.tmp_path)
        if not paths:
            logger.error(f"Could not get waveform paths for song: {song.title}")
            self.player.load_media(None)
            self.waveform_widget.load_waveform(None)
            return
            
        logger.debug(f"Updating player files. Audio status: {self.player.get_audio_status()}")
        if self.player.get_audio_status() == AudioFileStatus.AUDIO:
            logger.debug(f"Loading audio file: {paths['audio_file']}")
            self.player.load_media(paths['audio_file'])
            self.waveform_widget.load_waveform(paths['audio_waveform_file'])
        else:
            logger.debug(f"Loading vocals file: {paths['vocals_file']}")
            self.player.load_media(paths['vocals_file'])
            self.waveform_widget.load_waveform(paths['vocals_waveform_file'])

    def on_selected_songs_changed(self, songs: list):
        """Disable player when multiple songs are selected"""
        multiple_songs_selected = len(songs) > 1
        
        self.setEnabled(not multiple_songs_selected)
        self.ui_manager.handle_multiple_selection(multiple_songs_selected)
        
        if multiple_songs_selected:
            self.player.stop()
            self.waveform_widget.load_waveform(None)
    
    # Gap modification handlers
    def on_save_current_play_position_clicked(self):
        self._actions.update_gap_value(self._song, self.player.get_position())
    
    def on_revert_btn_clicked(self):
        self._actions.revert_gap_value(self._song)

    def on_keep_original_gap_btn_clicked(self):
        self._actions.keep_gap_value(self._song)

    def on_save_detected_gap_btn_clicked(self):
        self._actions.update_gap_value(self._song, self._song.gap_info.detected_gap)

