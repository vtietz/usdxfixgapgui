import traceback
from utils.worker_queue_manager import IWorker
import utils.audio as audio

import logging

logger = logging.getLogger(__name__)

class NormalizeAudioWorker(IWorker):
    def __init__(self, song):
        super().__init__()
        self.song = song
        self._isCancelled = False
        self.description = f"Normalizing {song.audio_file}."

    def run(self):
        try:
            audio.normalize_audio(self.audio_file)
        except Exception as e:
            stack_trace = traceback.format_exc()
            logger.error(f"Error creating waveform: {e}\nStack trace:\n{stack_trace}")
            self.signals.error.emit((e,))