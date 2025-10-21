"""
Tier-2 scanner tests: metadata alignment scenarios.

Tests scan_for_onset() with real audio chunk I/O and stubbed separation.
Validates that scanner correctly finds onsets at various distances from expected gap.
"""

import os
import sys
from pathlib import Path

import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from test_utils.audio_factory import build_stereo_test, VocalEvent, InstrumentBed
from utils.providers.mdx.scanner.pipeline import scan_for_onset
from utils.providers.mdx.vocals_cache import VocalsCache


# ============================================================================
# Helper Functions
# ============================================================================

def assert_onset_within_tolerance(
    detected_ms: float | None,
    truth_ms: float,
    tolerance_ms: float,
    scenario: str
):
    """Assert onset detection within tolerance."""
    assert detected_ms is not None, f"{scenario}: No onset detected (expected {truth_ms:.0f}ms)"
    
    error_ms = abs(detected_ms - truth_ms)
    assert error_ms <= tolerance_ms, (
        f"{scenario}: Onset error {error_ms:.0f}ms exceeds tolerance {tolerance_ms:.0f}ms "
        f"(detected={detected_ms:.0f}ms, truth={truth_ms:.0f}ms)"
    )


# ============================================================================
# Test Scenarios
# ============================================================================

def test_01_exact_match(
    tmp_path,
    patch_separator,
    mdx_config_tight,
    model_placeholder
):
    """
    Scenario 1: Exact match (±50ms).
    
    Vocal onset at expected gap position with minimal offset.
    """
    # Build test audio
    onset_ms = 5000.0
    expected_gap_ms = 5000.0
    
    audio_result = build_stereo_test(
        output_path=tmp_path / "test_exact_match.wav",
        duration_ms=30000,
        vocal_events=[
            VocalEvent(onset_ms=onset_ms, duration_ms=10000, fade_in_ms=50, amp=0.7)
        ],
        instrument_bed=InstrumentBed(noise_floor_db=-60.0)
    )
    
    # Run scanner
    detected = scan_for_onset(
        audio_file=audio_result.path,
        expected_gap_ms=expected_gap_ms,
        model=model_placeholder,
        device="cpu",
        config=mdx_config_tight,
        vocals_cache=VocalsCache(),
        total_duration_ms=audio_result.duration_ms,
        check_cancellation=None
    )
    
    # Assert
    assert_onset_within_tolerance(detected, onset_ms, tolerance_ms=100, scenario="01-exact-match")


def test_02_close_match(
    tmp_path,
    patch_separator,
    mdx_config_tight,
    model_placeholder
):
    """
    Scenario 2: Close match (≤500ms offset).
    
    Onset slightly offset from expected gap.
    """
    onset_ms = 5400.0
    expected_gap_ms = 5000.0
    
    audio_result = build_stereo_test(
        output_path=tmp_path / "test_close_match.wav",
        duration_ms=30000,
        vocal_events=[
            VocalEvent(onset_ms=onset_ms, duration_ms=10000, fade_in_ms=100, amp=0.7)
        ],
        instrument_bed=InstrumentBed(noise_floor_db=-60.0)
    )
    
    detected = scan_for_onset(
        audio_file=audio_result.path,
        expected_gap_ms=expected_gap_ms,
        model=model_placeholder,
        device="cpu",
        config=mdx_config_tight,
        vocals_cache=VocalsCache(),
        total_duration_ms=audio_result.duration_ms
    )
    
    assert_onset_within_tolerance(detected, onset_ms, tolerance_ms=150, scenario="02-close-match")


def test_03_reasonable_offset(
    tmp_path,
    patch_separator,
    mdx_config_tight,
    model_placeholder
):
    """
    Scenario 3: Reasonable offset (500-2000ms).
    
    Moderate offset still within first expansion window.
    """
    onset_ms = 7000.0
    expected_gap_ms = 5000.0
    
    audio_result = build_stereo_test(
        output_path=tmp_path / "test_reasonable_offset.wav",
        duration_ms=30000,
        vocal_events=[
            VocalEvent(onset_ms=onset_ms, duration_ms=10000, fade_in_ms=100, amp=0.7)
        ],
        instrument_bed=InstrumentBed(noise_floor_db=-60.0)
    )
    
    detected = scan_for_onset(
        audio_file=audio_result.path,
        expected_gap_ms=expected_gap_ms,
        model=model_placeholder,
        device="cpu",
        config=mdx_config_tight,
        vocals_cache=VocalsCache(),
        total_duration_ms=audio_result.duration_ms
    )
    
    assert_onset_within_tolerance(detected, onset_ms, tolerance_ms=200, scenario="03-reasonable-offset")


def test_04_large_offset_expansion(
    tmp_path,
    patch_separator,
    mdx_config_tight,
    model_placeholder
):
    """
    Scenario 4: Large offset requiring window expansion.
    
    Onset far from expected gap, requires expansion to find.
    Validates expansion strategy works correctly.
    """
    onset_ms = 20000.0
    expected_gap_ms = 2000.0
    
    # Use longer duration and loose config to allow expansions
    audio_result = build_stereo_test(
        output_path=tmp_path / "test_large_offset.wav",
        duration_ms=60000,
        vocal_events=[
            VocalEvent(onset_ms=onset_ms, duration_ms=15000, fade_in_ms=100, amp=0.7)
        ],
        instrument_bed=InstrumentBed(noise_floor_db=-60.0)
    )
    
    # Use tighter config but with enough expansions
    from utils.providers.mdx.config import MdxConfig
    config_expanded = MdxConfig(
        chunk_duration_ms=12000,
        chunk_overlap_ms=6000,
        start_window_ms=30000,
        start_window_increment_ms=15000,
        start_window_max_ms=60000,
        initial_radius_ms=7500,
        radius_increment_ms=7500,
        max_expansions=3  # Allow more expansions
    )
    
    detected = scan_for_onset(
        audio_file=audio_result.path,
        expected_gap_ms=expected_gap_ms,
        model=model_placeholder,
        device="cpu",
        config=config_expanded,
        vocals_cache=VocalsCache(),
        total_duration_ms=audio_result.duration_ms
    )
    
    assert_onset_within_tolerance(detected, onset_ms, tolerance_ms=300, scenario="04-large-offset-expansion")


def test_05_early_stop_when_close(
    tmp_path,
    patch_separator,
    mdx_config_tight,
    model_placeholder
):
    """
    Scenario 5: Early-stop when onset very close to expected.
    
    Validates early-stop optimization triggers when onset is within tolerance.
    """
    onset_ms = 5100.0  # Within early_stop_tolerance_ms (500ms)
    expected_gap_ms = 5000.0
    
    audio_result = build_stereo_test(
        output_path=tmp_path / "test_early_stop.wav",
        duration_ms=30000,
        vocal_events=[
            VocalEvent(onset_ms=onset_ms, duration_ms=10000, fade_in_ms=50, amp=0.7),
            # Add a second onset much later (should not be reached)
            VocalEvent(onset_ms=20000, duration_ms=5000, fade_in_ms=50, amp=0.6)
        ],
        instrument_bed=InstrumentBed(noise_floor_db=-60.0)
    )
    
    detected = scan_for_onset(
        audio_file=audio_result.path,
        expected_gap_ms=expected_gap_ms,
        model=model_placeholder,
        device="cpu",
        config=mdx_config_tight,
        vocals_cache=VocalsCache(),
        total_duration_ms=audio_result.duration_ms
    )
    
    # Should detect first onset and early-stop
    assert_onset_within_tolerance(detected, onset_ms, tolerance_ms=150, scenario="05-early-stop")
