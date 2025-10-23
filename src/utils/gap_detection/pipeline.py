"""Gap detection pipeline - modular implementation.

This module provides gap detection that breaks
down the monolithic perform() function into pure, testable components.

Architecture:
    Input -> Validate -> Normalize -> Detect -> Post-process -> Output
    
Each step is a pure function with clear inputs/outputs and no side effects.
This improves testability, maintainability, and code clarity.
"""

import logging
import os
from dataclasses import dataclass
from typing import List, Tuple, Optional, Callable, Sequence

import utils.audio as audio
import utils.files as files
from common.config import Config
from utils.providers import get_detection_provider
from utils.types import DetectGapResult

logger = logging.getLogger(__name__)


@dataclass
class GapDetectionContext:
    """Immutable context for gap detection pipeline.
    
    Contains all parameters needed for detection in a validated,
    normalized format. This eliminates parameter passing complexity
    and ensures consistency across pipeline steps.
    """
    audio_file: str
    original_gap_ms: float
    detection_time_sec: int
    audio_length_ms: Optional[int]
    tmp_root: str
    config: Config
    overwrite: bool
    start_window_sec: int = 30
    window_increment_sec: int = 15
    window_max_sec: int = 90
    
    def __post_init__(self):
        """Validate inputs immediately after construction."""
        if not self.audio_file:
            raise ValueError("Audio file path is required")
        if not os.path.exists(self.audio_file):
            raise FileNotFoundError(f"Audio file not found: {self.audio_file}")
        if self.original_gap_ms < 0:
            raise ValueError("Original gap cannot be negative")
        if not self.config:
            raise ValueError("Config is required for gap detection")


def validate_inputs(
    audio_file: str,
    original_gap: int,
    audio_length: Optional[int],
    config: Optional[Config]
) -> None:
    """Validate gap detection inputs with clear error messages.
    
    Args:
        audio_file: Path to audio file
        original_gap: Original gap value in milliseconds
        audio_length: Optional audio length in milliseconds
        config: Configuration object
        
    Raises:
        ValueError: If inputs are invalid
        FileNotFoundError: If audio file doesn't exist
    """
    if not audio_file:
        raise ValueError("Audio file path is required")
    
    if not os.path.exists(audio_file):
        raise FileNotFoundError(f"Audio file not found: {audio_file}")
    
    if original_gap < 0:
        raise ValueError(f"Original gap cannot be negative: {original_gap}")
    
    if audio_length is not None and audio_length < 0:
        raise ValueError(f"Audio length cannot be negative: {audio_length}")
    
    if not config:
        raise ValueError("Config is required for gap detection")


def calculate_detection_time(
    original_gap_ms: float,
    default_detection_time_sec: int
) -> int:
    """Calculate optimal detection time window.
    
    Ensures detection window is large enough to capture the gap.
    Uses a 1.5x multiplier to provide buffer beyond the expected gap.
    
    Args:
        original_gap_ms: Original gap in milliseconds
        default_detection_time_sec: Default detection window in seconds
        
    Returns:
        Detection time in seconds
        
    Example:
        >>> calculate_detection_time(5000, 60)  # 5s gap, 60s default
        60  # Default is sufficient
        >>> calculate_detection_time(65000, 60)  # 65s gap
        97  # (60 + 60) * 1.5 = 180s, but incremented to 120 then 1.5x = 180
    """
    detection_time_sec = default_detection_time_sec
    original_gap_sec = original_gap_ms / 1000
    
    # Increment detection time until it's larger than the gap
    while detection_time_sec <= original_gap_sec:
        detection_time_sec += default_detection_time_sec
    
    # Add 50% buffer
    detection_time_sec = detection_time_sec + int(detection_time_sec / 2)
    
    return detection_time_sec


