import logging
import os
import utils.files as files
import shutil
import utils.audio as audio
from utils.separate import separate_audio
from typing import List, Tuple, Optional
from common.config import Config
from utils.types import DetectGapResult
from utils.providers import get_detection_provider
from utils.providers.exceptions import DetectionFailedError

logger = logging.getLogger(__name__)

class DetectGapOptions:
    """Options for gap detection."""
    
    def __init__(self, 
                 audio_file: str,
                 tmp_root: str,
                 original_gap: int,
                 audio_length: Optional[int] = None,
                 default_detection_time: int = 60,
                 silence_detect_params: str = "silencedetect=noise=-10dB:d=0.2",
                 overwrite: bool = False,
                 config: Optional[Config] = None):
        self.audio_file = audio_file
        self.tmp_root = tmp_root
        self.original_gap = original_gap
        self.audio_length = audio_length
        self.default_detection_time = default_detection_time
        self.silence_detect_params = silence_detect_params
        self.overwrite = overwrite
        self.config = config  # Configuration for provider selection


def detect_nearest_gap(silence_periods: List[Tuple[float, float]], start_position_ms: float) -> Optional[int]:
    """Detect the nearest gap before or after the given start position in the audio file."""
    logger.debug(f"Detecting nearest gap relative to {start_position_ms}ms")
    logger.debug(f"Silence periods: {silence_periods}")

    closest_gap_ms = None
    closest_gap_diff_ms = float('inf')  # Initialize with infinity

    # Evaluate both the start and end of each silence period
    for start_ms, end_ms in silence_periods:
        # Calculate the difference from start_position_ms to the start and end of the silence period
        start_diff = abs(start_ms - start_position_ms)
        end_diff = abs(end_ms - start_position_ms)

        # Determine which is closer: the start or the end of the silence period
        if start_diff < closest_gap_diff_ms:
            closest_gap_diff_ms = start_diff
            closest_gap_ms = start_ms

        if end_diff < closest_gap_diff_ms:
            closest_gap_diff_ms = end_diff
            closest_gap_ms = end_ms

    # If a closest gap was found, return its position rounded to the nearest integer
    if closest_gap_ms is not None:
        return int(closest_gap_ms)
    else:
        return None


def detect_nearest_speech_start(speech_segments: List[Tuple[float, float]], start_position_ms: float) -> Optional[int]:
    """
    Detect the nearest speech start boundary relative to the given start position.
    
    Unlike detect_nearest_gap which looks for silence boundaries, this function
    looks specifically for the START of speech segments (vocal onset points).
    
    Args:
        speech_segments: List of (start_ms, end_ms) tuples representing speech periods
        start_position_ms: Reference position in milliseconds (typically original gap)
        
    Returns:
        Position in ms of the nearest speech segment start, or None if no segments found
    """
    logger.debug(f"Detecting nearest speech start relative to {start_position_ms}ms")
    logger.debug(f"Speech segments: {speech_segments}")
    
    if not speech_segments:
        logger.warning("No speech segments provided")
        return None
    
    closest_start_ms = None
    closest_diff_ms = float('inf')
    
    # Only evaluate the START of each speech segment (vocal onset)
    for start_ms, end_ms in speech_segments:
        diff = abs(start_ms - start_position_ms)
        
        if diff < closest_diff_ms:
            closest_diff_ms = diff
            closest_start_ms = start_ms
    
    if closest_start_ms is not None:
        logger.debug(f"Found nearest speech start at {closest_start_ms}ms (diff: {closest_diff_ms}ms)")
        return int(closest_start_ms)
    else:
        logger.warning("No speech start found")
        return None

def get_vocals_file(
        audio_file, 
        temp_root, 
        destination_vocals_filepath, 
        duration: int = 60,
        overwrite = False, 
        check_cancellation = None,
        config: Optional[Config] = None
    ):
    """
    Get vocals file using configured detection provider.
    
    This function now delegates to the appropriate provider based on config.
    Maintains backward compatibility with existing code.
    """
    logger.debug(f"Getting vocals file for {audio_file}...")
    
    if audio_file is None or os.path.exists(audio_file) is False:
        raise Exception(f"Audio file not found: {audio_file}")

    if not overwrite and os.path.exists(destination_vocals_filepath):
        logger.debug(f"Vocals file already exists: {destination_vocals_filepath}")
        return destination_vocals_filepath

    # Use provider system if config available, otherwise fallback to legacy
    if config:
        provider = get_detection_provider(config)
        return provider.get_vocals_file(
            audio_file,
            temp_root,
            destination_vocals_filepath,
            duration,
            overwrite,
            check_cancellation
        )
    else:
        # Legacy Spleeter path (backward compatibility)
        logger.debug("No config provided, using legacy Spleeter path")
        output_path = os.path.join(temp_root, "spleeter")
        vocals_file, instrumental_file = separate_audio(
            audio_file, 
            duration,
            output_path,
            overwrite, 
            check_cancellation=None
        )
        
        if vocals_file is None:
            raise Exception(f"Failed to extract vocals from '{audio_file}'")

        vocals_file = audio.make_clearer_voice(vocals_file, check_cancellation)
        vocals_file = audio.convert_to_mp3(vocals_file, check_cancellation)

        if(vocals_file and destination_vocals_filepath):
            if os.path.exists(destination_vocals_filepath):
                os.remove(destination_vocals_filepath)
            files.move_file(vocals_file, destination_vocals_filepath)
        
        files.rmtree(output_path)

        return destination_vocals_filepath

