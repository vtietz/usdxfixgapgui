"""
Main orchestrator for MDX onset scanning.

Coordinates chunk iteration, window expansion, and onset detection.
High-level coordination - delegates actual work to specialized modules.
"""

import logging
from typing import Optional, Callable, List

from utils.providers.mdx.config import MdxConfig
from utils.providers.mdx.vocals_cache import VocalsCache
from utils.providers.mdx.logging import flush_logs as _flush_logs
from utils.providers.mdx.scanner.chunk_iterator import ChunkIterator
from utils.providers.mdx.scanner.expansion_strategy import ExpansionStrategy
from utils.providers.mdx.scanner.onset_detector import OnsetDetectorPipeline
from utils.providers.exceptions import DetectionFailedError

logger = logging.getLogger(__name__)


def _find_closest_onset(onsets: List[float], expected_gap_ms: float) -> float:
    """
    Find onset closest to expected gap position.

    Special case: When expected_gap is very early (< 1000ms), prefer later onsets
    over very early ones, as songs typically have an intro before vocals start.

    Args:
        onsets: List of detected onset timestamps
        expected_gap_ms: Expected gap position

    Returns:
        Onset closest to expected position (always >= 0)
    """
    # Filter out negative onsets (can happen due to hysteresis lookback at chunk boundaries)
    valid_onsets = [o for o in onsets if o >= 0.0]
    if not valid_onsets:
        # All onsets were negative - return 0 as fallback
        return 0.0

    # If expected gap is very early (< 1s) and we have onsets after 1s,
    # filter out very early onsets (< 800ms) as they're likely instrumental noise
    MIN_PLAUSIBLE_GAP_MS = 800.0

    if expected_gap_ms < 1000.0 and any(o >= MIN_PLAUSIBLE_GAP_MS for o in valid_onsets):
        # Filter out onsets before MIN_PLAUSIBLE_GAP_MS if we have later candidates
        filtered = [o for o in valid_onsets if o >= MIN_PLAUSIBLE_GAP_MS]
        if filtered:
            # Return earliest plausible onset (most likely correct)
            return min(filtered)

    # Normal case: return closest to expected
    return min(valid_onsets, key=lambda x: abs(x - expected_gap_ms))


def _is_duplicate_onset(onset_ms: float, existing_onsets: List[float], threshold_ms: float = 1000) -> bool:
    """
    Check if onset is a duplicate of existing onsets.

    Args:
        onset_ms: Onset timestamp to check
        existing_onsets: List of existing onset timestamps
        threshold_ms: Distance threshold for considering duplicates

    Returns:
        True if onset is within threshold of any existing onset
    """
    return any(abs(onset_ms - existing) < threshold_ms for existing in existing_onsets)


