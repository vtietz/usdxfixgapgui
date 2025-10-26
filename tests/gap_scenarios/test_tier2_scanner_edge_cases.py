"""
Tier-2 scanner tests: edge cases.

Tests boundary conditions and special scenarios for scan_for_onset().
"""

import os
import sys
from pathlib import Path

import pytest
import numpy as np
from scipy.io import wavfile

sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from test_utils.audio_factory import build_stereo_test, VocalEvent, InstrumentBed
from test_utils import visualize
from utils.providers.mdx.scanner.pipeline import scan_for_onset
from utils.providers.mdx.vocals_cache import VocalsCache


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def artifact_dir(tmp_path):
    """Return docs directory if GAP_TIER2_WRITE_DOCS=1, else tmp_path."""
    if os.environ.get('GAP_TIER2_WRITE_DOCS') == '1':
        docs_path = Path(__file__).parent.parent.parent / 'docs' / 'gap-tests' / 'tier2'
        docs_path.mkdir(parents=True, exist_ok=True)
        return docs_path
    return tmp_path


def write_tier2_preview_if_enabled(
    audio_path,
    truth_ms: float,
    detected_ms,
    early_noise_ms,
    expected_gap_ms: float,
    test_name: str,
    artifact_dir: Path
):
    """Write waveform preview if GAP_TIER2_WRITE_DOCS=1."""
    if os.environ.get('GAP_TIER2_WRITE_DOCS') != '1':
        return

    # Load stereo audio
    sr, audio = wavfile.read(str(audio_path))

    # Extract vocals (right channel for stereo test files)
    if audio.ndim == 2:
        vocals = audio[:, 1].astype(np.float32) / 32768.0
    else:
        vocals = audio.astype(np.float32) / 32768.0

    # Build title with timing info
    title_parts = [f"Expected: {expected_gap_ms:.0f}ms"]
    if early_noise_ms is not None:
        title_parts.append(f"Early Noise: {early_noise_ms:.0f}ms")
    title_parts.append(f"Truth: {truth_ms:.0f}ms")
    if detected_ms is not None:
        title_parts.append(f"Detected: {detected_ms:.0f}ms")
    title = " | ".join(title_parts)

    # Save visualization
    output_path = artifact_dir / f"{test_name}.png"
    visualize.save_waveform_preview(
        wave=vocals,
        sr=sr,
        truth_ms=truth_ms,
        detected_ms=detected_ms,
        title=title,
        out_path=str(output_path),
        rms_overlay=True
    )


# ============================================================================
# Edge Case Tests
# ============================================================================

def test_06_vocals_at_zero_expected_far(
    tmp_path,
    patch_separator,
    mdx_config_tight,
    model_placeholder
):
    """
    Scenario 6: Very early vocals with expected gap much later.

    Tests scanner behavior when vocals appear within first expansion window
    but far from expected gap. Scanner starts at expected±radius, so vocals
    at 500ms are within the initial search window (8000-7500=500ms).
    """
    onset_ms = 1000.0  # Within first expansion window
    expected_gap_ms = 8000.0  # Expected much later

    audio_result = build_stereo_test(
        output_path=tmp_path / "test_vocals_early.wav",
        duration_ms=30000,
        vocal_events=[
            VocalEvent(onset_ms=onset_ms, duration_ms=10000, fade_in_ms=100, amp=0.8)  # Strong onset
        ],
        instrument_bed=InstrumentBed(noise_floor_db=-60.0)
    )

    detected = scan_for_onset(
        audio_file=audio_result.path,
        expected_gap_ms=expected_gap_ms,
        model=model_placeholder,
        device="cpu",
        config=mdx_config_tight,  # initial_radius_ms=7500
        vocals_cache=VocalsCache(),
        total_duration_ms=audio_result.duration_ms
    )

    # Should detect vocals within first expansion (expected±radius = 8000±7500 = 500-15500ms)
    assert detected is not None
    assert abs(detected - onset_ms) <= 500, (
        f"06-vocals-early: Expected detection near {onset_ms}ms, got {detected}ms"
    )


def test_07_multiple_onsets_choose_closest(
    tmp_path,
    patch_separator,
    mdx_config_tight,
    model_placeholder
):
    """
    Scenario 7: Multiple onsets, choose closest to expected.

    Validates that scanner selects the onset nearest to expected gap.
    """
    onset1_ms = 2000.0
    onset2_ms = 21000.0
    expected_gap_ms = 2050.0  # Closer to onset1

    audio_result = build_stereo_test(
        output_path=tmp_path / "test_multiple_onsets.wav",
        duration_ms=60000,
        vocal_events=[
            VocalEvent(onset_ms=onset1_ms, duration_ms=8000, fade_in_ms=100, amp=0.7),
            VocalEvent(onset_ms=onset2_ms, duration_ms=8000, fade_in_ms=100, amp=0.6)
        ],
        instrument_bed=InstrumentBed(noise_floor_db=-60.0)
    )

    # Use config that will scan both regions
    from utils.providers.mdx.config import MdxConfig
    config_wide = MdxConfig(
        start_window_ms=30000,
        start_window_increment_ms=15000,
        start_window_max_ms=60000,
        initial_radius_ms=10000,
        radius_increment_ms=10000,
        max_expansions=3
    )

    detected = scan_for_onset(
        audio_file=audio_result.path,
        expected_gap_ms=expected_gap_ms,
        model=model_placeholder,
        device="cpu",
        config=config_wide,
        vocals_cache=VocalsCache(),
        total_duration_ms=audio_result.duration_ms
    )

    # Should detect onset1 (closest to expected)
    assert detected is not None
    assert abs(detected - onset1_ms) <= 300, (
        f"07-multiple-onsets: Expected detection near {onset1_ms}ms, got {detected}ms"
    )