def perform(options: DetectGapOptions, check_cancellation=None) -> DetectGapResult:
    """
    Perform gap detection with the given options.
    Returns a DetectGapResult with the detected gap, silence periods, and vocals file path.
    Now with extended metadata including confidence, preview, and waveform.
    """
    logger.info(f"Detecting gap for {options.audio_file}")
    if not options.audio_file or not os.path.exists(options.audio_file):
        raise FileNotFoundError(f"Audio file not found: {options.audio_file}")

    tmp_path = files.get_tmp_path(options.tmp_root, options.audio_file)

    if(not options.audio_length):
        duration = audio.get_audio_duration(options.audio_file, check_cancellation)
        options.audio_length = int(duration) if duration else None

    # Calculate the maximum detection time (s), increasing it if necessary
    detection_time = options.default_detection_time
    while detection_time <= options.original_gap / 1000:
        detection_time += options.default_detection_time

    detection_time = detection_time + int(detection_time / 2)

    destination_vocals_file = files.get_vocals_path(tmp_path)
    logger.debug(f"Destination vocals file: {destination_vocals_file}")

    # Get detection provider
    provider = None
    if options.config:
        provider = get_detection_provider(options.config)
        detection_method = provider.get_method_name()
    else:
        detection_method = "spleeter"  # Legacy default

    # detect gap, increasing the detection time if necessary
    while True:
        if os.path.exists(destination_vocals_file) and not options.overwrite:
            vocals_file = destination_vocals_file
        else:
            vocals_file = get_vocals_file(
                options.audio_file, 
                options.tmp_root, 
                destination_vocals_file,
                detection_time,
                options.overwrite,
                check_cancellation,
                config=options.config
            )

        # Detect silence/speech periods using provider
        if provider:
            silence_periods = provider.detect_silence_periods(
                options.audio_file,
                vocals_file,
                check_cancellation=check_cancellation
            )
        else:
            # Legacy fallback
            silence_periods = audio.detect_silence_periods(
                vocals_file, 
                silence_detect_params=options.silence_detect_params,
                check_cancellation=check_cancellation
            )
        
        # Select gap detection method based on provider type
        # VAD returns speech segments, so we look for speech START (vocal onset)
        # Spleeter returns silence periods, so we look for silence boundaries
        if detection_method == "vad_preview":
            # For VAD: speech_segments are returned, find nearest speech START
            detected_gap = detect_nearest_speech_start(silence_periods, options.original_gap)
            logger.debug(f"Using speech-start detection for {detection_method}")
        else:
            # For Spleeter and others: use traditional silence boundary detection
            detected_gap = detect_nearest_gap(silence_periods, options.original_gap)
            logger.debug(f"Using silence-boundary detection for {detection_method}")
        
        if detected_gap is None:
            raise Exception(f"Failed to detect gap in {options.audio_file}")
        
        if detected_gap < detection_time * 1000 or (options.audio_length and detection_time * 1000 >= options.audio_length):
            break

        logger.info(f"Detected GAP seems not to be correct. Increasing detection time to {detection_time + detection_time}s.")
        detection_time += detection_time
 
        if options.audio_length and detection_time >= options.audio_length and detected_gap > options.audio_length:
            raise Exception(f"Error: Unable to detect gap within the length of the audio: {options.audio_file}")

    # Apply spectral flux snapping if enabled (vad_preview only)
    original_detected_gap = detected_gap
    if (detection_method == "vad_preview" and 
        options.config and 
        options.config.flux_snap_enabled):
        try:
            from utils.hpss import find_flux_peak
            
            flux_peak_ms = find_flux_peak(
                options.audio_file,
                float(detected_gap),
                window_ms=options.config.flux_snap_window_ms,
                check_cancellation=check_cancellation
            )
            
            if flux_peak_ms is not None:
                detected_gap = int(flux_peak_ms)
                logger.info(f"Flux snap: {original_detected_gap}ms → {detected_gap}ms (Δ{detected_gap - original_detected_gap:+d}ms)")
            else:
                logger.debug("Flux snap unavailable, using original detection")
        except Exception as e:
            logger.warning(f"Flux snap failed: {e}, using original detection")

    logger.info(f"Detected GAP: {detected_gap}ms in {options.audio_file}")

    # Create result with basic fields
    result = DetectGapResult(detected_gap, silence_periods, vocals_file)
    result.detection_method = detection_method
    result.detected_gap_ms = float(detected_gap)
    
    # Compute confidence if provider available
    if provider:
        try:
            result.confidence = provider.compute_confidence(
                options.audio_file,
                float(detected_gap),
                check_cancellation=check_cancellation
            )
            logger.debug(f"Detection confidence: {result.confidence:.3f}")
        except Exception as e:
            logger.warning(f"Failed to compute confidence: {e}")
            result.confidence = None
    
    # Generate preview and waveform for non-Spleeter methods
    if detection_method != "spleeter" and options.config:
        try:
            from utils.preview import build_vocals_preview
            from utils.waveform_json import build_waveform_json
            
            # Build vocals preview
            preview_file = build_vocals_preview(
                options.audio_file,
                float(detected_gap),
                pre_ms=options.config.vad_preview_pre_ms,
                post_ms=options.config.vad_preview_post_ms,
                vad_segments=silence_periods if detection_method == "vad_preview" else None,
                use_hpss=True,
                output_file=os.path.join(tmp_path, "vocals_preview.wav"),
                check_cancellation=check_cancellation
            )
            result.preview_wav_path = preview_file
            logger.debug(f"Preview created: {preview_file}")
            
            # Generate waveform JSON
            waveform_json = build_waveform_json(
                preview_file,
                output_file=os.path.join(tmp_path, "waveform.json"),
                bins=2048,
                check_cancellation=check_cancellation
            )
            result.waveform_json_path = waveform_json
            logger.debug(f"Waveform JSON created: {waveform_json}")
            
        except Exception as e:
            logger.warning(f"Failed to generate preview/waveform: {e}")
            # Non-fatal - continue with basic result

    return result

