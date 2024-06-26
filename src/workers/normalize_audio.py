from model.song import Song
from workers.worker_queue_manager import IWorker
import utils.audio as audio

import logging

logger = logging.getLogger(__name__)

class NormalizeAudioWorker(IWorker):
    def __init__(self, song: Song):
        super().__init__()
        self.song = song
        self._isCancelled = False
        self.description = f"Normalizing {song.audio_file}."

    async def run(self):
        try:
            audio.normalize_audio(self.song.audio_file, target_level=-23, check_cancellation=self.is_cancelled)
            self.signals.finished.emit()
        except Exception as e:
            logger.error(f"Error normalizing audio: {self.song.audio_file}")
            self.song.error_message = str(e)
            self.signals.error.emit(e)