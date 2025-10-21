"""
Tier-1 onset detection tests: pure energy-based detection on synthetic vocal stems.

Tests the core onset detection logic without file I/O, Demucs, or scanner dependencies.
Tests detect_onset_in_vocal_chunk() directly with synthetic waveforms.
"""

import os
import sys
from pathlib import Path

import numpy as np
import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from utils.providers.mdx.config import MdxConfig
from utils.providers.mdx.detection import detect_onset_in_vocal_chunk
from test_utils import synth, visualize


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mdx_cfg_default():
    """Default MdxConfig for testing."""
    return MdxConfig()


@pytest.fixture
def artifact_dir(tmp_path):
    """
    Artifact directory for preview images.

    If GAP_TIER1_WRITE_DOCS=1, writes to docs/gap-tests/tier1/
    Otherwise uses tmp_path for CI cleanliness.
    """
    if os.environ.get('GAP_TIER1_WRITE_DOCS') == '1':
        docs_path = Path(__file__).parent.parent.parent / 'docs' / 'gap-tests' / 'tier1'
        docs_path.mkdir(parents=True, exist_ok=True)
        return docs_path
    return tmp_path


# ============================================================================
# Helpers
# ============================================================================

def assert_onset(actual_ms: float | None, truth_ms: float, tol_ms: float, scenario: str):
    """Assert onset detection within tolerance."""
    if actual_ms is None:
        pytest.fail(f"{scenario}: No onset detected (expected {truth_ms:.1f}ms)")

    error_ms = abs(actual_ms - truth_ms)
    assert error_ms <= tol_ms, (
        f"{scenario}: Onset error {error_ms:.1f}ms exceeds tolerance {tol_ms:.1f}ms "
        f"(detected={actual_ms:.1f}ms, truth={truth_ms:.1f}ms)"
    )


def write_preview_if_enabled(
    wave: np.ndarray,
    sr: int,
    truth_ms: float,
    detected_ms: float | None,
    scenario_name: str,
    artifact_dir: Path
):
    """Write waveform preview if GAP_TIER1_WRITE_DOCS is enabled."""
    if os.environ.get('GAP_TIER1_WRITE_DOCS') == '1':
        out_path = artifact_dir / f"{scenario_name}.png"
        error_str = f"Δ{detected_ms - truth_ms:+.1f}ms" if detected_ms else "NONE"
        title = f"{scenario_name.replace('-', ' ').title()} | Truth={truth_ms:.0f}ms, Detected={detected_ms:.0f}ms ({error_str})" if detected_ms else f"{scenario_name.replace('-', ' ').title()} | Truth={truth_ms:.0f}ms, NOT DETECTED"
        visualize.save_waveform_preview(
            wave, sr, title, truth_ms, detected_ms, str(out_path), rms_overlay=True
        )


# ============================================================================
# Test Scenarios
# ============================================================================

def test_01_abrupt_onset(mdx_cfg_default, artifact_dir):
    """
    Scenario 1: Abrupt onset (easy detection).

    Clean tone starting immediately without fade-in.
    Validates threshold crossing and sustained min duration.
    """
    onset_ms = 1500
    wave, meta = synth.build_vocal_onset(
        duration_ms=6000,
        onset_ms=onset_ms,
        fade_in_ms=0,
        breath_ms=0,
        noise_floor_db=-60.0,
        f0_hz=220.0,
        harmonics=4,
        sr=44100
    )

    detected = detect_onset_in_vocal_chunk(
        vocal_audio=wave,
        sample_rate=meta['sr'],
        chunk_start_ms=0.0,
        config=mdx_cfg_default
    )

    write_preview_if_enabled(wave, meta['sr'], onset_ms, detected, "01-abrupt-onset", artifact_dir)
    assert_onset(detected, onset_ms, tol_ms=50, scenario="01-abrupt-onset")


def test_02_gradual_fade_in(mdx_cfg_default, artifact_dir):
    """
    Scenario 2: Gradual fade-in (slow energy rise).

    Tone with 1000ms linear fade-in from onset.
    Validates derivative refinement finds first consistent rise.
    """
    onset_ms = 1500
    wave, meta = synth.build_vocal_onset(
        duration_ms=8000,
        onset_ms=onset_ms,
        fade_in_ms=1000,
        breath_ms=0,
        noise_floor_db=-60.0,
        f0_hz=220.0,
        harmonics=4,
        sr=44100
    )

    detected = detect_onset_in_vocal_chunk(
        vocal_audio=wave,
        sample_rate=meta['sr'],
        chunk_start_ms=0.0,
        config=mdx_cfg_default
    )

    write_preview_if_enabled(wave, meta['sr'], onset_ms, detected, "02-gradual-fade-in", artifact_dir)
    assert_onset(detected, onset_ms, tol_ms=200, scenario="02-gradual-fade-in")


