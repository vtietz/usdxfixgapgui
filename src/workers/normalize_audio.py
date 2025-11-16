from model.song import Song
from managers.worker_queue_manager import IWorker
import utils.audio as audio
from app.app_data import AppData
from services.gap_info_service import GapInfoService  # Add this import

import logging

logger = logging.getLogger(__name__)


class NormalizeAudioWorker(IWorker):
    def __init__(self, song: Song):
        super().__init__()
        self.song = song
        self._isCancelled = False
        self.description = f"Normalizing {song.audio_file}."
        # Get the configuration
        self.config = AppData().config

    async def run(self):
        try:
            # Use the normalization level from config
            normalization_level = self.config.normalization_level
            audio.normalize_audio(
                self.song.audio_file, target_level=normalization_level, check_cancellation=self.is_cancelled
            )

            # Update normalization info using service
            GapInfoService.set_normalized(self.song.gap_info, normalization_level)
            await GapInfoService.save(self.song.gap_info)
            logger.info(f"Audio normalized to {normalization_level} dB and info saved: {self.song.audio_file}")

        except Exception as e:
            logger.error(f"Error normalizing audio: {self.song.audio_file}")
            self.save_error_to_song(self.song, e)
            self.signals.error.emit(e)

        # Always emit finished signal, even if cancelled
        self.signals.finished.emit()
