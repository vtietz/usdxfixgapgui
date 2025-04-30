from enum import Enum
import logging
import os
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtCore import QObject, QUrl, Qt, Signal, QTimer, QEvent
from PySide6.QtGui import QPainter, QPen, QPixmap

from actions import Actions
from data import AppData, Config
from model.song import Song, SongStatus

import utils.usdx as usdx
import utils.audio as audio

logger = logging.getLogger(__name__)

class MediaPlayerEventFilter(QObject):
    def __init__(self, component, callback_left, callback_right, callback_play):
        super().__init__()
        self.callback_left = callback_left
        self.callback_right = callback_right
        self.callback_play = callback_play
        self.component = component

    def eventFilter(self, watched, event):
        widget = QApplication.focusWidget()
        while widget is not None:
            if widget == self.component:
                if event.type() == QEvent.Type.KeyPress:
                    if event.key() == Qt.Key.Key_Left:
                        self.callback_left()
                        return True
                    elif event.key() == Qt.Key.Key_Right:
                        self.callback_right()
                        return True
                    elif event.key() == Qt.Key.Key_Space:
                        self.callback_play()
                        return True
                return False
            widget = widget.parent()

        return False  # Event not handled, continue with default processing


class MediaPlayerLoader:
    def __init__(self, media_player: QMediaPlayer):
        self.media_player = media_player

    def load(self, file):
        # Use a QTimer to delay the setSource call without blocking
        QTimer.singleShot(100, lambda: self.set_media_source(file))

    def set_media_source(self, file):
        if file and os.path.exists(file):
            self.media_player.setSource(QUrl.fromLocalFile(file))
        else:
            self.media_player.setSource(QUrl())

class AudioFileStatus(Enum):
    AUDIO = 0
    VOCALS = 1

