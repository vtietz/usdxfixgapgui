import logging
from common.config import Config
from model.song import Song
from managers.worker_queue_manager import IWorker, IWorkerSignals
import utils.waveform as waveform
import utils.audio as audio

logger = logging.getLogger(__name__)

class CreateWaveform(IWorker):
    def __init__(
            self, 
            song: Song,
            config: Config,
            audio_file,
            waveform_file
        ):
        super().__init__()
        self.signals = IWorkerSignals()
        self.song = song
        self.config = config
        self.audio_file = audio_file
        self.waveform_file = waveform_file
        self._isCancelled = False
        self.description = f"Creating waveform for {song.audio_file}."

    async def run(self):
        try:
            self._create_waveform()
            self.signals.finished.emit()  # This matches the base IWorkerSignals.finished
        except Exception as e:
            logger.error(f"Error creating waveform: {self.waveform_file}")
            self.song.error_message = str(e)
            self.signals.error.emit(e)

    def cancel(self):
        logger.debug("Cancelling waveform creation...")
        self._isCancelled = True

    def is_cancelled(self):
        return self._isCancelled

    def _create_waveform(self):
        
        song: Song = self.song
        audio_file = self.audio_file

        duration_ms = audio.get_audio_duration(audio_file)

        waveform_file = self.waveform_file
        title = f"{song.artist} - {song.title}"

        notes = song.notes
        gap = song.gap
        detected_gap = song.gap_info.detected_gap
        silence_periods = song.gap_info.silence_periods

        silence_periods_color = self.config.silence_periods_color
        detected_gap_color = self.config.detected_gap_color
        waveform_color = self.config.waveform_color

        waveform.create_waveform_image(audio_file, waveform_file, waveform_color)

        if(song.gap_info.silence_periods):
            waveform.draw_silence_periods(waveform_file, silence_periods, duration_ms, silence_periods_color)

        waveform.draw_gap(waveform_file, gap, duration_ms, waveform_color)
        if detected_gap:
            waveform.draw_gap(waveform_file, detected_gap, duration_ms, detected_gap_color)
        waveform.draw_notes(waveform_file, notes, duration_ms, waveform_color)
        waveform.draw_title(waveform_file, title, waveform_color)