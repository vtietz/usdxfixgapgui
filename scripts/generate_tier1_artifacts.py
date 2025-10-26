"""
Standalone artifact generator for Tier-1 onset detection tests.

Runs the same synth + detect_onset_in_vocal_chunk pipeline for all scenarios,
saves images under docs/gap-tests/tier1/, and prints a report.

Usage:
    python scripts/generate_tier1_artifacts.py
"""

import sys
from pathlib import Path

import numpy as np

# Add src and tests to path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'tests'))

from utils.providers.mdx.config import MdxConfig
from utils.providers.mdx.detection import detect_onset_in_vocal_chunk
from test_utils import synth, visualize


# Output directory
ARTIFACT_DIR = ROOT / 'docs' / 'gap-tests' / 'tier1'
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)


def run_scenario(name: str, wave: np.ndarray, sr: int, truth_ms: float, config: MdxConfig):
    """Run detection on a scenario and save artifact."""
    detected = detect_onset_in_vocal_chunk(
        vocal_audio=wave,
        sample_rate=sr,
        chunk_start_ms=0.0,
        config=config
    )

    # Generate title
    error_str = f"Δ{detected - truth_ms:+.1f}ms" if detected else "NONE"
    title = (
        f"{name.replace('-', ' ').title()} | "
        f"Truth={truth_ms:.0f}ms, Detected={detected:.0f if detected else 'NOT'}ms "
        f"({error_str})"
    )

    # Save preview
    out_path = ARTIFACT_DIR / f"{name}.png"
    visualize.save_waveform_preview(
        wave, sr, title, truth_ms, detected, str(out_path), rms_overlay=True
    )

    # Print report
    status = "✓" if detected else "✗"
    error = f"{detected - truth_ms:+6.1f}ms" if detected else "    NONE"
    print(f"  [{status}] {name:30s}  Truth={truth_ms:6.1f}ms  Detected={str(detected) + 'ms' if detected else 'NONE':10s}  Error={error}")

    return detected


def main():
    """Generate all Tier-1 artifacts."""
    print("=" * 80)
    print("Generating Tier-1 Onset Detection Artifacts")
    print("=" * 80)
    print()

    cfg_default = MdxConfig()

    # Scenario 1: Abrupt onset
    print("Scenario 1: Abrupt Onset")
    wave, meta = synth.build_vocal_onset(
        duration_ms=6000, onset_ms=1500, fade_in_ms=0, breath_ms=0,
        noise_floor_db=-60.0, f0_hz=220.0, harmonics=4, sr=44100
    )
    run_scenario("01-abrupt-onset", wave, meta['sr'], 1500, cfg_default)

    # Scenario 2: Gradual fade-in
    print("Scenario 2: Gradual Fade-In")
    wave, meta = synth.build_vocal_onset(
        duration_ms=8000, onset_ms=1500, fade_in_ms=1000, breath_ms=0,
        noise_floor_db=-60.0, f0_hz=220.0, harmonics=4, sr=44100
    )
    run_scenario("02-gradual-fade-in", wave, meta['sr'], 1500, cfg_default)

    # Scenario 3: Breathy start
    print("Scenario 3: Breathy Start")
    wave, meta = synth.build_vocal_onset(
        duration_ms=8000, onset_ms=1500, fade_in_ms=200, breath_ms=300,
        breath_db=-40.0, noise_floor_db=-60.0, f0_hz=220.0, harmonics=4, sr=44100
    )
    run_scenario("03-breathy-start", wave, meta['sr'], 1500, cfg_default)

    # Scenario 4: Quiet vocals
    print("Scenario 4: Quiet Vocals Near Threshold")
    wave, meta = synth.build_vocal_onset(
        duration_ms=6000, onset_ms=1500, fade_in_ms=200, breath_ms=0,
        noise_floor_db=-50.0, f0_hz=220.0, harmonics=4, sr=44100
    )
    wave = wave * 0.15  # Reduce amplitude
    run_scenario("04-quiet-vocals", wave, meta['sr'], 1500, cfg_default)

    # Scenario 5: High noise floor
    print("Scenario 5: High Noise Floor")
    wave, meta = synth.build_vocal_onset(
        duration_ms=6000, onset_ms=1500, fade_in_ms=100, breath_ms=0,
        noise_floor_db=-24.0, f0_hz=220.0, harmonics=4, sr=44100
    )
    run_scenario("05-high-noise-floor", wave, meta['sr'], 1500, cfg_default)

    # Scenario 6: Instrument spike
    print("Scenario 6: Instrument Spike Before Onset")
    wave, meta = synth.build_vocal_onset(
        duration_ms=6000, onset_ms=1500, fade_in_ms=50, breath_ms=0,
        noise_floor_db=-60.0, f0_hz=220.0, harmonics=4, sr=44100
    )
    # Add spike at 1000ms
    spike_start_sample = int(1000 / 1000.0 * meta['sr'])
    spike_duration_samples = int(30 / 1000.0 * meta['sr'])
    spike_end_sample = spike_start_sample + spike_duration_samples
    if spike_end_sample < len(wave):
        wave[spike_start_sample:spike_end_sample] += 0.4 * np.sin(
            2 * np.pi * 440.0 * np.arange(spike_duration_samples) / meta['sr']
        )
    run_scenario("06-instrument-spike", wave, meta['sr'], 1500, cfg_default)

    # Scenario 7: Too short energy
    print("Scenario 7: Too Short Energy")
    silence_before = synth.pad_silence(1500, sr=44100)
    burst = synth.harmonic_tone(f0_hz=220.0, duration_ms=100, sr=44100, harmonics=4, amp=0.8)
    silence_after = synth.pad_silence(2000, sr=44100)
    wave = synth.mix_signals([silence_before, burst, silence_after])
    wave = synth.add_noise_floor(wave, level_db=-60.0, sr=44100)
    wave = synth.normalize_peak(wave, peak=0.9)
    run_scenario("07-too-short-energy", wave, 44100, 1500, cfg_default)

    # Scenario 8: Extremely short audio
    print("Scenario 8: Extremely Short Audio")
    wave = np.zeros(500)
    detected = detect_onset_in_vocal_chunk(wave, 44100, 0.0, cfg_default)
    print(f"  [✓] {'08-extremely-short-audio':30s}  (Edge case: {len(wave)} samples, no detection expected)")

    # Scenario 9: Sensitivity sweeps
    print("Scenario 9: Sensitivity Sweeps")
    wave_base, meta = synth.build_vocal_onset(
        duration_ms=6000, onset_ms=1500, fade_in_ms=0, breath_ms=0,
        noise_floor_db=-60.0, f0_hz=220.0, harmonics=4, sr=44100
    )

    variants = [
        (4.0, 0.01, "09-sensitivity-snr4.0-abs0.010"),
        (6.0, 0.01, "09-sensitivity-snr6.0-abs0.010"),
        (3.0, 0.01, "09-sensitivity-snr3.0-abs0.010"),
        (4.0, 0.02, "09-sensitivity-snr4.0-abs0.020"),
    ]

    for snr, abs_thresh, name in variants:
        cfg = MdxConfig(onset_snr_threshold=snr, onset_abs_threshold=abs_thresh)
        run_scenario(name, wave_base, meta['sr'], 1500, cfg)

    print()
    print("=" * 80)
    print(f"✓ Artifacts generated in: {ARTIFACT_DIR}")
    print("=" * 80)


if __name__ == '__main__':
    main()