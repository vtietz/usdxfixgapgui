from enum import Enum
import os
import sys
from PyQt6.QtWidgets import  QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtCore import QUrl, Qt, pyqtSignal, QPoint, QEvent
from PyQt6.QtGui import QPainter, QPen, QPixmap

from data import AppData
from model.song import Song

class AudioFileStatus(Enum):
    AUDIO = 0
    VOCALS = 1

class MediaPlayerComponent(QWidget):

    positionChanged = pyqtSignal(int)
    audioFileStatusChanged = pyqtSignal(AudioFileStatus)

    audioFileStatus: AudioFileStatus = AudioFileStatus.AUDIO
    song: Song = None

    currentPosition = 0 
    def __init__(self, data: AppData, parent=None):
        super().__init__(parent)
        self.data = data

        self.mediaPlayer = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.mediaPlayer.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(50)
        
        buttonsLayout = QHBoxLayout()

        self.playButton = QPushButton("Play")
        self.playButton.setCheckable(True)
        self.stopButton = QPushButton("Stop")

        self.audioButton = QPushButton("Audio")
        self.audioButton.setCheckable(True)
        self.vocalsButton = QPushButton("Vocals")
        self.vocalsButton.setCheckable(True)

        buttonsLayout.addWidget(self.playButton)
        buttonsLayout.addWidget(self.stopButton)

        buttonsLayout.addWidget(self.audioButton)
        buttonsLayout.addWidget(self.vocalsButton)
        
        layout = QVBoxLayout()
        layout.addLayout(buttonsLayout)
        self.setLayout(layout)
        
        waveformLayout = QVBoxLayout()
        waveformLayout.setContentsMargins(0, 0, 0, 0) 
        self.waveformLabel = QLabel()
        self.waveformLabel.setStyleSheet("padding: 0px; margin: 0px;")
        self.waveformLabel.setFixedHeight(150)  # Set a fixed height for the waveform display area
        self.waveformLabel.setScaledContents(True) 
        self.waveformLabel.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.waveformLabel.installEventFilter(self)
        waveformLayout.addWidget(self.waveformLabel)

        layout.addLayout(waveformLayout)

        labels = QHBoxLayout()
        self.positionLabel = QLabel('00:00:000 (0 ms)')
        self.positionLabel.setStyleSheet("color: red;")
        labels.addWidget(self.positionLabel)

        self.gapLabel = QLabel('0 ms')
        self.gapLabel.setStyleSheet("color: gray;")
        labels.addWidget(self.gapLabel)

        self.detectedGapLabel = QLabel('0 ms')
        self.detectedGapLabel.setStyleSheet("color: blue;")
        labels.addWidget(self.detectedGapLabel)

        layout.addLayout(labels)

        # Overlay for showing the current play position
        self.overlay = QWidget(self.waveformLabel)
        self.overlay.setFixedSize(self.waveformLabel.size())
        self.overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)  # Allow clicks to pass through
        self.overlay.paintEvent = self.paintOverlay

        self.mediaPlayer.positionChanged.connect(self.updateOverlayPosition)
        self.waveformLabel.mousePressEvent = self.changePlayPosition
        
        data.selectedSongChanged.connect(self.songChanged)

        self.playButton.clicked.connect(self.play)
        self.stopButton.clicked.connect(self.stop)

        self.audioButton.clicked.connect(self.audioMode)
        self.vocalsButton.clicked.connect(self.vocalsMode)

        self.mediaPlayer.positionChanged.connect(self.updatePositionLabel)

        self.audioFileStatusChanged()

    def songChanged(self, song):
        self.song = song
        self.audioFileStatusChanged()
        self.gapLabel.setText(f"{song.gap} ms")
        self.detectedGapLabel.setText(f"{song.info.detected_gap} ms")

    def audioFileStatusChanged(self):
        self.audioButton.setChecked(self.audioFileStatus == AudioFileStatus.AUDIO)
        self.vocalsButton.setChecked(self.audioFileStatus == AudioFileStatus.VOCALS)
        song=self.song
        self.waveformLabel.setPixmap(QPixmap())
        if(not song): return
        if(self.audioFileStatus == AudioFileStatus.AUDIO):
            self.loadMedia(song.audio_file)
            self.loadWaveform(song.audio_waveform_file)
        if(self.audioFileStatus == AudioFileStatus.VOCALS):
            self.loadMedia(song.vocals_file)
            self.loadWaveform(song.vocals_waveform_file)

    def loadMedia(self, file: str):
        if(os.path.exists(file)):
            self.mediaPlayer.setSource(QUrl.fromLocalFile(file))

    def loadWaveform(self, file: str):
        if(os.path.exists(file)):
            self.waveformLabel.setPixmap(QPixmap(file))

    def paintOverlay(self, event):
        painter = QPainter(self.overlay)
        pen = QPen(Qt.GlobalColor.red, 2)
        painter.setPen(pen)
        # Convert x to an integer to ensure it matches the expected argument type
        x = int(self.currentPosition * self.overlay.width())
        painter.drawLine(x, 0, x, self.overlay.height())


    def updateOverlayPosition(self, position):
        duration = self.mediaPlayer.duration()
        if duration > 0:
            self.currentPosition = position / duration
            self.overlay.update()  # Trigger a repaint
        else:
            self.currentPosition = 0


    def changePlayPosition(self, event):
        # Calculate the new position based on the click event and set the media player's position
        clickPosition = event.position().x()  # Get the X coordinate of the click
        newPosition = (clickPosition / self.waveformLabel.width()) * self.mediaPlayer.duration()
        # Convert newPosition to an integer
        newPosition = int(newPosition)
        self.mediaPlayer.setPosition(newPosition)
        self.positionChanged.emit(newPosition)  # Emit signal with the new position

    def eventFilter(self, watched, event):
        if watched == self.waveformLabel and event.type() == QEvent.Type.Resize:
            # Adjust the overlay size to match the waveformLabel
            self.overlay.setFixedSize(self.waveformLabel.size())
        return super().eventFilter(watched, event)
    
    def updatePositionLabel(self, position):
        # Convert position from milliseconds to minutes:seconds:milliseconds
        minutes = position // 60000
        seconds = (position % 60000) // 1000
        milliseconds = position % 1000
        # Update the label
        self.positionLabel.setText(f'{minutes:02d}:{seconds:02d}:{milliseconds:03d} ({position} ms)')

    def play(self):
        print(self.mediaPlayer.playbackState())
        if self.mediaPlayer.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.playButton.setText("Play")
            self.playButton.setChecked(False)
            self.mediaPlayer.pause()
        else:
            self.playButton.setText("Pause")
            self.playButton.setChecked(True)
            self.mediaPlayer.play()
    
    def stop(self):
        self.mediaPlayer.stop()

    def audioMode(self):
        self.mediaPlayer.stop()
        self.audioFileStatus=AudioFileStatus.AUDIO
        self.audioFileStatusChanged()

    def vocalsMode(self):
        self.mediaPlayer.stop()
        self.audioFileStatus=AudioFileStatus.VOCALS
        self.audioFileStatusChanged()