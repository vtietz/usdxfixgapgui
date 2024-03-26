from model.song import Song
import utils.waveform as waveform
from utils.worker_queue_manager import IWorker, IWorkerSignals
import utils.audio as audio
import logging
import traceback

logger = logging.getLogger(__name__)

class CreateWaveform(IWorker):
        
    signals = IWorkerSignals()
     
    def __init__(
            self, 
            song,
            audio_file,
            waveform_file,
            detected_gap_color = "blue",
            waveform_color = "gray"
            ):
        super().__init__()
        self.song = song
        self.audio_file = audio_file
        self.waveform_file = waveform_file
        self.detected_gap_color = detected_gap_color
        self.waveform_color = waveform_color
        self._isCancelled = False
        self.description = f"Creating waveform for {song.audio_file}."

    def run(self):
        try:
            self._create_waveform()
            self.signals.finished.emit()
        except Exception as e:
            stack_trace = traceback.format_exc()
            logger.error(f"Error creating waveform: {e}\nStack trace:\n{stack_trace}")
            self.signals.error.emit((e,))

    def cancel(self):
        print("Cancelling waveform creation...")
        self._isCancelled = True

    def check_cancellation(self):
        return self._isCancelled

    def _create_waveform(self):
        
        song: Song = self.song
        audio_file = self.audio_file

        duration_ms = audio.get_audio_duration(audio_file)

        waveform_file = self.waveform_file
        title = f"{song.artist} - {song.title}"

        notes = song.notes
        bpm = song.bpm
        gap = song.gap
        detected_gap = song.gap_info.detected_gap
        is_relative = song.is_relative
        detected_gap_color = self.detected_gap_color
        waveform_color = self.waveform_color

        waveform.create_waveform_image(audio_file, waveform_file, waveform_color)
        waveform.draw_gap(waveform_file, gap, duration_ms, waveform_color)
        if detected_gap:
            waveform.draw_gap(waveform_file, detected_gap, duration_ms, detected_gap_color)
        waveform.draw_notes(waveform_file, notes, bpm, gap, duration_ms, waveform_color, is_relative)
        waveform.draw_title(waveform_file, title, waveform_color)