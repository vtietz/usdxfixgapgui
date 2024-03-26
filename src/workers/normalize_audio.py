import traceback
from model.song import Song
from utils.worker_queue_manager import IWorker
import utils.audio as audio

import logging

logger = logging.getLogger(__name__)

class NormalizeAudioWorker(IWorker):
    def __init__(self, song: Song):
        super().__init__()
        self.song = song
        self._isCancelled = False
        self.description = f"Normalizing {song.audio_file}."

    def run(self):
        try:
            audio.normalize_audio(self.song.audio_file, target_level=-23, check_cancellation=self.is_canceled)
            self.signals.finished.emit()
        except Exception as e:
            stack_trace = traceback.format_exc()
            logger.error(f"Error creating waveform: {e}\nStack trace:\n{stack_trace}")
            self.signals.error.emit((e,))