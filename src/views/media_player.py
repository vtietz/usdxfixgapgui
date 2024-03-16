from enum import Enum
import os
import sys
from PyQt6.QtWidgets import  QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtCore import QObject, QUrl, Qt, pyqtSignal, QPoint, QEvent
from PyQt6.QtGui import QPainter, QPen, QPixmap
from actions import Actions

from data import AppData, Config
from model.song import Song

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

class AudioFileStatus(Enum):
    AUDIO = 0
    VOCALS = 1

class MediaPlayerComponent(QWidget):

    positionChanged = pyqtSignal(int)
    audio_file_status_changed = pyqtSignal(AudioFileStatus)

    audioFileStatus: AudioFileStatus = AudioFileStatus.AUDIO
    song: Song = None

    currentPosition = 0 
    def __init__(self, data: AppData, config: Config, actions: Actions, parent=None):
        super().__init__(parent)
        self.data = data
        self.config = config
        self.actions = actions
        self.initUI()

    def initUI(self):
        
        # playbuttons

        self.audio_output = QAudioOutput()
        self.audio_output.setVolume(50)

        self.media_player = QMediaPlayer()
        self.media_player.setAudioOutput(self.audio_output)
        
        self.play_btn = QPushButton("Play")
        self.play_btn.setCheckable(True)

        self.stop_btn = QPushButton("Stop")

        self.audio_btn = QPushButton("Audio")
        self.audio_btn.setCheckable(True)

        self.vocals_btn = QPushButton("Vocals")
        self.vocals_btn.setCheckable(True)

        # waveform

        play_and_waveform_layout = QHBoxLayout()
        play_and_waveform_layout.addWidget(self.play_btn)
        play_and_waveform_layout.addWidget(self.stop_btn)
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

        self.position_label = QLabel('00:00:000')
        self.position_label.setStyleSheet(f"color: {self.config.playback_position_color};")
        self.keep_original_gap_btn = QPushButton("Keep original gap (0 ms)")
        self.save_current_play_position_btn = QPushButton("Save play position (0 ms)")
        self.save_detected_gap_btn = QPushButton("Save detected gap (0 ms)")
        self.revert_btn = QPushButton("Revert")

        labels = QHBoxLayout()
        labels.addWidget(self.position_label)
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

        self.media_player.positionChanged.connect(self.data.update_player_position)
        self.media_player.playingChanged.connect(self.data.update_playing)

        self.data.selected_song_changed.connect(self.song_changed)

        self.media_player.positionChanged.connect(self.update_overlay_position)
        self.waveform_label.mousePressEvent = self.change_play_position

        self.play_btn.clicked.connect(self.play)
        self.stop_btn.clicked.connect(self.stop)

        self.audio_btn.clicked.connect(self.audio_mode)
        self.vocals_btn.clicked.connect(self.vocals_mode)

        self.media_player.positionChanged.connect(self.update_position_label)
        self.data.player_position_changed.connect(self.media_player.setPosition)

        self.save_current_play_position_btn.clicked.connect(self.save_current_play_position) 

        self.song_changed(self.data.selected_song)

    def save_current_play_position(self):
        self.actions.update_gap_value(self.song, self.media_player.position())

    def song_changed(self, song):
        self.song = song
        self.media_player.stop()
        self.audio_file_status_changed()
        self.update_button_states(song)
        
    def update_button_states(self, song):
        is_enabled = song is not None
        self.save_current_play_position_btn.setEnabled(is_enabled)
        self.save_detected_gap_btn.setEnabled(is_enabled and song.info.detected_gap > 0)
        self.keep_original_gap_btn.setEnabled(is_enabled)
        self.play_btn.setEnabled(is_enabled)
        self.stop_btn.setEnabled(is_enabled)
        self.vocals_btn.setEnabled(is_enabled)
        self.audio_btn.setEnabled(is_enabled)

        if song:
            self.save_detected_gap_btn.setText(f"Save detected gap ({song.info.detected_gap} ms)")
            self.keep_original_gap_btn.setText(f"Keep gap ({song.gap} ms)")
        else:
            self.save_detected_gap_btn.setText(f"Save detected gap (0 ms)")
            self.keep_original_gap_btn.setText(f"Save gap (0 ms)")

    def audio_file_status_changed(self):
        self.audio_btn.setChecked(self.audioFileStatus == AudioFileStatus.AUDIO)
        self.vocals_btn.setChecked(self.audioFileStatus == AudioFileStatus.VOCALS)
        song=self.song
        self.waveform_label.setPixmap(QPixmap())
        if(not song): return
        if(self.audioFileStatus == AudioFileStatus.AUDIO):
            self.load_media(song.audio_file)
            self.load_waveform(song.audio_waveform_file)
        if(self.audioFileStatus == AudioFileStatus.VOCALS):
            self.load_media(song.vocals_file)
            self.load_waveform(song.vocals_waveform_file)

    def load_media(self, file: str):
        if(os.path.exists(file)):
            self.media_player.setSource(QUrl.fromLocalFile(file))

    def load_waveform(self, file: str):
        if(os.path.exists(file)):
            self.waveform_label.setPixmap(QPixmap(file))

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
        self.positionChanged.emit(newPosition)  # Emit signal with the new position

    def eventFilter(self, watched, event):
        if watched == self.waveform_label and event.type() == QEvent.Type.Resize:
            # Adjust the overlay size to match the waveformLabel
            self.overlay.setFixedSize(self.waveform_label.size())
        return super().eventFilter(watched, event)
    
    def update_position_label(self, position):
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
            self.play_btn.setText("Play")
            self.play_btn.setChecked(False)
            self.media_player.pause()
        else:
            self.play_btn.setText("Pause")
            self.play_btn.setChecked(True)
            self.media_player.play()
    
    def stop(self):
        self.media_player.stop()

    def audio_mode(self):
        self.media_player.stop()
        self.audioFileStatus=AudioFileStatus.AUDIO
        self.audio_file_status_changed()

    def vocals_mode(self):
        self.media_player.stop()
        self.audioFileStatus=AudioFileStatus.VOCALS
        self.audio_file_status_changed()

    def adjust_position(self, milliseconds):
        newPosition = max(0, self.media_player.position() + milliseconds)
        self.media_player.setPosition(newPosition)