def normalize_context(
    audio_file: str,
    tmp_root: str,
    original_gap: int,
    audio_length: Optional[int],
    default_detection_time: int,
    config: Config,
    overwrite: bool,
    check_cancellation: Optional[Callable] = None
) -> GapDetectionContext:
    """Normalize inputs into immutable detection context.
    
    Converts raw inputs into validated, normalized context object.
    Handles audio length detection if not provided.
    
    Args:
        audio_file: Path to audio file
        tmp_root: Temporary directory root
        original_gap: Original gap in milliseconds
        audio_length: Optional audio length in milliseconds
        default_detection_time: Default detection window in seconds
        config: Configuration object
        overwrite: Whether to overwrite existing files
        check_cancellation: Optional cancellation callback
        
    Returns:
        GapDetectionContext with normalized values
    """
    # Validate inputs first
    validate_inputs(audio_file, original_gap, audio_length, config)
    
    # Detect audio length if not provided
    if audio_length is None:
        duration = audio.get_audio_duration(audio_file, check_cancellation)
        audio_length = int(duration * 1000) if duration else None
    
    # Calculate detection time
    detection_time = calculate_detection_time(
        float(original_gap),
        default_detection_time
    )
    
    return GapDetectionContext(
        audio_file=audio_file,
        original_gap_ms=float(original_gap),
        detection_time_sec=detection_time,
        audio_length_ms=audio_length,
        tmp_root=tmp_root,
        config=config,
        overwrite=overwrite,
        start_window_sec=config.vocal_start_window_sec,
        window_increment_sec=config.vocal_window_increment_sec,
        window_max_sec=config.vocal_window_max_sec
    )


def get_or_create_vocals(
    ctx: GapDetectionContext,
    check_cancellation: Optional[Callable] = None,
    provider = None
) -> str:
    """Get or create vocals file for detection.
    
    I/O boundary - handles file system operations.
    
    Args:
        ctx: Detection context
        check_cancellation: Optional cancellation callback
        provider: Optional detection provider (reused if provided)
        
    Returns:
        Path to vocals file
    """
    tmp_path = files.get_tmp_path(ctx.tmp_root, ctx.audio_file)
    destination_vocals_file = files.get_vocals_path(tmp_path)
    
    logger.debug(f"Destination vocals file: {destination_vocals_file}")
    
    # Check if vocals file already exists
    if os.path.exists(destination_vocals_file) and not ctx.overwrite:
        logger.debug(f"Using existing vocals file: {destination_vocals_file}")
        return destination_vocals_file
    
    # Get provider if not provided (for reuse)
    if provider is None:
        provider = get_detection_provider(ctx.config)
    
    vocals_file = provider.get_vocals_file(
        ctx.audio_file,
        ctx.tmp_root,
        destination_vocals_file,
        ctx.detection_time_sec,
        ctx.overwrite,
        check_cancellation
    )
    
    return vocals_file


def detect_silence_periods(
    ctx: GapDetectionContext,
    vocals_file: str,
    check_cancellation: Optional[Callable] = None,
    provider = None
) -> List[Tuple[float, float]]:
    """Detect silence periods in vocals file.
    
    Delegates to detection provider for actual analysis.
    
    Args:
        ctx: Detection context
        vocals_file: Path to vocals file
        check_cancellation: Optional cancellation callback
        provider: Optional detection provider (reused if provided)
        
    Returns:
        List of (start_ms, end_ms) silence periods
    """
    # Get provider if not provided (for reuse)
    if provider is None:
        provider = get_detection_provider(ctx.config)
    
    silence_periods = provider.detect_silence_periods(
        ctx.audio_file,
        vocals_file,
        original_gap_ms=ctx.original_gap_ms,
        check_cancellation=check_cancellation
    )
    
    logger.debug(f"Detected {len(silence_periods)} silence periods")
    return silence_periods


def detect_gap_from_silence(
    silence_periods: Sequence[Tuple[float, float]],
    original_gap_ms: float
) -> Optional[int]:
    """Pure function: detect gap from silence periods.
    
    Returns the END of the first silence period (where vocals start).
    This is the detected gap value.
    
    Args:
        silence_periods: Sequence of (start_ms, end_ms) silence periods
        original_gap_ms: Expected gap position in milliseconds (unused in current logic)
        
    Returns:
        Detected gap in milliseconds (end of first silence period), or 0 if no silence
        
    Example:
        >>> periods = [(0, 2600)]
        >>> detect_gap_from_silence(periods, 0)
        2600  # Vocals start at end of silence
    """
    # If no silence periods found, vocals start immediately
    if not silence_periods:
        return 0
    
    # Return the end of the first silence period
    # This is where vocals actually start
    first_silence = silence_periods[0]
    gap_ms = first_silence[1]  # end_ms
    
    return int(gap_ms)


def should_retry_detection(
    detected_gap_ms: int,
    detection_time_sec: int,
    audio_length_ms: Optional[int]
) -> bool:
    """Pure function: determine if detection should be retried.
    
    Retry if detected gap is beyond detection window, unless we've
    already covered the full audio length.
    
    Args:
        detected_gap_ms: Detected gap in milliseconds
        detection_time_sec: Detection window in seconds
        audio_length_ms: Optional audio length in milliseconds
        
    Returns:
        True if detection should be retried with larger window
    """
    detection_time_ms = detection_time_sec * 1000
    
    # Gap is within detection window - success
    if detected_gap_ms < detection_time_ms:
        return False
    
    # Detection window covers full audio - can't expand further
    if audio_length_ms and detection_time_ms >= audio_length_ms:
        return False
    
    # Gap beyond window and room to expand - retry
    return True