def scan_for_onset(
    audio_file: str,
    expected_gap_ms: float,
    model,
    device: str,
    config: MdxConfig,
    vocals_cache: VocalsCache,
    total_duration_ms: float,
    check_cancellation: Optional[Callable[[], bool]] = None,
) -> Optional[float]:
    """
    Vocal onset detection with expanding window search.

    This is the main entry point for the scanner. It coordinates:
        1. ChunkIterator - generates chunk boundaries with deduplication
        2. ExpansionStrategy - manages search window expansion
        3. OnsetDetectorPipeline - processes each chunk for onset detection

    Strategy:
        - Start with small window around expected gap (±initial_radius)
        - Process chunks in window, detecting onsets
        - If no onset found, expand search window (up to max_expansions)
        - Return closest onset to expected gap

    Complexity Reduction:
        Original _scan_chunks_for_onset: CCN=18, NLOC=102
        Refactored: CCN≤5 per function, total ~150 NLOC across 4 files

    Args:
        audio_file: Path to audio file
        expected_gap_ms: Expected gap position from metadata
        model: Demucs model instance
        device: Device for processing ("cuda" or "cpu")
        config: MDX configuration
        vocals_cache: Cache for separated vocals
        total_duration_ms: Total audio duration in milliseconds
        check_cancellation: Callback returning True if cancelled

    Returns:
        Absolute onset timestamp in milliseconds, or None if not found

    Raises:
        DetectionFailedError: If scanning fails or is cancelled
    """
    try:
        logger.info(f"Starting onset scan (expected gap: {expected_gap_ms:.0f}ms)")
        _flush_logs()

        # Initialize modules
        chunk_iterator = ChunkIterator(
            chunk_duration_ms=config.chunk_duration_ms,
            chunk_overlap_ms=config.chunk_overlap_ms,
            total_duration_ms=total_duration_ms,
        )

        expansion_strategy = ExpansionStrategy(
            initial_radius_ms=config.initial_radius_ms,
            radius_increment_ms=config.radius_increment_ms,
            max_expansions=config.max_expansions,
            total_duration_ms=total_duration_ms,
        )

        onset_detector = OnsetDetectorPipeline(
            audio_file=audio_file, model=model, device=device, config=config, vocals_cache=vocals_cache
        )

        # Collect all detected onsets
        all_onsets: List[float] = []

        # Iterative window expansion: start with start_window_ms, expand if needed
        search_limit_ms = config.start_window_ms
        search_iteration = 0

        while search_limit_ms <= config.start_window_max_ms:
            search_iteration += 1
            logger.info(
                f"Search iteration #{search_iteration}: "
                f"limit={search_limit_ms/1000:.1f}s (max={config.start_window_max_ms/1000:.1f}s)"
            )
            _flush_logs()

            # Generate expansion windows
            windows = expansion_strategy.generate_windows(expected_gap_ms)

            # Process each window (only chunks within search_limit_ms)
            for window in windows:
                logger.info(
                    f"Expansion #{window.expansion_num}: "
                    f"radius=±{window.radius_ms/1000:.1f}s, "
                    f"window {window.start_ms/1000:.1f}s - {window.end_ms/1000:.1f}s"
                )
                _flush_logs()

                # Process chunks in current window (cap at search_limit_ms)
                chunks_processed = 0
                for chunk in chunk_iterator.generate_chunks(window.start_ms, window.end_ms):
                    # Skip chunks beyond search limit
                    if chunk.start_ms >= search_limit_ms:
                        continue

                    # Check cancellation
                    if check_cancellation and check_cancellation():
                        raise DetectionFailedError("Search cancelled by user", provider_name="mdx")

                    chunks_processed += 1
                    logger.info(
                        f"Loading chunk at {chunk.start_s:.1f}s-{chunk.end_s:.1f}s "
                        f"(expansion #{window.expansion_num}, chunk {chunks_processed})"
                    )
                    _flush_logs()

                    # Process chunk for onset
                    onset_ms = onset_detector.process_chunk(chunk, check_cancellation)

                    if onset_ms is not None:
                        # Check for duplicates (within 1 second)
                        if not _is_duplicate_onset(onset_ms, all_onsets):
                            all_onsets.append(onset_ms)
                            logger.info(
                                f"Found vocal onset at {onset_ms:.0f}ms "
                                f"(distance from expected: {abs(onset_ms - expected_gap_ms):.0f}ms)"
                            )

                            # Early-stop if onset is within tolerance
                            diff = abs(onset_ms - expected_gap_ms)
                            early_stop_threshold = max(config.hysteresis_ms, config.early_stop_tolerance_ms)
                            if diff <= early_stop_threshold:
                                logger.info(
                                    f"Early-stop triggered: onset within {early_stop_threshold}ms tolerance "
                                    f"(diff={diff:.0f}ms). Returning {onset_ms:.0f}ms immediately."
                                )
                                _flush_logs()
                                return onset_ms

                logger.info(
                    f"Expansion #{window.expansion_num} complete: "
                    f"processed {chunks_processed} new chunks, "
                    f"found {len(all_onsets)} total onset(s) so far"
                )

                # Check if should continue to next expansion
                if not expansion_strategy.should_continue(window.expansion_num, found_onset=False):
                    break

            # If onsets found, return closest to expected gap
            if all_onsets:
                logger.info("Onset(s) detected! Finding closest to expected position...")
                closest_onset = _find_closest_onset(all_onsets, expected_gap_ms)

                logger.info(
                    f"Returning closest onset: {closest_onset:.0f}ms "
                    f"(expected: {expected_gap_ms:.0f}ms, "
                    f"diff: {abs(closest_onset - expected_gap_ms):.0f}ms)"
                )
                return closest_onset

            # No onset found in current window, expand search
            if search_limit_ms >= config.start_window_max_ms:
                break

            search_limit_ms = min(search_limit_ms + config.start_window_increment_ms, config.start_window_max_ms)
            logger.info(f"No onset in current window, expanding to {search_limit_ms/1000:.1f}s")
            _flush_logs()

        # No onset found after all expansions
        logger.warning(f"No onset detected after {search_iteration} search iteration(s)")
        return None

    except Exception as e:
        if "cancelled" in str(e).lower():
            raise
        logger.error(f"MDX scan failed: {e}")
        raise DetectionFailedError(f"MDX scanning failed: {e}", provider_name="mdx", cause=e)
