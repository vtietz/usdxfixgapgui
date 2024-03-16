from PyQt6.QtCore import  pyqtSignal, QRunnable
from data import Config
from model.song import Song
from utils.worker_queue_manager import IWorker, IWorkerSignals
import utils.audio as audio

import logging

logger = logging.getLogger(__name__)

class WorkerSignals(IWorkerSignals):
    finished = pyqtSignal(Song)

class DetectGapWorker(QRunnable):
    def __init__(self, song: Song, config: Config):
        super().__init__()
        self.song: Song = song
        self.config = config
        self.signals = WorkerSignals()
        self._isCancelled = False
        self.description = f"Detecting gap for {song.artist} - {song.title}."

    def run(self):
        try:
            audio.process_file(self.song, self.config)
            self.signals.finished.emit(self.song)
        except Exception as e:
            logger.exception(f"Error creating waveform for '{self.song.audio_file}': {e}")
            self.signals.error.emit((e,))

    def cancel(self):
        print("Cancelling vocal extraction...")
        self._isCancelled = True

    def check_cancellation(self):
        return self._isCancelled
    
