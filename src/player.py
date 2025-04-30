from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication, QMainWindow
import sys

class AudioPlayer(QMainWindow):
    def __init__(self):
        super().__init__()

        # Create a media player
        self.media_player = QMediaPlayer()

        # Create an audio output
        self.audio_output = QAudioOutput()
        self.media_player.setAudioOutput(self.audio_output)

        # Load the MP3 file
        self.media_player.setSource(QUrl.fromLocalFile("../samples/ABBA - Happy New Year/ABBA - Happy New Year.mp3"))

        # Play the audio
        self.media_player.play()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    player = AudioPlayer()
    player.show()
    sys.exit(app.exec())