def test_08_no_vocals(
    tmp_path,
    patch_separator,
    mdx_config_tight,
    model_placeholder
):
    """
    Scenario 8: No vocals present.

    Validates graceful handling when no vocal onsets are found.
    """
    # Build audio with no vocals (right channel silent)
    audio_result = build_stereo_test(
        output_path=tmp_path / "test_no_vocals.wav",
        duration_ms=30000,
        vocal_events=[],  # No vocals!
        instrument_bed=InstrumentBed(noise_floor_db=-40.0)  # Just instruments
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

    # Should return None
    assert detected is None, (
        f"08-no-vocals: Expected None for silent vocals, got {detected}ms"
    )


def test_09_very_late_vocals(
    tmp_path,
    patch_separator,
    mdx_config_loose,
    model_placeholder
):
    """
    Scenario 9: Very late vocals near start_window_max.

    Tests scanner behavior with vocals near the maximum search window.
    """
    onset_ms = 70000.0  # 70 seconds
    expected_gap_ms = 2000.0

    audio_result = build_stereo_test(
        output_path=tmp_path / "test_very_late.wav",
        duration_ms=90000,  # 90 seconds
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
        config=mdx_config_loose,  # Uses 90s max window
        vocals_cache=VocalsCache(),
        total_duration_ms=audio_result.duration_ms
    )

    # Should detect within tolerance or return None if beyond limit
    if detected is not None:
        assert abs(detected - onset_ms) <= 500, (
            f"09-very-late: Onset error too large (detected={detected}ms, truth={onset_ms}ms)"
        )
    # If None, that's also acceptable (beyond reasonable search limit)


def test_10_quiet_vocals_with_instruments(
    tmp_path,
    patch_separator,
    mdx_config_tight,
    model_placeholder
):
    """
    Scenario 10: Quiet vocals with loud instrument bed.

    Tests detection with challenging SNR (but separation is perfect via stub).
    """
    onset_ms = 5000.0

    audio_result = build_stereo_test(
        output_path=tmp_path / "test_quiet_vocals.wav",
        duration_ms=30000,
        vocal_events=[
            VocalEvent(onset_ms=onset_ms, duration_ms=10000, fade_in_ms=200, amp=0.3)  # Quiet
        ],
        instrument_bed=InstrumentBed(
            noise_floor_db=-30.0,  # Loud instruments
            transients=[
                {'t_ms': 3000, 'level_db': -18, 'dur_ms': 100}  # Loud transient before vocals
            ]
        )
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

    # Stub returns clean vocals, so should still detect
    assert detected is not None
    assert abs(detected - onset_ms) <= 300, (
        f"10-quiet-vocals: Detection failed or inaccurate (detected={detected}ms, truth={onset_ms}ms)"
    )


def test_11_zero_gap_with_late_vocals(
    tmp_path,
    artifact_dir,
    patch_separator,
    mdx_config_tight,
    model_placeholder
):
    """
    Scenario 11: Gap=0ms with instrumental intro before vocals.

    This tests the edge case where metadata has gap=0 but vocals don't
    actually start until later (e.g., instrumental intro). The algorithm
    should NOT blindly return 0ms, but search forward for actual vocals.

    Setup:
    - Expected gap: 0ms (or very early, < 1000ms)
    - Instrumental noise/energy at 0-2000ms
    - Actual vocals start at 8000ms

    Expected behavior:
    - Filter out very early "onsets" (< 800ms) if later candidates exist
    - Return first plausible vocal onset (>= 800ms)
    - NEVER return negative values (regression test for hysteresis bug)
    """
    instrumental_noise_ms = 500.0  # Early noise that passes thresholds
    vocal_onset_ms = 8000.0  # Actual vocals much later
    expected_gap_ms = 0.0  # Metadata says gap=0

    audio_result = build_stereo_test(
        output_path=tmp_path / "test_zero_gap_late_vocals.wav",
        duration_ms=30000,
        vocal_events=[
            VocalEvent(onset_ms=vocal_onset_ms, duration_ms=15000, fade_in_ms=150, amp=0.7)
        ],
        instrument_bed=InstrumentBed(
            noise_floor_db=-60.0,
            transients=[
                # Early instrumental transients that might trigger false detection
                {'t_ms': instrumental_noise_ms, 'level_db': -24.0, 'dur_ms': 400}
            ]
        )
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

    # Write visualization
    write_tier2_preview_if_enabled(
        audio_result.path,
        vocal_onset_ms,
        detected,
        instrumental_noise_ms,
        expected_gap_ms,
        "11-zero-gap-with-late-vocals",
        artifact_dir
    )

    # Import validation helper
    from conftest import validate_detected_gap

    # Universal validation (catches negative gaps and other bugs)
    validate_detected_gap(detected, "test_11_zero_gap_with_late_vocals")

    assert detected is not None, "Should detect vocals despite gap=0"

    # Should NOT return early noise position
    assert detected >= 800.0, (
        f"Should not return very early onset (detected={detected:.0f}ms). "
        f"Expected >= 800ms (MIN_PLAUSIBLE_GAP_MS threshold)."
    )

    # Should detect actual vocals
    error_ms = abs(detected - vocal_onset_ms)
    assert error_ms <= 500, (
        f"Detection error {error_ms:.0f}ms (detected={detected:.0f}ms, truth={vocal_onset_ms:.0f}ms). "
        f"Should ignore early instrumental noise and find actual vocals."
    )