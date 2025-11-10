"""
Tier-2 scanner tests: gap-focused search validation.

Tests that validate the gap-focused search strategy correctly prioritizes
detection near expected_gap_ms and ignores false positives far from it.

Key improvement in v2.4: Search window is centered around expected_gap_ms
instead of starting from t=0, eliminating false positive detections from
early noise/artifacts.
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from test_utils.audio_factory import build_stereo_test, VocalEvent, InstrumentBed
from utils.providers.mdx.scanner.pipeline import scan_for_onset
from utils.providers.mdx.vocals_cache import VocalsCache


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def artifact_dir(tmp_path):
    """
    Artifact directory for preview images.

    If GAP_WRITE_DOCS=1, writes to docs/gap-tests/tier2/
    Otherwise uses tmp_path for CI cleanliness.
    """
    if os.environ.get("GAP_WRITE_DOCS") == "1":
        docs_path = Path(__file__).parent.parent.parent / "docs" / "gap-tests" / "tier2"
        docs_path.mkdir(parents=True, exist_ok=True)
        return docs_path
    return tmp_path


# ============================================================================
# Helpers
# ============================================================================


def write_tier2_preview_if_enabled(
    audio_path: str,
    truth_ms: float,
    detected_ms: float | None,
    early_noise_ms: float | None,
    expected_gap_ms: float,
    scenario_name: str,
    artifact_dir: Path,
):
    """Write tier-2 visualization if GAP_WRITE_DOCS is enabled."""
    if os.environ.get("GAP_WRITE_DOCS") == "1":
        from test_utils import visualize
        import torchaudio

        # Load stereo audio and extract right channel (vocals)
        waveform, sr = torchaudio.load(audio_path)
        vocals = waveform[1].numpy()  # Right channel = vocals

        out_path = artifact_dir / f"{scenario_name}.png"
        error_str = f"Δ{detected_ms - truth_ms:+.1f}ms" if detected_ms else "NONE"

        title_parts = [
            scenario_name.replace("-", " ").replace("_", " ").title(),
            f"Expected={expected_gap_ms:.0f}ms",
            f"Truth={truth_ms:.0f}ms",
            f"Detected={detected_ms:.0f}ms ({error_str})" if detected_ms else "NOT DETECTED",
        ]
        if early_noise_ms:
            title_parts.insert(1, f"EarlyNoise={early_noise_ms:.0f}ms")

        title = " | ".join(title_parts)

        visualize.save_waveform_preview(vocals, sr, title, truth_ms, detected_ms, str(out_path), rms_overlay=True)


# ============================================================================
# Gap-Focused Search Tests
# ============================================================================


def test_11_ignore_early_noise_detect_expected_gap(
    tmp_path, artifact_dir, patch_separator, mdx_config_tight, model_placeholder
):
    """
    Scenario 11: Early noise burst + vocals at expected gap.

    This is THE test case for gap-focused search validation.

    Setup:
    - Early transient/noise at 2000ms (should be IGNORED)
    - Actual vocals at 10000ms (should be DETECTED)
    - Expected gap = 10000ms

    Gap-focused search strategy (v2.4):
    - First window: [10000 - 7500, 10000 + 7500] = [2500ms, 17500ms]
    - Early noise at 2000ms is OUTSIDE first window → ignored
    - Vocals at 10000ms are INSIDE first window → detected

    Old behavior (v2.1-v2.3):
    - First window: [0, 10000 + 7500] = [0ms, 17500ms]
    - Early noise at 2000ms was INSIDE → false positive

    This test validates the v2.4 fix works correctly.
    """
    early_noise_ms = 2000.0  # False positive location
    vocal_onset_ms = 10000.0  # True vocal onset
    expected_gap_ms = 10000.0  # Metadata hint

    # Build stereo test audio:
    # Left channel (mixture): early transient + vocals
    # Right channel (vocals): only vocals (no early transient)
    audio_result = build_stereo_test(
        output_path=tmp_path / "test_gap_focused.wav",
        duration_ms=30000,
        vocal_events=[VocalEvent(onset_ms=vocal_onset_ms, duration_ms=10000, fade_in_ms=100, amp=0.7)],
        instrument_bed=InstrumentBed(
            noise_floor_db=-60.0,
            transients=[
                # Early noise burst that should be IGNORED
                {"t_ms": early_noise_ms, "level_db": -25.0, "dur_ms": 500}
            ],
        ),
    )

    # Run scanner with expected_gap_ms hint
    detected = scan_for_onset(
        audio_file=audio_result.path,
        expected_gap_ms=expected_gap_ms,
        model=model_placeholder,
        device="cpu",
        config=mdx_config_tight,  # initial_radius_ms=7500
        vocals_cache=VocalsCache(),
        total_duration_ms=audio_result.duration_ms,
    )

    # Write visualization
    write_tier2_preview_if_enabled(
        audio_result.path,
        vocal_onset_ms,
        detected,
        early_noise_ms,
        expected_gap_ms,
        "11-ignore-early-noise-detect-expected-gap",
        artifact_dir,
    )

    # Validate detection
    assert detected is not None, f"Gap-focused search should detect vocals at {vocal_onset_ms}ms"

    # Key assertion: detected gap should be NEAR expected gap, NOT near early noise
    error_ms = abs(detected - vocal_onset_ms)
    early_noise_distance = abs(detected - early_noise_ms)

    assert error_ms <= 300, (
        f"Detection error {error_ms:.0f}ms exceeds tolerance 300ms "
        f"(detected={detected:.0f}ms, truth={vocal_onset_ms:.0f}ms)"
    )

    assert early_noise_distance > 5000, (
        f"Detected gap {detected:.0f}ms is too close to early noise at {early_noise_ms:.0f}ms "
        f"(distance={early_noise_distance:.0f}ms). Gap-focused search should ignore early noise!"
    )

    print(f"\n[Gap-Focused Search Test]")
    print(f"Early noise at: {early_noise_ms}ms (IGNORED ✓)")
    print(f"Expected gap: {expected_gap_ms}ms")
    print(f"Detected gap: {detected:.0f}ms")
    print(f"Error: {error_ms:.0f}ms")
    print(f"Distance from early noise: {early_noise_distance:.0f}ms")


def test_12_multiple_false_positives_detect_correct_gap(
    tmp_path, artifact_dir, patch_separator, mdx_config_tight, model_placeholder
):
    """
    Scenario 12: Multiple early false positives + correct vocal onset.

    Setup:
    - False positive #1 at 1500ms (percussion)
    - False positive #2 at 3500ms (breath-like artifact)
    - False positive #3 at 5000ms (instrumental bleed)
    - Actual vocals at 12000ms
    - Expected gap = 12000ms

    Gap-focused search should:
    - Start at [12000 - 7500, 12000 + 7500] = [4500ms, 19500ms]
    - Ignore FP #1 and #2 (outside window)
    - Ignore FP #3 (still outside or too far from expected)
    - Detect actual vocals at 12000ms
    """
    fp1_ms = 1500.0
    fp2_ms = 3500.0
    fp3_ms = 5000.0
    vocal_onset_ms = 12000.0
    expected_gap_ms = 12000.0

    audio_result = build_stereo_test(
        output_path=tmp_path / "test_multiple_false_positives.wav",
        duration_ms=30000,
        vocal_events=[VocalEvent(onset_ms=vocal_onset_ms, duration_ms=10000, fade_in_ms=150, amp=0.7)],
        instrument_bed=InstrumentBed(
            noise_floor_db=-60.0,
            transients=[
                {"t_ms": fp1_ms, "level_db": -22.0, "dur_ms": 200},
                {"t_ms": fp2_ms, "level_db": -28.0, "dur_ms": 400},
                {"t_ms": fp3_ms, "level_db": -24.0, "dur_ms": 300},
            ],
        ),
    )

    detected = scan_for_onset(
        audio_file=audio_result.path,
        expected_gap_ms=expected_gap_ms,
        model=model_placeholder,
        device="cpu",
        config=mdx_config_tight,
        vocals_cache=VocalsCache(),
        total_duration_ms=audio_result.duration_ms,
    )

    # Write visualization (fp1_ms as representative early noise)
    write_tier2_preview_if_enabled(
        audio_result.path,
        vocal_onset_ms,
        detected,
        fp1_ms,
        expected_gap_ms,
        "12-multiple-false-positives-detect-correct-gap",
        artifact_dir,
    )

    assert detected is not None, "Should detect correct vocal onset"

    error_ms = abs(detected - vocal_onset_ms)
    assert (
        error_ms <= 300
    ), f"Detection error {error_ms:.0f}ms (detected={detected:.0f}ms, truth={vocal_onset_ms:.0f}ms)"

    # Ensure we didn't detect any of the false positives
    for fp_ms, fp_name in [(fp1_ms, "FP1"), (fp2_ms, "FP2"), (fp3_ms, "FP3")]:
        distance = abs(detected - fp_ms)
        assert distance > 3000, (
            f"Detected gap {detected:.0f}ms too close to {fp_name} at {fp_ms:.0f}ms "
            f"(distance={distance:.0f}ms). Should detect correct vocals at {vocal_onset_ms:.0f}ms!"
        )


def test_13_early_vocals_outside_initial_window_requires_expansion(
    tmp_path, artifact_dir, patch_separator, mdx_config_tight, model_placeholder
):
    """
    Scenario 13: Vocals at 1000ms, expected gap at 10000ms.

    Tests that expansion strategy still works when vocals are early but
    metadata hint is later. Scanner should expand window and eventually
    detect early vocals.

    Gap-focused search:
    - First window: [10000 - 7500, 10000 + 7500] = [2500ms, 17500ms]
    - Vocals at 1000ms are outside first window
    - Expansion #1: [10000 - 15000, 10000 + 15000] = [0ms, 25000ms] → detects!

    This validates that gap-focused search doesn't break fallback expansion.
    """
    vocal_onset_ms = 1000.0  # Very early
    expected_gap_ms = 10000.0  # Expected much later

    audio_result = build_stereo_test(
        output_path=tmp_path / "test_early_vocals_expansion.wav",
        duration_ms=30000,
        vocal_events=[VocalEvent(onset_ms=vocal_onset_ms, duration_ms=15000, fade_in_ms=100, amp=0.8)],
        instrument_bed=InstrumentBed(noise_floor_db=-60.0),
    )

    detected = scan_for_onset(
        audio_file=audio_result.path,
        expected_gap_ms=expected_gap_ms,
        model=model_placeholder,
        device="cpu",
        config=mdx_config_tight,  # Will expand to catch early vocals
        vocals_cache=VocalsCache(),
        total_duration_ms=audio_result.duration_ms,
    )

    # Write visualization (no early noise)
    write_tier2_preview_if_enabled(
        audio_result.path,
        vocal_onset_ms,
        detected,
        None,  # No early noise
        expected_gap_ms,
        "13-early-vocals-outside-initial-window",
        artifact_dir,
    )

    # Should still detect early vocals via expansion
    assert detected is not None, f"Expansion should find early vocals at {vocal_onset_ms}ms even with late expected_gap"

    error_ms = abs(detected - vocal_onset_ms)
    assert (
        error_ms <= 500
    ), f"Detection error {error_ms:.0f}ms (detected={detected:.0f}ms, truth={vocal_onset_ms:.0f}ms)"

    print(f"\n[Early Vocals + Expansion Test]")
    print(f"Vocals at: {vocal_onset_ms}ms (very early)")
    print(f"Expected gap: {expected_gap_ms}ms (metadata hint)")
    print(f"Detected: {detected:.0f}ms via expansion (error: {error_ms:.0f}ms)")


def test_14_gradual_fade_in_at_expected_gap_with_early_noise(
    tmp_path, artifact_dir, patch_separator, mdx_config_tight, model_placeholder
):
    """
    Scenario 14: Gradual fade-in vocals at expected gap + early noise.

    This combines two challenging aspects:
    - Gradual fade-in (2 second ramp) requires sensitive thresholds
    - Early noise requires gap-focused search to avoid false positive

    With v2.4 (gap-focused + aggressive thresholds):
    - Search window centered at expected gap catches gradual onset
    - Early noise outside window is ignored
    - Aggressive thresholds (5.0/0.015) catch slow fade-in
    """
    early_noise_ms = 3000.0
    vocal_onset_ms = 15000.0  # Start of 2-second fade-in
    expected_gap_ms = 15000.0

    audio_result = build_stereo_test(
        output_path=tmp_path / "test_gradual_fade_gap_focused.wav",
        duration_ms=30000,
        vocal_events=[
            # Very gradual fade-in over 2 seconds
            VocalEvent(onset_ms=vocal_onset_ms, duration_ms=10000, fade_in_ms=2000, amp=0.6)
        ],
        instrument_bed=InstrumentBed(
            noise_floor_db=-60.0, transients=[{"t_ms": early_noise_ms, "level_db": -26.0, "dur_ms": 600}]
        ),
    )

    detected = scan_for_onset(
        audio_file=audio_result.path,
        expected_gap_ms=expected_gap_ms,
        model=model_placeholder,
        device="cpu",
        config=mdx_config_tight,
        vocals_cache=VocalsCache(),
        total_duration_ms=audio_result.duration_ms,
    )

    # Write visualization
    write_tier2_preview_if_enabled(
        audio_result.path,
        vocal_onset_ms,
        detected,
        early_noise_ms,
        expected_gap_ms,
        "14-gradual-fade-in-with-early-noise",
        artifact_dir,
    )

    assert detected is not None, "Should detect gradual fade-in vocals"

    error_ms = abs(detected - vocal_onset_ms)
    early_noise_distance = abs(detected - early_noise_ms)

    # Gradual fade-in tolerance
    assert error_ms <= 500, (
        f"Gradual fade-in detection error {error_ms:.0f}ms "
        f"(detected={detected:.0f}ms, truth={vocal_onset_ms:.0f}ms)"
    )

    # Must ignore early noise
    assert early_noise_distance > 8000, f"Detected {detected:.0f}ms too close to early noise at {early_noise_ms:.0f}ms"

    print(f"\n[Gradual Fade-In + Gap-Focused Test]")
    print(f"Early noise: {early_noise_ms}ms (IGNORED ✓)")
    print(f"Gradual fade-in onset: {vocal_onset_ms}ms")
    print(f"Detected: {detected:.0f}ms (error: {error_ms:.0f}ms)")
    print(f"Distance from noise: {early_noise_distance:.0f}ms")


def test_15_expected_region_is_processed_with_distance_gating(
    tmp_path, artifact_dir, patch_separator, mdx_config_tight, model_placeholder
):
    """
    Scenario 15: Distance gating ensures expected region is analyzed.

    This validates the critical fix for tracks like ABBA "Gimme! Gimme! Gimme!"
    where the expected gap is far from the start (e.g., 37.8s).

    Before fix:
    - Absolute-time gating: "if chunk.start_ms >= 20s: skip"
    - Only analyzed 0-20s, missed the actual gap at 37.8s
    - Detected early backing vocals at ~22-25s instead

    After fix (distance-based gating):
    - Analyzes band around expected: [expected - limit, expected + limit]
    - First iteration with 20s limit processes [17.8s - 57.8s] band
    - Correctly finds the true vocal onset near expected gap
    """
    early_backing_vocal_ms = 25000.0  # Early artifact/backing vocal
    true_vocal_onset_ms = 37800.0     # Actual main vocal start (near expected)
    expected_gap_ms = 38000.0          # Metadata hint

    audio_result = build_stereo_test(
        output_path=tmp_path / "test_distance_gating.wav",
        duration_ms=60000,
        vocal_events=[
            # Early backing vocal or artifact
            VocalEvent(onset_ms=early_backing_vocal_ms, duration_ms=2000, fade_in_ms=100, amp=0.4),
            # Main vocals starting near expected gap
            VocalEvent(onset_ms=true_vocal_onset_ms, duration_ms=15000, fade_in_ms=200, amp=0.7),
        ],
        instrument_bed=InstrumentBed(noise_floor_db=-50.0),
    )

    detected = scan_for_onset(
        audio_file=audio_result.path,
        expected_gap_ms=expected_gap_ms,
        model=model_placeholder,
        device="cpu",
        config=mdx_config_tight,
        vocals_cache=VocalsCache(),
        total_duration_ms=audio_result.duration_ms,
    )

    # Write visualization
    write_tier2_preview_if_enabled(
        audio_result.path,
        true_vocal_onset_ms,
        detected,
        early_backing_vocal_ms,
        expected_gap_ms,
        "15-expected-band-distance-gating",
        artifact_dir,
    )

    assert detected is not None, "Should detect vocal onset near expected gap"

    # Should detect near expected, not early backing vocal
    error_from_true = abs(detected - true_vocal_onset_ms)
    distance_from_early = abs(detected - early_backing_vocal_ms)

    assert error_from_true <= 500, (
        f"Should detect true onset at {true_vocal_onset_ms}ms, "
        f"got {detected:.0f}ms (error: {error_from_true:.0f}ms)"
    )

    assert distance_from_early >= 8000, (
        f"Should NOT detect early backing vocal at {early_backing_vocal_ms}ms, "
        f"but detected {detected:.0f}ms (distance: {distance_from_early:.0f}ms)"
    )

    print(f"\n[Distance Gating - Expected Region Processed]")
    print(f"Early backing vocal: {early_backing_vocal_ms}ms (IGNORED ✓)")
    print(f"True vocal onset: {true_vocal_onset_ms}ms (near expected)")
    print(f"Expected gap: {expected_gap_ms}ms")
    print(f"Detected: {detected:.0f}ms (error: {error_from_true:.0f}ms)")
    print(f"Distance from early artifact: {distance_from_early:.0f}ms")
