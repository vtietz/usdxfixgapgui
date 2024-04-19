from PyQt6.QtCore import pyqtSignal
from model.song import Song
from utils.worker_queue_manager import IWorker, IWorkerSignals
import utils.audio as audio
import utils.usdx as usdx
import utils.detect_gap as detect_gap

import logging

logger = logging.getLogger(__name__)

class WorkerSignals(IWorkerSignals):
    finished = pyqtSignal(int,float)

class DetectGapWorker(IWorker):
    def __init__(self, 
            song: Song,
            tmp_path,
            default_detection_time,
            overwrite=False
        ):
        super().__init__()
        self.song = song
        self.tmp_path = tmp_path
        self.default_detection_time = default_detection_time
        self.overwrite = overwrite
        self.signals = WorkerSignals()
        self._isCancelled = False
        self.description = f"Detecting gap in {song.audio_file}."

    def run(self):
        song: Song = self.song

        audio_file = song.audio_file
        duration = song.duration_ms
        gap = song.gap
        if(song.start):
            gap = gap + (song.start * 1000)
    
        try:
            detected_gap, silence_periods = detect_gap.perform(
                audio_file, 
                self.tmp_path,
                gap, 
                duration,
                self.default_detection_time,
                self.overwrite, 
                self.is_canceled)
            
            vocals_duration_ms = audio.get_audio_duration(song.vocals_file, self.is_canceled)
            notes_overlap = usdx.get_notes_overlap(song.notes, silence_periods, vocals_duration_ms)
            self.signals.finished.emit(detected_gap, notes_overlap)
        except Exception as e:
            logger.exception(f"Error detecting gap for '{audio_file}': {e}")
            self.signals.error.emit((e,))

