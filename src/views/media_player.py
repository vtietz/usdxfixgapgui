from enum import Enum
import logging
import os
from PyQt6.QtWidgets import  QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtCore import QObject, QUrl, Qt, pyqtSignal, QTimer, QEvent
from PyQt6.QtGui import QPainter, QPen, QPixmap

from actions import Actions
from data import AppData, Config
from model.info import SongStatus
from model.song import Song

import utils.usdx as usdx


logger = logging.getLogger(__name__)

class MediaPlayerEventFilter(QObject):
    def __init__(self, callback_left, callback_right, callback_play):
        super().__init__()
        self.callback_left = callback_left
        self.callback_right = callback_right
        self.callback_play = callback_play

    def eventFilter(self, obj, event):
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

    position_changed = pyqtSignal(int)
    is_playing_changed = pyqtSignal(bool)
    audio_file_status_changed = pyqtSignal(AudioFileStatus)

    globalEventFilter = None

    _song: Song = None
    _audioFileStatus: AudioFileStatus = AudioFileStatus.AUDIO
    _media_is_loaded = False
    _is_playing = False
    _play_position = 0

    currentPosition = 0 
    def __init__(self, data: AppData, config: Config, actions: Actions, parent=None):
        super().__init__(parent)
        self._data = data
        self._config = config
        self._actions = actions

        self.globalEventFilter = MediaPlayerEventFilter(
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

    def on_save_current_play_position_clicked(self):
        self._actions.update_gap_value(self._song, self.media_player.position())
    
    def on_revert_btn_clicked(self):
        self._actions.revert_gap_value(self._song)

    def on_keep_original_gap_btn_clicked(self):
        self._actions.keep_gap_value(self._song)

    def on_save_detected_gap_btn_clicked(self):
        self._actions.update_gap_value(self._song, self._song.info.detected_gap)

    def on_song_changed(self, song: Song):
        logger.debug(f"Song changed: {song}")
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
        is_enabled = song is not None and not (song.info.status == SongStatus.PROCESSING)
        self.save_current_play_position_btn.setEnabled(is_enabled and self._play_position > 0)
        self.save_detected_gap_btn.setEnabled(is_enabled and song.info.detected_gap > 0)
        self.keep_original_gap_btn.setEnabled(is_enabled)
        self.play_btn.setEnabled(is_enabled and self._media_is_loaded or self._is_playing)
        self.vocals_btn.setEnabled(is_enabled)
        self.audio_btn.setEnabled(is_enabled)
        self.revert_btn.setEnabled(is_enabled and song.gap != song.info.original_gap)
        if song:
            self.save_detected_gap_btn.setText(f"Save detected gap ({song.info.detected_gap} ms)")
            self.keep_original_gap_btn.setText(f"Keep gap ({song.gap} ms)")
            self.revert_btn.setText(f"Revert gap ({song.info.original_gap} ms)")
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
        if(not song or song.info.status == SongStatus.PROCESSING): 
            self.load_media(None)
            self.load_waveform(None)
            return
        if(self._audioFileStatus == AudioFileStatus.AUDIO):
            self.load_media(song.audio_file)
            self.load_waveform(song.audio_waveform_file)
        if(self._audioFileStatus == AudioFileStatus.VOCALS):
            self.load_media(song.vocals_file)
            self.load_waveform(song.vocals_waveform_file)

    def update_syllable_label(self, position):
        song = self._song
        if(not song or song.info.status == SongStatus.PROCESSING):
            self.syllable_label.setText("")
            return
        syllable = usdx.get_syllable(song.notes, position, song.bpm, song.gap)
        self.syllable_label.setText(syllable)

    def load_media(self, file: str):
        old_source = self.media_player.source()
        new_source = QUrl.fromLocalFile(file)
        if(old_source.toString() == new_source.toString()):
            return
        self.media_player.stop()
        self.media_player_loader.load(file)

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
        # Convert position from milliseconds to minutes:seconds:milliseconds
        minutes = position // 60000
        seconds = (position % 60000) // 1000
        milliseconds = position % 1000
        # Update the label
        playposition_text=f'{minutes:02d}:{seconds:02d}:{milliseconds:03d}'
        self.position_label.setText(playposition_text)
        self.save_current_play_position_btn.setText(f"Save play position ({position} ms)")

    def play(self):
        if self.media_player.isPlaying():
            self.media_player.pause()
        else:
            self.media_player.play()
    
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