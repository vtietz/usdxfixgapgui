import utils.waveform as waveform
from PyQt6.QtCore import pyqtSignal, QRunnable
from utils.worker_queue_manager import IWorker, IWorkerSignals

class CreateWaveform(QRunnable):
        
    signals = IWorkerSignals()
     
    def __init__(
            self, 
            audio_file, 
            duration_ms, 
            waveform_file, 
            song_title, 
            notes, 
            bpm, 
            gap, 
            detected_gap, 
            is_relative,
            detected_gap_color = "blue",
            waveform_color = "gray"
            ):
        super().__init__()
        self.audio_file = audio_file
        self.duration_ms = duration_ms
        self.waveform_file = waveform_file
        self.song_title = song_title
        self.notes = notes
        self.bpm = bpm
        self.gap = gap
        self.detected_gap = detected_gap
        self.is_relative = is_relative
        self.detected_gap_color = detected_gap_color
        self.waveform_color = waveform_color
        self._isCancelled = False
        self.description = f"Creating waveform for {audio_file}."

    def run(self):
        try:
            self._create_waveform()
            self.signals.finished.emit()
        except Exception as e:
            self.signals.error.emit((e,))

    def cancel(self):
        print("Cancelling waveform creation...")
        self._isCancelled = True

    def check_cancellation(self):
        return self._isCancelled

    def _create_waveform(self):
        
        audio_file = self.audio_file
        duration_ms = self.duration_ms
        waveform_file = self.waveform_file
        song_title = self.song_title
        notes = self.notes
        bpm = self.bpm
        gap = self.gap
        detected_gap = self.detected_gap
        is_relative = self.is_relative
        detected_gap_color = self.detected_gap_color
        waveform_color = self.waveform_color

        waveform.create_waveform_image(audio_file, waveform_file, waveform_color)
        waveform.draw_gap(waveform_file, gap, duration_ms, waveform_color)
        waveform.draw_gap(waveform_file, detected_gap, duration_ms, detected_gap_color)
        waveform.draw_notes(waveform_file, notes, bpm, gap, duration_ms, waveform_color, is_relative)
        waveform.draw_title(waveform_file, song_title, waveform_color)