class MediaPlayerComponent(QWidget):

    position_changed = Signal(int)
    is_playing_changed = Signal(bool)
    audio_file_status_changed = Signal(AudioFileStatus)

    globalEventFilter = None

    _song: Song = None
    _audioFileStatus: AudioFileStatus = AudioFileStatus.AUDIO
    _media_is_loaded = False
    _is_playing = False
    _play_position = 0

    currentPosition = 0 
    def __init__(self, data: AppData, actions: Actions, parent=None):
        super().__init__(parent)
        self._data = data
        self._config = data.config
        self._actions = actions

        self.globalEventFilter = MediaPlayerEventFilter(
            self,
            lambda: self.adjust_position_left(),
            lambda: self.adjust_position_right(),
            self.play
        )

        self.initUI()

    def initUI(self):

        # playbuttons

        self.audio_output = QAudioOutput()
        self.audio_output.setVolume(50)

        self.media_player = QMediaPlayer()
        self.media_player.setAudioOutput(self.audio_output)
        self.media_player_loader = MediaPlayerLoader(self.media_player)
        
        self.play_btn = QPushButton("Play")
        self.play_btn.setCheckable(True)

        self.audio_btn = QPushButton("Original Audio")
        self.audio_btn.setCheckable(True)

        self.vocals_btn = QPushButton("Extracted Vocals")
        self.vocals_btn.setCheckable(True)

        # waveform

        play_and_waveform_layout = QHBoxLayout()
        play_and_waveform_layout.addWidget(self.play_btn)
        play_and_waveform_layout.addWidget(self.audio_btn)
        play_and_waveform_layout.addWidget(self.vocals_btn)
        
        waveform_layout = QVBoxLayout()
        waveform_layout.setContentsMargins(0, 0, 0, 0) 
        self.waveform_label = QLabel()
        self.waveform_label.setStyleSheet("padding: 0px; margin: 0px;")
        self.waveform_label.setFixedHeight(150)  # Set a fixed height for the waveform display area
        self.waveform_label.setScaledContents(True) 
        self.waveform_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.waveform_label.installEventFilter(self)
        waveform_layout.addWidget(self.waveform_label)

        # position label and action buttons

        self.position_label = QLabel('')
        self.position_label.setStyleSheet(f"color: {self._config.playback_position_color};")
        self.keep_original_gap_btn = QPushButton("Keep original gap (0 ms)")
        self.save_current_play_position_btn = QPushButton("Save play position (0 ms)")
        self.save_detected_gap_btn = QPushButton("Save detected gap (0 ms)")
        self.revert_btn = QPushButton("Revert")

        self.syllable_label = QLabel('')
        self.syllable_label.setStyleSheet(f"color: {self._config.playback_position_color};")

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
        self.setLayout(main)
        main.addLayout(labels)

        # Overlay for showing the current play position
        self.overlay = QWidget(self.waveform_label)
        self.overlay.setFixedSize(self.waveform_label.size())
        self.overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)  # Allow clicks to pass through
        self.overlay.paintEvent = self.paint_overlay

        # event handling

        self._data.selected_song_changed.connect(self.on_song_changed)
        self._data.songs.updated.connect(self.on_song_updated)
        self._data.songs.deleted.connect(lambda: self.unload_all_media())

        self.media_player.positionChanged.connect(self.update_overlay_position)
        self.waveform_label.mousePressEvent = self.change_play_position

        self.play_btn.clicked.connect(self.play)

        self.audio_btn.clicked.connect(self.audio_mode)
        self.vocals_btn.clicked.connect(self.vocals_mode)

        self.media_player.positionChanged.connect(self.on_media_player_position_changed)
        self.media_player.playbackStateChanged.connect(self.on_media_player_playback_state_changed)
        self.media_player.mediaStatusChanged.connect(self.on_media_status_changed)

        self.is_playing_changed.connect(self.on_media_player_play_state_change)

        self.save_current_play_position_btn.clicked.connect(self.on_save_current_play_position_clicked) 
        self.revert_btn.clicked.connect(self.on_revert_btn_clicked)
        self.keep_original_gap_btn.clicked.connect(self.on_keep_original_gap_btn_clicked)
        self.save_detected_gap_btn.clicked.connect(self.on_save_detected_gap_btn_clicked)

        self.audio_file_status_changed.connect(self.on_audio_file_status_changed)

        self.update_button_states()

        # handle focus
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.waveform_label.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.waveform_label.mousePressEvent = self.focus_and_change_play_position

    def focus_and_change_play_position(self, event):
        self.setFocus() 
        self.change_play_position(event)

    def on_save_current_play_position_clicked(self):
        self._actions.update_gap_value(self._song, self.media_player.position())
    
    def on_revert_btn_clicked(self):
        self._actions.revert_gap_value(self._song)

    def on_keep_original_gap_btn_clicked(self):
        self._actions.keep_gap_value(self._song)

    def on_save_detected_gap_btn_clicked(self):
        self._actions.update_gap_value(self._song, self._song.gap_info.detected_gap)

    def on_song_changed(self, song: Song):
        logger.debug(f"Song changed in media player: {song}")
        logger.debug(f"Song path: {song.path}, Audio file: {song.audio_file}")
        logger.debug(f"Audio file exists: {os.path.exists(song.audio_file) if song.audio_file else False}")
        logger.debug(f"Vocals file: {song.vocals_file}")
        logger.debug(f"Vocals file exists: {os.path.exists(song.vocals_file) if song.vocals_file else False}")
        
        self._song = song
        self.update_button_states()
        self.update_player_files()
    
    def on_song_updated(self):
        logger.debug(f"Current song updated")
        self.update_button_states()
        self.update_player_files()

    def on_media_player_playback_state_changed(self):
        self._is_playing = self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        self.is_playing_changed.emit(self._is_playing)

    def on_media_status_changed(self, status):
        self._media_is_loaded = status == QMediaPlayer.MediaStatus.LoadedMedia
        logger.debug(f"Media status changed: {status}, loaded: {self._media_is_loaded}")
        self.update_button_states()

    def on_audio_file_status_changed(self):
        self.media_player.stop()
        self.update_player_files()
        self.update_button_states
    
    def on_media_player_position_changed(self, position):
        self._play_position = position
        self.update_position_label(position)
        self.update_button_states()
        self.update_syllable_label(position)
        
    def on_media_player_play_state_change(self, playing: bool):
        logger.debug(f"on_play_state_change: {playing}")
        self._is_playing=playing
        if playing:
            self.play_btn.setChecked(True)
        else:
            self.play_btn.setChecked(False)

    def update_button_states(self):
        song = self._song
        is_enabled = song is not None and not (song.status == SongStatus.PROCESSING)
        self.save_current_play_position_btn.setEnabled(is_enabled and self._play_position > 0)
        self.save_detected_gap_btn.setEnabled(is_enabled and song.gap_info.detected_gap > 0)
        self.keep_original_gap_btn.setEnabled(is_enabled)
        self.play_btn.setEnabled(is_enabled and self._media_is_loaded or self._is_playing)
        self.vocals_btn.setEnabled(is_enabled)
        self.audio_btn.setEnabled(is_enabled)
        self.revert_btn.setEnabled(is_enabled and song.gap != song.gap_info.original_gap)
        if song:
            self.save_detected_gap_btn.setText(f"Save detected gap ({song.gap_info.detected_gap} ms)")
            self.keep_original_gap_btn.setText(f"Keep gap ({song.gap} ms)")
            self.revert_btn.setText(f"Revert gap ({song.gap_info.original_gap} ms)")
        else:
            self.save_detected_gap_btn.setText(f"Save detected gap (0 ms)")
            self.keep_original_gap_btn.setText(f"Save gap (0 ms)")
            self.revert_btn.setText(f"Revert gap (0 ms)")
        self.audio_btn.setChecked(self._audioFileStatus == AudioFileStatus.AUDIO)
        self.vocals_btn.setChecked(self._audioFileStatus == AudioFileStatus.VOCALS)
        self.overlay.setVisible(is_enabled and self._media_is_loaded or self._is_playing)
        self.update_position_label(self.media_player.position())

    def update_player_files(self):
        song = self._song
        if(not song or song.status == SongStatus.PROCESSING): 
            logger.debug("No song or song is processing - not loading media")
            self.load_media(None)
            self.load_waveform(None)
            return
            
        logger.debug(f"Updating player files. Audio status: {self._audioFileStatus}")
        if(self._audioFileStatus == AudioFileStatus.AUDIO):
            logger.debug(f"Loading audio file: {song.audio_file}")
            self.load_media(song.audio_file)
            self.load_waveform(song.audio_waveform_file)
        if(self._audioFileStatus == AudioFileStatus.VOCALS):
            logger.debug(f"Loading vocals file: {song.vocals_file}")
            self.load_media(song.vocals_file)
            self.load_waveform(song.vocals_waveform_file)

    def update_syllable_label(self, position):
        song = self._song
        if(not song or song.status == SongStatus.PROCESSING):
            self.syllable_label.setText("")
            return
        syllable = usdx.get_syllable(song.notes, position, song.bpm, song.gap)
        self.syllable_label.setText(syllable)

    def load_media(self, file: str):
        old_source = self.media_player.source()
        
        if not file:
            logger.debug("No media file to load")
            self.media_player.stop()
            self.media_player.setSource(QUrl())
            return
            
        new_source = QUrl.fromLocalFile(file)
        logger.debug(f"Loading media file: {file}, exists: {os.path.exists(file)}")
        
        if(old_source.toString() == new_source.toString()):
            logger.debug("Media source unchanged - not reloading")
            return
            
        logger.debug(f"Setting new media source: {new_source}")
        self.media_player.stop()
        self.media_player_loader.load(file)
    
    def unload_all_media(self):
        self.media_player.stop()
        self.media_player.setSource(QUrl())
        self.waveform_label.setPixmap(QPixmap())

    def load_waveform(self, file: str):
        if(file and os.path.exists(file)):
            self.waveform_label.setPixmap(QPixmap(file))
        else:
            self.waveform_label.setPixmap(QPixmap())

    def paint_overlay(self, event):
        painter = QPainter(self.overlay)
        pen = QPen(Qt.GlobalColor.red, 2)
        painter.setPen(pen)
        # Convert x to an integer to ensure it matches the expected argument type
        x = int(self.currentPosition * self.overlay.width())
        painter.drawLine(x, 0, x, self.overlay.height())


    def update_overlay_position(self, position):
        duration = self.media_player.duration()
        if duration > 0:
            self.currentPosition = position / duration
            self.overlay.update()  # Trigger a repaint
        else:
            self.currentPosition = 0

    def change_play_position(self, event):
        # Calculate the new position based on the click event and set the media player's position
        clickPosition = event.position().x()  # Get the X coordinate of the click
        newPosition = (clickPosition / self.waveform_label.width()) * self.media_player.duration()
        # Convert newPosition to an integer
        newPosition = int(newPosition)
        self.media_player.setPosition(newPosition)
        self.position_changed.emit(newPosition)  # Emit signal with the new position

    def eventFilter(self, watched, event):
        if watched == self.waveform_label and event.type() == QEvent.Type.Resize:
            # Adjust the overlay size to match the waveformLabel
            self.overlay.setFixedSize(self.waveform_label.size())
        return super().eventFilter(watched, event)

    def update_position_label(self, position):
        if(not self._media_is_loaded and not self._is_playing):
            self.position_label.setText("")
            return
        playposition_text=audio.milliseconds_to_str(position)
        self.position_label.setText(playposition_text)
        self.save_current_play_position_btn.setText(f"Save play position ({position} ms)")

    def play(self):
        logger.debug(f"Play button clicked. Is playing: {self.media_player.isPlaying()}")
        if self.media_player.isPlaying():
            self.media_player.pause()
            logger.debug("Media player paused")
        else:
            self.media_player.play()
            logger.debug("Media player started playing")
    
    def stop(self):
        self.media_player.stop()

    def audio_mode(self):
        self._audioFileStatus=AudioFileStatus.AUDIO
        self.audio_file_status_changed.emit(self._audioFileStatus)

    def vocals_mode(self):
        self._audioFileStatus=AudioFileStatus.VOCALS
        self.audio_file_status_changed.emit(self._audioFileStatus)

    def adjust_position_left(self):
        if(self._audioFileStatus == AudioFileStatus.AUDIO):
            ms = self._config.adjust_player_position_step_audio
        else:
            ms = self._config.adjust_player_position_step_vocals
        newPosition = max(0, self.media_player.position() - ms)
        self.media_player.setPosition(newPosition)

    def adjust_position_right(self):
        if(self._audioFileStatus == AudioFileStatus.AUDIO):
            ms = self._config.adjust_player_position_step_audio
        else:
            ms = self._config.adjust_player_position_step_vocals
        newPosition = max(0, self.media_player.position() + ms)
        self.media_player.setPosition(newPosition)