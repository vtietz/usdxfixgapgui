import os
import time
from typing import List, Tuple, Optional
from PySide6.QtCore import Signal
from common.config import Config
from model.gap_info import GapInfoStatus
from model.song import Song, SongStatus
from model.usdx_file import Note
from managers.worker_queue_manager import IWorker, IWorkerSignals
import utils.audio as audio
import utils.usdx as usdx
import utils.detect_gap as detect_gap
from utils.detect_gap import DetectGapOptions, DetectGapResult
from services.gap_info_service import GapInfoService

import logging

logger = logging.getLogger(__name__)

class DetectGapWorkerOptions:
    """Options for the DetectGapWorker."""
    
    def __init__(self, 
                 audio_file: str,
                 txt_file: str,
                 notes: List[Note],
                 bpm,
                 original_gap: int,
                 duration_ms: int,
                 config: Config,
                 tmp_path: str,
                 overwrite=False):
        self.audio_file = audio_file
        self.txt_file = txt_file
        self.notes = notes
        self.original_gap = original_gap
        self.duration_ms = duration_ms
        self.config = config
        self.tmp_path = tmp_path
        self.overwrite = overwrite
        self.bpm = bpm

class GapDetectionResult:
    """Class to hold gap detection results separate from the Song object."""
    
    def __init__(self, song_file_path: str):
        # Reference to identify which song this relates to
        self.song_file_path = song_file_path
        
        # Detection results
        self.detected_gap: Optional[int] = None
        self.original_gap: Optional[int] = None
        self.silence_periods: Optional[List[Tuple[float, float]]] = None
        self.gap_diff: Optional[int] = None
        self.notes_overlap: Optional[float] = None
        self.duration_ms: Optional[float] = None
        self.status: Optional[GapInfoStatus] = None
        self.error: Optional[str] = None
        
        # Extended detection metadata
        self.confidence: Optional[float] = None
        self.detection_method: str = "unknown"
        self.preview_wav_path: Optional[str] = None
        self.waveform_json_path: Optional[str] = None
        self.detected_gap_ms: Optional[float] = None

class WorkerSignals(IWorkerSignals):
    finished = Signal(GapDetectionResult)
    
class DetectGapWorker(IWorker):
    def __init__(self, options: DetectGapWorkerOptions):
        super().__init__()
        self.signals = WorkerSignals()
        self.options = options
        self._isCancelled = False
        self.description = f"Detecting gap in {options.audio_file}."

    async def run(self):
        result = GapDetectionResult(self.options.txt_file)
        result.original_gap = self.options.original_gap
        
        try:
            # wait 3 seconds (if needed for testing)
            logger.debug(f"Detecting gap for '{self.options.audio_file}' in 3 seconds...")
            time.sleep(3)
            
            # Create detect gap options with config
            detect_options = DetectGapOptions(
                audio_file=self.options.audio_file,
                tmp_root=self.options.tmp_path,
                original_gap=self.options.original_gap,
                audio_length=self.options.duration_ms,
                default_detection_time=self.options.config.default_detection_time,
                silence_detect_params=self.options.config.spleeter_silence_detect_params,
                overwrite=self.options.overwrite,
                config=self.options.config  # Pass config for provider selection
            )
            
            # Perform gap detection
            detection_result = detect_gap.perform(detect_options, self.is_cancelled)
            
            # Fix gap based on the song's BPM and other factors
            if self.options.notes and self.options.bpm:
                detected_gap = usdx.fix_gap(detection_result.detected_gap, self.options.notes[0].StartBeat, self.options.bpm)
            else:
                detected_gap = detection_result.detected_gap
                logger.warning("No notes or BPM provided, so no correction of gap if first note does not start on beat 0 or song has a start time.")
            gap_diff = abs(self.options.original_gap - detected_gap)
            
            # Determine status
            info_status = GapInfoStatus.MISMATCH if gap_diff > self.options.config.gap_tolerance else GapInfoStatus.MATCH
            
            # Get vocals duration for notes overlap calculation
            vocals_duration_ms = audio.get_audio_duration(detection_result.vocals_file, self.is_cancelled)
            notes_overlap = usdx.get_notes_overlap(self.options.notes, detection_result.silence_periods, vocals_duration_ms)
            
            # Populate the result with basic fields
            result.detected_gap = detected_gap
            result.silence_periods = detection_result.silence_periods
            result.gap_diff = gap_diff
            result.notes_overlap = notes_overlap
            result.status = info_status
            
            # Populate extended detection metadata
            result.confidence = detection_result.confidence
            result.detection_method = detection_result.detection_method
            result.preview_wav_path = detection_result.preview_wav_path
            result.waveform_json_path = detection_result.waveform_json_path
            result.detected_gap_ms = detection_result.detected_gap_ms
            
            # Set duration if available
            if self.options.duration_ms:
                result.duration_ms = self.options.duration_ms
            else:
                result.duration_ms = audio.get_audio_duration(self.options.audio_file, self.is_cancelled)
                
            self.signals.finished.emit(result)
            
        except Exception as e:
            logger.exception(f"Error detecting gap for '{self.options.audio_file}'")
            result.error = str(e)
            self.signals.error.emit(e)
            # We should still emit the result with the error
            self.signals.finished.emit(result)