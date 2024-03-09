import os
import sys
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel
from PyQt6.QtMultimedia import QMediaPlayer
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtCore import QUrl, Qt, pyqtSignal, QPoint
from PyQt6.QtGui import QPainter, QPen, QPixmap

from data import AppData

class MediaPlayerComponent(QWidget):

    positionChanged = pyqtSignal(int)  # Signal to emit when the play position changes

    currentPosition = 0 

    def __init__(self, data: AppData, parent=None):
        super().__init__(parent)
        self.data = data

        data.selectedSongChanged.connect(self.songChanged)

        self.mediaPlayer = QMediaPlayer()
        self.videoWidget = QVideoWidget()

        layout = QVBoxLayout()
        layout.addWidget(self.videoWidget)
        self.setLayout(layout)

        # Waveform display (using a QLabel for simplicity; consider a custom QWidget for more complex drawing)
        self.waveformLabel = QLabel()
        self.waveformLabel.setFixedHeight(100)  # Set a fixed height for the waveform display area
        layout.addWidget(self.waveformLabel)

        # Set up media player
        self.mediaPlayer.setVideoOutput(self.videoWidget)

        # Overlay for showing the current play position
        self.overlay = QWidget(self.waveformLabel)
        self.overlay.setFixedSize(self.waveformLabel.size())
        self.overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)  # Allow clicks to pass through
        self.overlay.paintEvent = self.paintOverlay

        self.mediaPlayer.positionChanged.connect(self.updateOverlayPosition)
        self.waveformLabel.mousePressEvent = self.changePlayPosition

    def songChanged(self, song):
        if os.path.exists(song.vocal_file):
            self.mediaPlayer.setSource(QUrl.fromLocalFile(song.vocal_file))
        else:
            print(f"File not found: {song.vocal_file}")
            self.mediaPlayer.setSource(QUrl(""))
        if os.path.exists(song.waveform_file):
            self.waveformLabel.setPixmap(QPixmap(song.waveform_file))
        else:
            print(f"File not found: {song.waveform_file}")
            self.waveformLabel.setPixmap(QPixmap())
       
    def paintOverlay(self, event):
        # Custom painting code for the play position line
        painter = QPainter(self.overlay)
        pen = QPen(Qt.GlobalColor.red, 2)
        painter.setPen(pen)
        # This example assumes self.currentPosition is a percentage of the total width
        x = self.currentPosition * self.overlay.width()
        painter.drawLine(x, 0, x, self.overlay.height())

    def updateOverlayPosition(self, position):
        # Update currentPosition based on the media player's position
        # This is a placeholder; you'll need to calculate currentPosition based on the duration and current position
        self.currentPosition = position / self.mediaPlayer.duration()
        self.overlay.update()  # Trigger a repaint of the overlay

    def changePlayPosition(self, event):
        # Calculate the new position based on the click event and set the media player's position
        clickPosition = event.position().x()  # Get the X coordinate of the click
        newPosition = (clickPosition / self.waveformLabel.width()) * self.mediaPlayer.duration()
        self.mediaPlayer.setPosition(newPosition)
        self.positionChanged.emit(newPosition)  # Emit signal with the new position

    def play(self):
        self.mediaPlayer.play()