def test_03_breathy_start(mdx_cfg_default, artifact_dir):
    """
    Scenario 3: Breathy start (low-level noise pre-roll).

    300ms breath noise at -40dB before vocal onset with 200ms fade-in.
    Note: Algorithm will detect breath+vocal rising energy, not purely the vocal onset.
    Validates energy detection in presence of pre-vocal breath artifacts.
    """
    onset_ms = 1500
    breath_ms = 300
    vocal_start_ms = onset_ms - breath_ms  # Where breath+vocal energy actually starts
    
    wave, meta = synth.build_vocal_onset(
        duration_ms=8000,
        onset_ms=onset_ms,
        fade_in_ms=200,
        breath_ms=breath_ms,
        breath_db=-40.0,  # Quieter breath 
        noise_floor_db=-60.0,
        f0_hz=220.0,
        harmonics=4,
        sr=44100
    )

    detected = detect_onset_in_vocal_chunk(
        vocal_audio=wave,
        sample_rate=meta['sr'],
        chunk_start_ms=0.0,
        config=mdx_cfg_default
    )

    write_preview_if_enabled(wave, meta['sr'], onset_ms, detected, "03-breathy-start", artifact_dir)
    # Expect detection somewhere between breath start and vocal onset
    # since breath+vocal creates rising energy profile
    assert detected is not None, "03-breathy-start: No onset detected"
    assert vocal_start_ms - 100 <= detected <= onset_ms + 150, (
        f"03-breathy-start: Detected at {detected:.1f}ms, expected between "
        f"{vocal_start_ms - 100:.1f}ms (breath start) and {onset_ms + 150:.1f}ms (vocal onset)"
    )


def test_04_quiet_vocals_near_threshold(mdx_cfg_default, artifact_dir):
    """
    Scenario 4: Quiet vocals near threshold (low SNR).

    Reduced amplitude so early RMS barely exceeds combined threshold.
    Validates combined threshold logic (max of absolute and SNR threshold).
    """
    onset_ms = 1500
    # Build at normal amplitude first
    wave, meta = synth.build_vocal_onset(
        duration_ms=6000,
        onset_ms=onset_ms,
        fade_in_ms=200,
        breath_ms=0,
        noise_floor_db=-50.0,  # Higher noise floor
        f0_hz=220.0,
        harmonics=4,
        sr=44100
    )

    # Reduce overall amplitude to make vocals quieter (just above threshold)
    # Target: RMS slightly above onset_abs_threshold (0.01) and SNR threshold
    wave = wave * 0.15

    detected = detect_onset_in_vocal_chunk(
        vocal_audio=wave,
        sample_rate=meta['sr'],
        chunk_start_ms=0.0,
        config=mdx_cfg_default
    )

    write_preview_if_enabled(wave, meta['sr'], onset_ms, detected, "04-quiet-vocals", artifact_dir)
    assert_onset(detected, onset_ms, tol_ms=250, scenario="04-quiet-vocals")


def test_05_high_noise_floor(mdx_cfg_default, artifact_dir):
    """
    Scenario 5: High noise floor baseline.

    Noise floor at -24dB with adequate tone amplitude to exceed noise + k*sigma.
    Validates SNR threshold scales with sigma.
    """
    onset_ms = 1500
    wave, meta = synth.build_vocal_onset(
        duration_ms=6000,
        onset_ms=onset_ms,
        fade_in_ms=100,
        breath_ms=0,
        noise_floor_db=-24.0,  # Very high noise floor
        f0_hz=220.0,
        harmonics=4,
        sr=44100
    )

    detected = detect_onset_in_vocal_chunk(
        vocal_audio=wave,
        sample_rate=meta['sr'],
        chunk_start_ms=0.0,
        config=mdx_cfg_default
    )

    write_preview_if_enabled(wave, meta['sr'], onset_ms, detected, "05-high-noise-floor", artifact_dir)
    assert_onset(detected, onset_ms, tol_ms=200, scenario="05-high-noise-floor")