def compute_confidence_score(
    ctx: GapDetectionContext,
    detected_gap_ms: float,
    check_cancellation: Optional[Callable] = None,
    provider = None
) -> Optional[float]:
    """Compute confidence score for detection.
    
    Args:
        ctx: Detection context
        detected_gap_ms: Detected gap in milliseconds
        check_cancellation: Optional cancellation callback
        provider: Optional detection provider (reused if provided)
        
    Returns:
        Confidence score 0.0-1.0, or None if computation fails
    """
    try:
        # Get provider if not provided (for reuse)
        if provider is None:
            provider = get_detection_provider(ctx.config)
        
        confidence = provider.compute_confidence(
            ctx.audio_file,
            detected_gap_ms,
            check_cancellation=check_cancellation
        )
        logger.debug(f"Detection confidence: {confidence:.3f}")
        return confidence
    except Exception as e:
        logger.warning(f"Failed to compute confidence: {e}")
        return None


def perform(
    audio_file: str,
    tmp_root: str,
    original_gap: int,
    audio_length: Optional[int],
    default_detection_time: int,
    config: Config,
    overwrite: bool,
    check_cancellation: Optional[Callable] = None
) -> DetectGapResult:
    """Gap detection pipeline.
    
    Breaks down gap detection into clear, testable steps.
    Each step is a pure function where possible.
    
    Pipeline:
        1. Validate inputs
        2. Normalize context
        3. Get/create vocals file
        4. Detect silence periods
        5. Find gap from silence
        6. Compute confidence
        7. Return result
    
    Args:
        audio_file: Path to audio file
        tmp_root: Temporary directory root
        original_gap: Original gap in milliseconds
        audio_length: Optional audio length in milliseconds
        default_detection_time: Default detection window in seconds
        config: Configuration object
        overwrite: Whether to overwrite existing files
        check_cancellation: Optional cancellation callback
        
    Returns:
        DetectGapResult with detected gap and metadata
        
    Raises:
        ValueError: If inputs are invalid
        FileNotFoundError: If audio file not found
        Exception: If detection fails
    """
    logger.info(f"Detecting gap for {audio_file}")
    
    # Step 1: Normalize inputs into context
    ctx = normalize_context(
        audio_file,
        tmp_root,
        original_gap,
        audio_length,
        default_detection_time,
        config,
        overwrite,
        check_cancellation
    )
    
    # Create provider once for reuse across pipeline (avoid redundant model loads)
    provider = get_detection_provider(ctx.config)
    
    # Step 2: Get or create vocals file
    vocals_file = get_or_create_vocals(ctx, check_cancellation, provider)
    
    # Step 3: Detect silence periods
    silence_periods = detect_silence_periods(ctx, vocals_file, check_cancellation, provider)
    
    # Step 4: Find gap from silence (pure function)
    detected_gap = detect_gap_from_silence(silence_periods, ctx.original_gap_ms)
    
    if detected_gap is None:
        raise Exception(f"Failed to detect gap in {audio_file}")
    
    # Validate: gap must be non-negative
    if detected_gap < 0:
        logger.warning(
            f"Detected negative gap ({detected_gap}ms) in {audio_file}. "
            f"Clamping to 0ms. Silence periods: {silence_periods}"
        )
        detected_gap = 0
    
    # Step 5: Check if we need to retry with larger window
    if should_retry_detection(detected_gap, ctx.detection_time_sec, ctx.audio_length_ms):
        logger.info(
            f"Detected gap {detected_gap}ms beyond detection window. "
            f"Consider increasing detection time."
        )
        # Note: Retry logic not included - failed detection should be handled by caller
        # Can be re-added if needed with recursive call
    
    logger.info(f"Detected GAP: {detected_gap}ms in {audio_file}")
    
    # Step 6: Compute confidence (reuse provider)
    confidence = compute_confidence_score(ctx, float(detected_gap), check_cancellation, provider)
    
    # Step 7: Build result
    result = DetectGapResult(detected_gap, silence_periods, vocals_file)
    result.detection_method = provider.get_method_name()
    result.detected_gap_ms = float(detected_gap)
    result.confidence = confidence
    
    return result
