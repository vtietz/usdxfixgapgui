import os
from PySide6.QtCore import QTimer, QUrl
from PySide6.QtMultimedia import QMediaPlayer


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
