import logging
import os
import utils.files as files
import shutil
import utils.audio as audio
from utils.separate import separate_audio
from typing import List, Tuple, Optional
from common.config import Config

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

class DetectGapResult:
    """Results of gap detection."""
    
    def __init__(self, detected_gap: int, silence_periods: List[Tuple[float, float]], vocals_file: str):
        self.detected_gap = detected_gap
        self.silence_periods = silence_periods
        self.vocals_file = vocals_file
        # Extended fields for new detection metadata
        self.confidence: Optional[float] = None
        self.detection_method: str = "unknown"
        self.preview_wav_path: Optional[str] = None
        self.waveform_json_path: Optional[str] = None
        self.detected_gap_ms: Optional[float] = None

def detect_nearest_gap(silence_periods: List[Tuple[float, float]], start_position_ms: float) -> int:
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
        from utils.detection_provider import get_detection_provider
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
        from utils.detection_provider import get_detection_provider
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
        
        detected_gap = detect_nearest_gap(silence_periods, options.original_gap)
        if detected_gap is None:
            raise Exception(f"Failed to detect gap in {options.audio_file}")
        
        if detected_gap < detection_time * 1000 or (options.audio_length and detection_time * 1000 >= options.audio_length):
            break

        logger.info(f"Detected GAP seems not to be correct. Increasing detection time to {detection_time + detection_time}s.")
        detection_time += detection_time
 
        if options.audio_length and detection_time >= options.audio_length and detected_gap > options.audio_length:
            raise Exception(f"Error: Unable to detect gap within the length of the audio: {options.audio_file}")

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

