import logging
from PySide6.QtCore import Signal as pyqtSignal
from model.song import Song
from managers.worker_queue_manager import IWorker, IWorkerSignals
import utils.audio as audio
from services.gap_info_service import GapInfoService

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

    async def run(self):
        logger.debug(self.description)
        try:
            duration = audio.get_audio_duration(self.song.audio_file)
            self.song.duration_ms = duration
            self.song.gap_info.duration = duration
            # Use service to save gap info
            await GapInfoService.save(self.song.gap_info)
            if not self.is_cancelled():
                self.signals.lengthDetected.emit(self.song)
        except Exception as e:
            logger.error(f"Error detecting audio length song '{self.song.audio_file}'")
            self.song.error_message = str(e)
            self.signals.error.emit(e)

        # Always emit finished signal, even if cancelled
        self.signals.finished.emit()
        if self.is_cancelled():
            logger.debug("Cancelled detecting audio length.")
        else:
            logger.debug("Finished detecting audio length.")
