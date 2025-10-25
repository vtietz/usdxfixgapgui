import logging
import os
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Signal, Qt, QSize

from actions import Actions
from app.app_data import AppData
from model.song import Song, SongStatus
from services.waveform_path_service import WaveformPathService

from ui.mediaplayer.constants import AudioFileStatus
from ui.mediaplayer.event_filter import MediaPlayerEventFilter
from ui.mediaplayer.waveform_widget import WaveformWidget
from ui.mediaplayer.player_controller import PlayerController
from ui.mediaplayer.ui_manager import UIManager
from ui.mediaplayer.gap_marker_colors import (
    PLAYHEAD_HEX,
    DETECTED_GAP_HEX,
    REVERT_GAP_HEX
)
from ui.ui_utils import make_color_dot_icon

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
        self.player.vocals_validation_failed.connect(self.on_vocals_validation_failed)

        # Connect signals from self to player
        self.is_playing_changed.connect(self.on_play_state_changed)
        self.audio_file_status_changed.connect(self.on_audio_file_status_changed)

        # Connect to the data signals
        self._data.selected_song_changed.connect(self.on_song_changed)
        self._data.selected_songs_changed.connect(self.on_selected_songs_changed)
        self._data.songs.updated.connect(self.on_song_updated)
        self._data.songs.deleted.connect(lambda: self.player.unload_all_media())
        # New: allow actions to request unloading media to prevent Windows file locks during normalization
        if hasattr(self._data, "media_unload_requested"):
            self._data.media_unload_requested.connect(lambda: self.player.unload_all_media())

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

        # Add colored dot icons matching waveform markers
        # "Keep current gap" - no color icon (just marks gap as solved without changing value)
        self.keep_original_gap_btn = QPushButton(" Keep current gap (0 ms)")

        # "Save play position" - red icon (matches playhead)
        self.save_current_play_position_btn = QPushButton(" Save play position (0 ms)")
        self.save_current_play_position_btn.setIcon(make_color_dot_icon(PLAYHEAD_HEX, diameter=8))
        self.save_current_play_position_btn.setIconSize(QSize(8, 8))

        # "Save detected gap" - green icon (matches AI detection)
        self.save_detected_gap_btn = QPushButton(" Save detected gap (0 ms)")
        self.save_detected_gap_btn.setIcon(make_color_dot_icon(DETECTED_GAP_HEX, diameter=8))
        self.save_detected_gap_btn.setIconSize(QSize(8, 8))

        # "Revert gap" - gray icon (dashed line on waveform)
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

    def on_vocals_validation_failed(self):
        """Handle when vocals file fails validation"""
        # Clear waveform and show error placeholder
        self.waveform_widget.load_waveform(None)
        self.waveform_widget.set_placeholder(
            "Invalid vocals file - re-run gap detection to regenerate"
        )

        # Update vocals button tooltip
        self.vocals_btn.setToolTip(
            "Invalid vocals file format. Re-run gap detection to re-extract vocals."
        )

        # Update UI state
        self.update_ui()

    def on_song_changed(self, song: Song):
        """Handle when a different song is selected"""
        logger.debug(f"Song changed in media player: {song}")

        # Only process if player is enabled (not multiple selection)
        if not self.isEnabled():
            return

        self._song = song

        # Guard against None song
        if song is None:
            logger.debug("Song is None, clearing player")
            self.update_ui()
            self.update_player_files()
            # Track B: Clear gap markers
            self.waveform_widget.set_gap_markers(None, None)
            return

        # Update UI immediately for instant feedback
        self.update_ui()
        self.update_player_files()

        # Track B: Update gap markers from GapState
        if hasattr(self._data, 'gap_state') and self._data.gap_state:
            self.waveform_widget.set_gap_markers(
                original_gap_ms=self._data.gap_state.saved_gap_ms,
                detected_gap_ms=self._data.gap_state.detected_gap_ms
            )
        else:
            self.waveform_widget.set_gap_markers(None, None)

        # Defer async operations slightly to let UI render selection first
        # This eliminates any perceived lag from event loop contention
        from PySide6.QtCore import QTimer

        # Check if we need to load data (async, non-blocking)
        if not song.notes:
            # Song needs metadata reload - use light reload to avoid status changes
            # Defer by 0ms to let UI render first
            QTimer.singleShot(0, lambda: self._actions.reload_song_light(song))

        # Create waveforms for selected song if missing (instant task, runs immediately in parallel)
        if not WaveformPathService.waveforms_exists(song, self._data.tmp_path):
            # Set placeholder immediately to show user feedback
            self.waveform_widget.set_placeholder("Loading waveform…")

            from actions.audio_actions import AudioActions
            audio_actions = AudioActions(self._data)
            # Defer slightly to let UI render first, then start instant task
            QTimer.singleShot(0, lambda: audio_actions._create_waveforms(song, overwrite=False, use_queue=True))

    def on_song_updated(self, updated_song: Song):
        """Handle when the current song data is updated

        Args:
            updated_song: The song that was updated
        """
        # Only update UI if the updated song is the currently selected song
        if self._song is None or updated_song is None:
            return

        if self._song.path != updated_song.path:
            logger.debug(f"Song updated but not currently selected: {updated_song.title}")
            return

        logger.debug(f"Current song updated: {updated_song.title}")
        # Ensure we reference the latest Song instance so status checks (e.g., QUEUED) are accurate.
        # Without this, update_player_files may use a stale self._song and re-load media, causing file locks.
        self._song = updated_song
        self.update_ui()
        self.update_player_files()

        # Track B: Update GapState when song data changes (e.g., after metadata reload)
        if hasattr(self._data, 'gap_state') and self._data.gap_state:
            # Update GapState with latest gap_info data
            if updated_song.gap_info:
                self._data.gap_state.detected_gap_ms = updated_song.gap_info.detected_gap
                self._data.gap_state.saved_gap_ms = updated_song.gap_info.original_gap

            # Refresh gap markers on waveform
            self.waveform_widget.set_gap_markers(
                original_gap_ms=self._data.gap_state.saved_gap_ms,
                detected_gap_ms=self._data.gap_state.detected_gap_ms
            )

    def update_player_files(self):
        """Load the appropriate media files based on current state"""
        song: Song = self._song
        if not song:
            logger.debug("No song - not loading media")
            self.player.load_media(None)
            self.waveform_widget.load_waveform(None)
            self.waveform_widget.clear_placeholder()
            return

        # Avoid re-loading media while a processing task has just been queued or is running.
        # The QUEUED state is emitted immediately before starting normalization and can
        # cause the player to re-open the file, leading to Windows file locks.
        # PROCESSING state means a worker is actively modifying the file.
        # Skip loading during QUEUED/PROCESSING to allow background workers to operate safely.
        if song.status in (SongStatus.QUEUED, SongStatus.PROCESSING):
            logger.debug(f"Song is {song.status.name}; not loading media to prevent file locks during processing")
            self.player.load_media(None)
            # Keep waveform as-is; do not reload here
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
            self.waveform_widget.clear_placeholder()
            return

        logger.debug(f"Updating player files. Audio status: {self.player.get_audio_status()}")

        # Determine which files to load based on audio mode
        audio_status = self.player.get_audio_status()

        if audio_status == AudioFileStatus.AUDIO:
            logger.debug(f"Loading audio file: {paths['audio_file']}")
            # Keep audio playback available even during gap detection (PROCESSING status)
            self.player.load_media(paths['audio_file'])

            # Check if audio waveform exists
            if os.path.exists(paths['audio_waveform_file']):
                self.waveform_widget.load_waveform(paths['audio_waveform_file'])

                # Track B: Set waveform duration for gap markers from the actual audio file
                from utils.audio import get_audio_duration
                duration_f = get_audio_duration(paths['audio_file'])
                if duration_f is not None:
                    self.waveform_widget.duration_ms = int(duration_f)
                    self.waveform_widget.overlay.update()  # Trigger marker redraw
            else:
                self.waveform_widget.load_waveform(None)
                # Show different message during gap detection
                if song.status == SongStatus.PROCESSING:
                    self.waveform_widget.set_placeholder("Gap detection in progress…")
                else:
                    self.waveform_widget.set_placeholder("Loading waveform…")

            # Clear vocals button tooltip in audio mode
            self.vocals_btn.setToolTip("")

        else:  # VOCALS mode
            # Check if vocals file exists
            vocals_file_exists = os.path.exists(paths['vocals_file'])

            if not vocals_file_exists:
                # Vocals not extracted yet
                logger.debug("Vocals file does not exist")
                self.player.load_media(None)
                self.waveform_widget.load_waveform(None)
                self.waveform_widget.set_placeholder("Run gap detection to generate the vocals waveform.")
                self.vocals_btn.setToolTip("Run gap detection to extract vocals and generate a waveform.")
            else:
                # Vocals file exists, load it
                logger.debug(f"Loading vocals file: {paths['vocals_file']}")
                self.player.load_media(paths['vocals_file'])

                # Check if vocals waveform exists
                if os.path.exists(paths['vocals_waveform_file']):
                    self.waveform_widget.load_waveform(paths['vocals_waveform_file'])

                    # Track B: Set waveform duration for gap markers from the actual vocals file
                    from utils.audio import get_audio_duration
                    duration_f = get_audio_duration(paths['vocals_file'])
                    if duration_f is not None:
                        self.waveform_widget.duration_ms = int(duration_f)
                        self.waveform_widget.overlay.update()  # Trigger marker redraw
                else:
                    self.waveform_widget.load_waveform(None)
                    self.waveform_widget.set_placeholder("Loading waveform…")

                # Clear tooltip when vocals exist
                self.vocals_btn.setToolTip("")

    def on_selected_songs_changed(self, songs: list):
        """Disable player when multiple songs are selected"""
        multiple_songs_selected = len(songs) > 1

        self.setEnabled(not multiple_songs_selected)
        self.ui_manager.handle_multiple_selection(multiple_songs_selected)

        if multiple_songs_selected:
            logger.debug("Multiple songs selected, stopping player")
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