def test_06_instrument_spike_before_onset(mdx_cfg_default, artifact_dir):
    """
    Scenario 6: Instrument-like transient spike (false positive guard).

    Short 30ms spike at t=1000ms before vocal onset at 1500ms.
    Validates min_voiced_duration filters out short bursts.
    """
    onset_ms = 1500
    spike_ms = 1000

    # Build main vocal
    wave, meta = synth.build_vocal_onset(
        duration_ms=6000,
        onset_ms=onset_ms,
        fade_in_ms=50,
        breath_ms=0,
        noise_floor_db=-60.0,
        f0_hz=220.0,
        harmonics=4,
        sr=44100
    )

    # Add spike at 1000ms
    spike_start_sample = int(spike_ms / 1000.0 * meta['sr'])
    spike_duration_samples = int(30 / 1000.0 * meta['sr'])  # 30ms spike
    spike_end_sample = spike_start_sample + spike_duration_samples

    if spike_end_sample < len(wave):
        # Create short impulse
        spike_amplitude = 0.4
        wave[spike_start_sample:spike_end_sample] += spike_amplitude * np.sin(
            2 * np.pi * 440.0 * np.arange(spike_duration_samples) / meta['sr']
        )

    detected = detect_onset_in_vocal_chunk(
        vocal_audio=wave,
        sample_rate=meta['sr'],
        chunk_start_ms=0.0,
        config=mdx_cfg_default
    )

    write_preview_if_enabled(wave, meta['sr'], onset_ms, detected, "06-instrument-spike", artifact_dir)
    assert_onset(detected, onset_ms, tol_ms=150, scenario="06-instrument-spike")


def test_07_too_short_energy(mdx_cfg_default, artifact_dir):
    """
    Scenario 7: Too short energy (below min_voiced_duration).

    100ms voiced burst at onset, then silence.
    With min_voiced_duration_ms=300, should not detect.
    """
    onset_ms = 1500
    burst_duration_ms = 100

    # Build short burst
    silence_before = synth.pad_silence(onset_ms, sr=44100)
    burst = synth.harmonic_tone(f0_hz=220.0, duration_ms=burst_duration_ms, sr=44100, harmonics=4, amp=0.8)
    silence_after = synth.pad_silence(2000, sr=44100)  # Pad with silence after
    wave = synth.mix_signals([silence_before, burst, silence_after])
    wave = synth.add_noise_floor(wave, level_db=-60.0, sr=44100)
    wave = synth.normalize_peak(wave, peak=0.9)

    detected = detect_onset_in_vocal_chunk(
        vocal_audio=wave,
        sample_rate=44100,
        chunk_start_ms=0.0,
        config=mdx_cfg_default
    )

    write_preview_if_enabled(wave, 44100, onset_ms, detected, "07-too-short-energy", artifact_dir)

    # Expect no detection
    assert detected is None, (
        f"07-too-short-energy: Expected no detection for {burst_duration_ms}ms burst "
        f"(min_voiced_duration={mdx_cfg_default.min_voiced_duration_ms}ms), "
        f"but got {detected:.1f}ms"
    )


def test_08_extremely_short_audio(mdx_cfg_default, artifact_dir):
    """
    Scenario 8: Extremely short audio (RMS empty guard).

    Audio shorter than frame_samples.
    Validates graceful handling with warning and None return.
    """
    # Create audio shorter than one frame (25ms at 44100 Hz = ~1102 samples)
    wave = np.zeros(500)  # Less than one frame
    sr = 44100

    detected = detect_onset_in_vocal_chunk(
        vocal_audio=wave,
        sample_rate=sr,
        chunk_start_ms=0.0,
        config=mdx_cfg_default
    )

    # No visualization for this edge case (trivial)

    # Expect no detection
    assert detected is None, (
        f"08-extremely-short-audio: Expected no detection for {len(wave)} sample audio "
        f"(< frame_samples), but got {detected}"
    )


# ============================================================================
# Parameterized sensitivity tests (optional)
# ============================================================================

@pytest.mark.parametrize("snr_threshold,abs_threshold,expected_tol_ms", [
    (4.0, 0.01, 50),   # Default
    (6.0, 0.01, 80),   # Higher SNR requirement
    (3.0, 0.01, 50),   # Lower SNR requirement
    (4.0, 0.02, 60),   # Higher absolute threshold
])
def test_09_sensitivity_sweep_abrupt(snr_threshold, abs_threshold, expected_tol_ms, artifact_dir):
    """
    Scenario 9: Sensitivity sweep on abrupt onset.

    Tests different threshold configurations on clean abrupt onset.
    """
    onset_ms = 1500
    wave, meta = synth.build_vocal_onset(
        duration_ms=6000,
        onset_ms=onset_ms,
        fade_in_ms=0,
        breath_ms=0,
        noise_floor_db=-60.0,
        f0_hz=220.0,
        harmonics=4,
        sr=44100
    )

    # Custom config
    cfg = MdxConfig(
        onset_snr_threshold=snr_threshold,
        onset_abs_threshold=abs_threshold
    )

    detected = detect_onset_in_vocal_chunk(
        vocal_audio=wave,
        sample_rate=meta['sr'],
        chunk_start_ms=0.0,
        config=cfg
    )

    scenario_name = f"09-sensitivity-snr{snr_threshold:.1f}-abs{abs_threshold:.3f}"
    write_preview_if_enabled(wave, meta['sr'], onset_ms, detected, scenario_name, artifact_dir)
    assert_onset(detected, onset_ms, tol_ms=expected_tol_ms, scenario=scenario_name)
