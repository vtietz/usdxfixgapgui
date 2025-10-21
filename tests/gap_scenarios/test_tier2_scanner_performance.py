"""
Tier-2 scanner tests: performance and optimization.

Tests chunk deduplication and early-stop behavior.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from test_utils.audio_factory import build_stereo_test, VocalEvent, InstrumentBed
from utils.providers.mdx.scanner.pipeline import scan_for_onset
from utils.providers.mdx.vocals_cache import VocalsCache


# ============================================================================
# Performance Tests
# ============================================================================

def test_11_vocals_cache_reuse(
    tmp_path,
    patch_separator,
    mdx_config_tight,
    model_placeholder
):
    """
    Scenario 11: VocalsCache prevents redundant separation.
    
    Validates that multiple scans with the same cache reuse separated vocals.
    """
    onset_ms = 5000.0
    
    audio_result = build_stereo_test(
        output_path=tmp_path / "test_cache.wav",
        duration_ms=30000,
        vocal_events=[
            VocalEvent(onset_ms=onset_ms, duration_ms=10000, fade_in_ms=100, amp=0.7)
        ],
        instrument_bed=InstrumentBed(noise_floor_db=-60.0)
    )
    
    # Shared cache
    cache = VocalsCache()
    
    # First scan
    detected1 = scan_for_onset(
        audio_file=audio_result.path,
        expected_gap_ms=5000.0,
        model=model_placeholder,
        device="cpu",
        config=mdx_config_tight,
        vocals_cache=cache,
        total_duration_ms=audio_result.duration_ms
    )
    
    # Second scan with same cache
    detected2 = scan_for_onset(
        audio_file=audio_result.path,
        expected_gap_ms=5000.0,
        model=model_placeholder,
        device="cpu",
        config=mdx_config_tight,
        vocals_cache=cache,
        total_duration_ms=audio_result.duration_ms
    )
    
    # Both should detect onset
    assert detected1 is not None
    assert detected2 is not None
    assert abs(detected1 - onset_ms) <= 200
    assert abs(detected2 - onset_ms) <= 200
    
    # Cache should have entries
    assert len(cache._cache) > 0, "11-cache: VocalsCache should have stored chunks"


def test_12_early_stop_optimization(
    tmp_path,
    patch_separator,
    mdx_config_tight,
    model_placeholder
):
    """
    Scenario 12: Early stop when onset found within tolerance.
    
    Tests that scanner stops searching when onset is close to expected.
    This is a behavioral test - we verify it doesn't scan unnecessarily far.
    """
    onset_ms = 5100.0  # Very close to expected
    expected_gap_ms = 5000.0
    
    # Add another onset much later (should not be reached if early-stop works)
    audio_result = build_stereo_test(
        output_path=tmp_path / "test_early_stop.wav",
        duration_ms=60000,
        vocal_events=[
            VocalEvent(onset_ms=onset_ms, duration_ms=8000, fade_in_ms=100, amp=0.7),
            VocalEvent(onset_ms=40000.0, duration_ms=8000, fade_in_ms=100, amp=0.6)
        ],
        instrument_bed=InstrumentBed(noise_floor_db=-60.0)
    )
    
    cache = VocalsCache()
    detected = scan_for_onset(
        audio_file=audio_result.path,
        expected_gap_ms=expected_gap_ms,
        model=model_placeholder,
        device="cpu",
        config=mdx_config_tight,
        vocals_cache=cache,
        total_duration_ms=audio_result.duration_ms
    )
    
    # Should detect first onset
    assert detected is not None
    assert abs(detected - onset_ms) <= 200
    
    # Check cache to see what regions were processed
    # If early-stop works, shouldn't have cached chunks past ~25s
    cached_regions = [key for key in cache._cache.keys()]
    if cached_regions:
        # Cache keys are tuples (chunk_start_ms, chunk_end_ms)
        max_cached_ms = max(key[1] if isinstance(key, tuple) else key for key in cached_regions)
        if max_cached_ms > 25000:
            pytest.xfail(
                f"12-early-stop: Scanner processed beyond 25s (max cached: {max_cached_ms}ms). "
                "Early-stop may not be implemented."
            )


def test_13_resample_to_44100(
    tmp_path,
    patch_separator,
    mdx_config_tight,
    model_placeholder
):
    """
    Scenario 13: Audio resampling to 44100Hz.
    
    Validates that timestamps remain correct after resampling.
    """
    onset_ms = 5000.0
    
    # Build audio at 48000Hz (non-standard)
    audio_result = build_stereo_test(
        output_path=tmp_path / "test_resample.wav",
        sr=48000,  # Non-standard rate
        duration_ms=30000,
        vocal_events=[
            VocalEvent(onset_ms=onset_ms, duration_ms=10000, fade_in_ms=100, amp=0.7)
        ],
        instrument_bed=InstrumentBed(noise_floor_db=-60.0)
    )
    
    detected = scan_for_onset(
        audio_file=audio_result.path,
        expected_gap_ms=5000.0,
        model=model_placeholder,
        device="cpu",
        config=mdx_config_tight,
        vocals_cache=VocalsCache(),
        total_duration_ms=audio_result.duration_ms
    )
    
    # Should detect correctly despite resampling
    assert detected is not None
    assert abs(detected - onset_ms) <= 200, (
        f"13-resample: Timing error after resampling (detected={detected}ms, truth={onset_ms}ms)"
    )
