import logging
import os
from typing import List, Tuple, Optional
from common.config import Config
from utils.result_types import DetectGapResult
from utils.providers import get_detection_provider

logger = logging.getLogger(__name__)


class DetectGapOptions:
    """Options for gap detection."""

    def __init__(
        self,
        audio_file: str,
        tmp_root: str,
        original_gap: int,
        audio_length: Optional[int] = None,
        default_detection_time: int = 60,
        silence_detect_params: str = "silencedetect=noise=-10dB:d=0.2",
        overwrite: bool = False,
        config: Optional[Config] = None,
    ):
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

    # If no silence periods found (vocals start immediately), return 0
    if not silence_periods:
        logger.debug("No silence periods found, vocals start at beginning (gap=0)")
        return 0

    closest_gap_ms = None
    closest_gap_diff_ms = float("inf")  # Initialize with infinity

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
    overwrite=False,
    check_cancellation=None,
    config: Optional[Config] = None,
):
    """
    Get vocals file using configured detection provider.

    Delegates to the appropriate provider based on config settings.
    """
    logger.debug(f"Getting vocals file for {audio_file}...")

    if audio_file is None or os.path.exists(audio_file) is False:
        raise Exception(f"Audio file not found: {audio_file}")

    if not overwrite and os.path.exists(destination_vocals_filepath):
        logger.debug(f"Vocals file already exists: {destination_vocals_filepath}")
        return destination_vocals_filepath

    # Config is required for provider selection
    if not config:
        raise Exception("Config is required for gap detection.")

    provider = get_detection_provider(config)
    return provider.get_vocals_file(
        audio_file, temp_root, destination_vocals_filepath, duration, overwrite, check_cancellation
    )


def perform(options: DetectGapOptions, check_cancellation=None) -> DetectGapResult:
    """
    Perform gap detection with the given options.
    Returns a DetectGapResult with the detected gap, silence periods, and vocals file path.
    Now with extended metadata including confidence, preview, and waveform.
    """
    from utils.gap_detection import perform

    if not options.config:
        raise ValueError("Config is required for gap detection")

    logger.debug("Using gap detection pipeline")
    return perform(
        audio_file=options.audio_file,
        tmp_root=options.tmp_root,
        original_gap=options.original_gap,
        audio_length=options.audio_length,
        default_detection_time=options.default_detection_time,
        config=options.config,
        overwrite=options.overwrite,
        check_cancellation=check_cancellation,
    )
