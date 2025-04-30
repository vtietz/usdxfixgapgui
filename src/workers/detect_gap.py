from PySide6.QtCore import Signal as pyqtSignal
from config import Config
from model.gap_info import GapInfoStatus
from model.song import Song, SongStatus
from workers.worker_queue_manager import IWorker, IWorkerSignals
import utils.audio as audio
import utils.usdx as usdx
import utils.detect_gap as detect_gap
import time

import logging

logger = logging.getLogger(__name__)

class WorkerSignals(IWorkerSignals):
    finished = pyqtSignal(Song)

class DetectGapWorker(IWorker):
    def __init__(self, 
            song: Song,
            config: Config,
            tmp_path,
            default_detection_time,
            overwrite=False
        ):
        super().__init__()
        self.signals = WorkerSignals()
        self.song = song
        self.config = config
        self.tmp_path = tmp_path
        self.overwrite = overwrite
        self._isCancelled = False
        self.description = f"Detecting gap in {song.audio_file}."

    async def run(self):
        song: Song = self.song
        audio_file = song.audio_file
        duration_ms = song.duration_ms
        
        gap = song.gap

        # wait 3 seconds
        logger.debug(f"Detecting gap for '{audio_file}' in 3 seconds...")
        time.sleep(3)  
        
        try:
        
            detected_gap, silence_periods = detect_gap.perform(
                audio_file, 
                self.tmp_path,
                gap, 
                duration_ms,
                self.config.default_detection_time,
                self.config.silence_detect_params,
                self.overwrite, 
                self.is_cancelled
            )
            
            detected_gap = usdx.fix_gap(detected_gap, song)
            gap_diff = abs(song.gap - detected_gap)
            info_status = GapInfoStatus.MISMATCH if gap_diff > self.config.gap_tolerance else GapInfoStatus.MATCH
            song_status = SongStatus.MATCH if info_status == GapInfoStatus.MATCH else SongStatus.MISMATCH
            
            vocals_duration_ms = audio.get_audio_duration(song.vocals_file, self.is_cancelled)
            notes_overlap = usdx.get_notes_overlap(song.notes, silence_periods, vocals_duration_ms)

            song.gap_info.detected_gap = detected_gap
            song.gap_info.diff = gap_diff
            song.gap_info.status = info_status
            song.gap_info.notes_overlap = notes_overlap
            song.gap_info.silence_periods = silence_periods
            
            song.status = song_status

            await song.gap_info.save()

            self.signals.finished.emit(song) 
        except Exception as e:
            logger.exception(f"Error detecting gap for '{audio_file}")
            song.error_message = str(e)
            self.signals.error.emit(e)

