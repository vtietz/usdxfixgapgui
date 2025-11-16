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
from ui.mediaplayer.gap_marker_colors import PLAYHEAD_HEX, DETECTED_GAP_HEX
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
        self._suspend_loads = False  # Guard window to avoid reload during status/filter transitions
        self._mode_switch_timer = None  # Debounce timer for mode switch reload

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
            lambda: self.player.play(),
        )

        # Connect signals from player to local handlers
        self.player.position_changed.connect(self.update_position)
        self.player.is_playing_changed.connect(self.is_playing_changed)
        self.player.audio_file_status_changed.connect(self.audio_file_status_changed)
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
        # Optional: suspend media loads during status/filter transitions (if provided by AppData)
        if hasattr(self._data, "media_suspend_requested"):
            try:
                self._data.media_suspend_requested.connect(self.on_media_suspend_requested)
            except Exception:
                pass

    def initUI(self):
        # Create control buttons
        self.play_btn = QPushButton("Play")
        # Don't make checkable - we manage state via text (Play/Stop) to avoid Qt checkable button issues
        self.play_btn.setToolTip("Play/Pause audio (Space or Left/Right arrows)")

        self.audio_btn = QPushButton("Original Audio")
        self.audio_btn.setCheckable(True)
        self.audio_btn.setToolTip("Play original audio file")

        self.vocals_btn = QPushButton("Extracted Vocals")
        self.vocals_btn.setCheckable(True)
        # Tooltip is set dynamically based on vocals availability

        # Setup waveform
        self.waveform_widget = WaveformWidget(self)

        # Setup action buttons
        self.position_label = QLabel("")
        self.position_label.setStyleSheet(f"color: {self._config.playback_position_color};")

        # Add colored dot icons matching waveform markers
        # "Keep current gap" - no color icon (just marks gap as solved without changing value)
        self.keep_original_gap_btn = QPushButton(" Keep current gap (0 ms)")
        self.keep_original_gap_btn.setToolTip("Keep the current gap value and mark song as solved")

        # "Save play position" - red icon (matches playhead)
        self.save_current_play_position_btn = QPushButton(" Save play position (0 ms)")
        self.save_current_play_position_btn.setIcon(make_color_dot_icon(PLAYHEAD_HEX, diameter=8))
        self.save_current_play_position_btn.setIconSize(QSize(8, 8))
        self.save_current_play_position_btn.setToolTip("Save current playback position as gap value (S)")

        # "Save detected gap" - green icon (matches AI detection)
        self.save_detected_gap_btn = QPushButton(" Save detected gap (0 ms)")
        self.save_detected_gap_btn.setIcon(make_color_dot_icon(DETECTED_GAP_HEX, diameter=8))
        self.save_detected_gap_btn.setIconSize(QSize(8, 8))
        self.save_detected_gap_btn.setToolTip("Save AI-detected gap value (A)")

        # "Revert gap" - gray icon (dashed line on waveform)
        self.revert_btn = QPushButton("Revert")
        self.revert_btn.setToolTip("Revert to previously saved gap value (R)")

        self.syllable_label = QLabel("")
        self.syllable_label.setStyleSheet(f"color: {self._config.playback_position_color};")

        # Create layouts
        play_and_waveform_layout = QHBoxLayout()
        play_and_waveform_layout.addWidget(self.audio_btn)
        play_and_waveform_layout.addWidget(self.vocals_btn)

        waveform_layout = QVBoxLayout()
        waveform_layout.setContentsMargins(0, 0, 0, 0)
        waveform_layout.addWidget(self.waveform_widget)

        labels = QHBoxLayout()
        labels.addWidget(self.play_btn)  # Moved: Play button now left of position
        labels.addWidget(self.position_label)
        labels.addWidget(self.syllable_label)
        labels.addWidget(self.keep_original_gap_btn)
        labels.addWidget(self.save_current_play_position_btn)
        labels.addWidget(self.save_detected_gap_btn)
        labels.addWidget(self.revert_btn)

        main = QVBoxLayout()
        main.setContentsMargins(0, 5, 0, 5)
        main.addLayout(play_and_waveform_layout)
        main.addLayout(waveform_layout)
        main.addLayout(labels)
        self.setLayout(main)

        # Set up UI manager with references to UI elements
        button_dict = {
            "play": self.play_btn,
            "audio": self.audio_btn,
            "vocals": self.vocals_btn,
            "save_position": self.save_current_play_position_btn,
            "save_detected": self.save_detected_gap_btn,
            "keep_original": self.keep_original_gap_btn,
            "revert": self.revert_btn,
        }

        label_dict = {"position": self.position_label, "syllable": self.syllable_label}

        self.ui_manager.setup(button_dict, label_dict, self.waveform_widget)

        # Connect events
        self.setup_event_connections()

        # Initial UI state
        self.update_ui()

        # Set focus policy
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def setup_event_connections(self):
        # Button events
        self.play_btn.clicked.connect(self.player.play)
        self.audio_btn.clicked.connect(self.player.audio_mode)
        self.vocals_btn.clicked.connect(self.player.vocals_mode)

        # Action button events
        self.save_current_play_position_btn.clicked.connect(self.on_save_current_play_position_clicked)
        self.revert_btn.clicked.connect(self.on_revert_btn_clicked)
        self.keep_original_gap_btn.clicked.connect(self.on_keep_original_gap_btn_clicked)
        self.save_detected_gap_btn.clicked.connect(self.on_save_detected_gap_btn_clicked)

        # Waveform events
        self.waveform_widget.position_clicked.connect(lambda pos: self.player.set_position(pos))

    def update_position(self, position):
        """Update UI elements when position changes"""
        self.ui_manager.update_position_label(position, self.player.is_media_loaded(), self.player.is_playing())

        self.ui_manager.update_syllable_label(position, self._song)
        self.waveform_widget.update_position(position, self.player.get_duration())

        # Update save_position button state when position crosses 0 threshold
        # Only update this one button to avoid UI thrashing (50ms updates)
        if self._song and self._song.status != SongStatus.PROCESSING:
            should_enable = position > 0
            if self.save_current_play_position_btn.isEnabled() != should_enable:
                self.save_current_play_position_btn.setEnabled(should_enable)

    def update_ui(self):
        """Update all UI elements based on current state"""
        self.ui_manager.update_button_states(
            self._song, self.player.get_audio_status(), self.player.is_media_loaded(), self.player.is_playing()
        )

    def on_play_state_changed(self, playing: bool):
        """Update UI when play state changes"""
        self.ui_manager.set_playback_state(playing)

    def on_audio_file_status_changed(self):
        """Handle change between audio/vocals mode"""
        logger.debug("Audio file status changed - switching between dual players (debounced)")
        # Debounce reload to coalesce rapid toggles and avoid WMF races
        from PySide6.QtCore import QTimer

        if self._mode_switch_timer is None:
            self._mode_switch_timer = QTimer(self)
            self._mode_switch_timer.setSingleShot(True)
            self._mode_switch_timer.timeout.connect(self._on_mode_switch_timeout)
        if self._mode_switch_timer.isActive():
            self._mode_switch_timer.stop()
        self._mode_switch_timer.start(180)
        # Update UI immediately for button state
        self.update_ui()

    def _on_mode_switch_timeout(self):
        """Apply mode switch reload after debounce window."""
        self.update_player_files()
        self.update_ui()

    def on_vocals_validation_failed(self):
        """Handle when vocals file fails validation"""
        # Clear waveform and show error placeholder
        self.waveform_widget.load_waveform(None)
        self.waveform_widget.set_placeholder("Invalid vocals file - re-run gap detection to regenerate")

        # Update vocals button tooltip
        self.vocals_btn.setToolTip("Invalid vocals file format. Re-run gap detection to re-extract vocals.")

        # Update UI state
        self.update_ui()

    def on_media_suspend_requested(self, *args):
        """Suspend media loads for a short window to avoid unload→reload races during status/filter updates."""
        try:
            ms = int(args[0]) if args else 250
        except Exception:
            ms = 250
        self._suspend_media_loads(ms)

    def _suspend_media_loads(self, ms: int = 250):
        """Enable a temporary guard that skips update_player_files during sensitive UI transitions."""
        if self._suspend_loads:
            # Already suspended; extend by restarting the timer
            pass
        self._suspend_loads = True
        from PySide6.QtCore import QTimer

        def _clear():
            self._suspend_loads = False
            logger.debug("Media load suspension window ended")

        logger.debug(f"Suspending media loads for {ms}ms")
        QTimer.singleShot(ms, _clear)

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

        # Update gap markers from current song's gap_info
        # Note: Always read from song.gap_info, never from global gap_state which may be stale
        if song.gap_info:
            self.waveform_widget.set_gap_markers(
                original_gap_ms=song.gap_info.original_gap, detected_gap_ms=song.gap_info.detected_gap
            )
        else:
            self.waveform_widget.set_gap_markers(
                None, None
            )  # Defer async operations slightly to let UI render selection first
        # This eliminates any perceived lag from event loop contention
        from PySide6.QtCore import QTimer

        # Check if we need to load data (async, non-blocking)
        if not song.notes:
            # Song needs metadata reload - use light reload to avoid status changes
            # Defer by 0ms to let UI render first
            QTimer.singleShot(0, lambda: self._actions.reload_song_light(song))
            # Note: Waveform will be created after notes load via on_song_updated signal
        else:
            # Notes already loaded - safe to create waveforms immediately
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
        self._song = updated_song
        self.update_ui()

        # Check if waveform was just created (file now exists but placeholder is showing)
        # This fixes the "Loading waveform..." placeholder persistence issue
        waveforms_exist = WaveformPathService.waveforms_exists(updated_song, self._data.tmp_path)
        if self.waveform_widget.placeholder_visible and waveforms_exist:
            logger.info(f"Waveform created for {updated_song.title} - reloading display")
            self.update_player_files()
            return  # Early return - update_player_files already called

        # Reload media/waveform if status is QUEUED/PROCESSING (handled by _should_skip_loading)
        # Or if waveform exists and was just regenerated (for gap updates, note changes, etc.)
        should_reload = updated_song.status in (SongStatus.QUEUED, SongStatus.PROCESSING) or waveforms_exist
        if should_reload:
            if updated_song.status in (SongStatus.QUEUED, SongStatus.PROCESSING):
                logger.debug(f"Status changed to {updated_song.status.name}, reloading player files")
            else:
                logger.debug(f"Waveform regenerated for {updated_song.title}, reloading display")
            self.update_player_files()

        # Update gap markers from updated song's gap_info
        if updated_song.gap_info:
            # Show current gap from file (not original_gap) so marker updates when user saves
            self.waveform_widget.set_gap_markers(
                original_gap_ms=updated_song.gap, detected_gap_ms=updated_song.gap_info.detected_gap
            )
        else:
            self.waveform_widget.set_gap_markers(None, None)

        # If notes just finished loading and waveforms don't exist, create them now
        if updated_song.notes and not WaveformPathService.waveforms_exists(updated_song, self._data.tmp_path):
            logger.debug(f"Notes loaded for {updated_song.title}, creating waveforms with notes")
            from actions.audio_actions import AudioActions

            audio_actions = AudioActions(self._data)
            audio_actions._create_waveforms(updated_song, overwrite=False, use_queue=True)

    def update_player_files(self):
        """Load the appropriate media files based on current state"""
        import time

        start_time = time.perf_counter()

        # Guard: skip loads during suspension window (status/filter transitions in progress)
        if getattr(self, "_suspend_loads", False):
            logger.debug("update_player_files skipped (media loads suspended)")
            return

        # Guard: skip loading if current song is no longer selected (likely filtered out)
        try:
            selected = getattr(self._data, "selected_songs", [])
        except Exception:
            selected = []
        if selected and self._song is not None and self._song not in selected:
            logger.debug("update_player_files skipped (song no longer selected/visible)")
            return

        song = self._song
        if not song:
            self._clear_player_ui()
            return

        if self._should_skip_loading(song):
            return

        paths = self._get_song_paths(song)
        if not paths:
            return

        audio_status = self.player.get_audio_status()
        if audio_status == AudioFileStatus.AUDIO:
            self._load_audio_mode(song, paths)
        else:
            self._load_vocals_mode(paths)

        duration_ms = (time.perf_counter() - start_time) * 1000
        if duration_ms > 100:
            logger.warning(f"SLOW update_player_files: {duration_ms:.1f}ms")
        else:
            logger.debug(f"update_player_files completed in {duration_ms:.1f}ms")

    def _clear_player_ui(self):
        """Clear all player UI elements"""
        logger.debug("No song - not loading media")
        self.player.load_media(None)
        self.waveform_widget.load_waveform(None)
        self.waveform_widget.clear_placeholder()

    def _should_skip_loading(self, song: Song) -> bool:
        """Check if media loading should be skipped"""
        # Skip during QUEUED/PROCESSING to prevent file locks
        if song.status in (SongStatus.QUEUED, SongStatus.PROCESSING):
            logger.debug(f"Song is {song.status.name}; not loading media to prevent file locks during processing")
            self.player.load_media(None)
            return True

        # Log if notes not loaded yet, but allow playback
        if not hasattr(song, "notes") or song.notes is None:
            logger.debug(f"Song '{song.title}' does not have notes data yet (loading in progress), will play anyway")

        return False

    def _get_song_paths(self, song: Song) -> dict | None:
        """Get file paths for song, return None on error"""
        paths = WaveformPathService.get_paths(song, self._data.tmp_path)
        if not paths:
            logger.error(f"Could not get waveform paths for song: {song.title}")
            self._clear_player_ui()
        return paths

    def _load_audio_mode(self, song: Song, paths: dict):
        """Load audio file and waveform"""
        logger.debug(f"Loading audio file: {paths['audio_file']}")
        self.player.load_media(paths["audio_file"])

        if os.path.exists(paths["audio_waveform_file"]):
            self._load_audio_waveform(paths)
        else:
            self._show_waveform_placeholder(song)

        self.vocals_btn.setToolTip("")

    def _load_audio_waveform(self, paths: dict):
        """Load audio waveform and set duration"""
        import time
        from utils.audio import get_audio_duration

        start_time = time.perf_counter()

        self.waveform_widget.load_waveform(paths["audio_waveform_file"])
        duration_f = get_audio_duration(paths["audio_file"])
        if duration_f is not None:
            self.waveform_widget.duration_ms = int(duration_f)
            # Trigger initial position update so waveform displays with duration
            self.waveform_widget.update_position(0, int(duration_f))

        duration_ms = (time.perf_counter() - start_time) * 1000
        if duration_ms > 100:
            logger.warning(f"SLOW _load_audio_waveform: {duration_ms:.1f}ms (likely ffprobe blocking)")
        else:
            logger.debug(f"_load_audio_waveform completed in {duration_ms:.1f}ms")

    def _show_waveform_placeholder(self, song: Song):
        """Show appropriate placeholder message"""
        self.waveform_widget.load_waveform(None)
        if song.status == SongStatus.PROCESSING:
            self.waveform_widget.set_placeholder("Gap detection in progress…")
        else:
            self.waveform_widget.set_placeholder("Loading waveform…")

    def _load_vocals_mode(self, paths: dict):
        """Load vocals file and waveform"""
        if not os.path.exists(paths["vocals_file"]):
            self._show_vocals_missing()
            return

        logger.debug(f"Loading vocals file: {paths['vocals_file']}")
        self.player.load_media(paths["vocals_file"])

        if os.path.exists(paths["vocals_waveform_file"]):
            self._load_vocals_waveform(paths)
        else:
            self.waveform_widget.load_waveform(None)
            self.waveform_widget.set_placeholder("Loading waveform…")

        self.vocals_btn.setToolTip("")

    def _show_vocals_missing(self):
        """Show UI for missing vocals file"""
        logger.debug("Vocals file does not exist")
        self.player.load_media(None)
        self.waveform_widget.load_waveform(None)
        self.waveform_widget.set_placeholder("Run gap detection to generate the vocals waveform.")
        self.vocals_btn.setToolTip("Run gap detection to extract vocals and generate a waveform.")

    def _load_vocals_waveform(self, paths: dict):
        """Load vocals waveform and set duration"""
        from utils.audio import get_audio_duration

        self.waveform_widget.load_waveform(paths["vocals_waveform_file"])
        vocals_duration_f = get_audio_duration(paths["vocals_file"])
        if vocals_duration_f is not None:
            self.waveform_widget.duration_ms = int(vocals_duration_f)
            # Trigger initial position update so waveform displays with duration
            self.waveform_widget.update_position(0, int(vocals_duration_f))

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
        if not self._song:
            return
        gap_info = getattr(self._song, "gap_info", None)
        if gap_info and hasattr(gap_info, "detected_gap") and gap_info.detected_gap is not None:
            self._actions.update_gap_value(self._song, gap_info.detected_gap)
