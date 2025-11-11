"""
Tests for detect_gap_from_silence() function.

Regression tests for the Disney's Duck Tales bug where gap=0
resulted in returning 0ms instead of the actual onset at 2600ms.
"""

# flake8: noqa: E402

import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from utils.gap_detection.pipeline import detect_gap_from_silence


def test_disney_duck_tales_scenario():
    """
    Regression test for Disney's Duck Tales - Theme bug.

    Scenario:
    - Expected gap: 0ms (metadata)
    - Scanner detected onset: 2600ms
    - Silence period: [(0, 2600)]
    - Bug: Function returned 0ms (start of silence)
    - Fix: Function should return 2600ms (end of silence = vocal start)
    """
    silence_periods = [(0.0, 2600.0)]
    original_gap_ms = 0.0

    result = detect_gap_from_silence(silence_periods, original_gap_ms)

    assert result == 2600, (
        f"Should return END of silence (vocal onset at 2600ms), " f"not START of silence (0ms). Got: {result}ms"
    )


def test_no_silence_periods():
    """Vocals start immediately if no silence periods."""
    silence_periods = []
    original_gap_ms = 1000.0

    result = detect_gap_from_silence(silence_periods, original_gap_ms)

    assert result == 0, f"No silence means vocals at start (0ms), got {result}ms"


def test_typical_intro_scenario():
    """Typical song with 5 second intro."""
    silence_periods = [(0.0, 5000.0)]
    original_gap_ms = 5000.0

    result = detect_gap_from_silence(silence_periods, original_gap_ms)

    assert result == 5000, f"Should return 5000ms (end of silence), got {result}ms"


def test_very_short_intro():
    """Very short intro (< 1 second)."""
    silence_periods = [(0.0, 800.0)]
    original_gap_ms = 0.0

    result = detect_gap_from_silence(silence_periods, original_gap_ms)

    assert result == 800, f"Should return 800ms (end of silence), got {result}ms"


def test_long_intro():
    """Long instrumental intro."""
    silence_periods = [(0.0, 45000.0)]  # 45 seconds
    original_gap_ms = 10000.0  # Metadata way off

    result = detect_gap_from_silence(silence_periods, original_gap_ms)

    assert result == 45000, (
        f"Should return 45000ms (actual vocal onset), " f"not 10000ms (expected gap). Got {result}ms"
    )


def test_multiple_silence_periods():
    """
    Multiple silence periods - should return end of FIRST one.

    This can happen if there are pauses in the vocals, but we only
    care about the initial gap (first silence period).
    """
    silence_periods = [(0.0, 3000.0), (8000.0, 9000.0), (15000.0, 16000.0)]
    original_gap_ms = 0.0

    result = detect_gap_from_silence(silence_periods, original_gap_ms)

    assert result == 3000, (
        f"Should return end of FIRST silence period (3000ms), " f"not any other period. Got {result}ms"
    )
