from PyQt6.QtCore import pyqtSignal
from utils.worker_queue_manager import IWorker, IWorkerSignals
import utils.audio as audio

import logging

logger = logging.getLogger(__name__)

class WorkerSignals(IWorkerSignals):
    finished = pyqtSignal(int)

class DetectGapWorker(IWorker):
    def __init__(self, 
            audio_file, 
            tmp_path,
            bpm, 
            gap, 
            duration,
            default_detection_time, 
            overwrite=False
        ):
        super().__init__()
        self.audio_file = audio_file
        self.tmp_path = tmp_path
        self.bpm = bpm
        self.gap = gap
        self.duration = duration
        self.default_detection_time = default_detection_time
        self.overwrite = overwrite
        self.signals = WorkerSignals()
        self._isCancelled = False
        self.description = f"Detecting gap in {audio_file}."

    def run(self):
        try:
            logger.debug(self.is_canceled)
            detected_gap = audio.detect_gap(
                self.audio_file, 
                self.tmp_path,
                self.gap, 
                self.duration,
                self.default_detection_time, 
                self.overwrite, 
                self.is_canceled)
            self.signals.finished.emit(detected_gap)
        except Exception as e:
            logger.exception(f"Error detecting gap for '{self.audio_file}': {e}")
            self.signals.error.emit((e,))

