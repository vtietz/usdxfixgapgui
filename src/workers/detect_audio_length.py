from PyQt6.QtCore import pyqtSignal
from model.song import Song
from utils.worker_queue_manager import IWorker, IWorkerSignals
from utils.run_async import run_async
import utils.audio as audio
import traceback
import logging

logger = logging.getLogger(__name__)

class WorkerSignals(IWorkerSignals):
    lengthDetected = pyqtSignal(Song)  

class DetectAudioLengthWorker(IWorker):
    def __init__(self, song: Song):
        super().__init__()
        if not song:
            raise Exception("No song given")
        self.description = f"Detecting length of audio {song.audio_file}."
        self.song = song
        self.signals = WorkerSignals()

    def run(self):
        logger.debug(self.description)
        try:
            duration = audio.get_audio_duration(self.song.audio_file)
            self.song.duration_ms = duration
            self.song.gap_info.duration = duration
            run_async(self.song.gap_info.save(), lambda: self.signals.lengthDetected.emit(self.song))
        except Exception as e:
            stack_trace = traceback.format_exc()
            logger.error(f"Error detecting audio length song '{self.audio_file}': {e}\nStack trace:\n{stack_trace}")           
            self.signals.error.emit((e,))

        if not self.is_canceled():
            self.signals.finished.emit()
            logger.debug("Canceled detecting audio length.")
