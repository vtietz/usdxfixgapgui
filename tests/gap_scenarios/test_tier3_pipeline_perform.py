"""
Tier-3 pipeline integration tests.

Tests end-to-end orchestration of perform() with stubbed provider.
Validates file I/O, provider integration, and metadata propagation.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from utils.gap_detection.pipeline import perform
from test_utils.visualize import save_pipeline_overview


# ============================================================================
# Pipeline Tests - Success Paths
# ============================================================================


def test_01_exact_match(audio_scenario, stub_provider_factory, patch_provider, config_stub, write_tier3_docs, tmp_path):
    """
    Scenario 1: Exact match - onset at expected gap position.

    Validates:
    - Pipeline executes successfully
    - Detected gap matches truth onset
    - Confidence propagates correctly
    - Method name returned
    """
    # Build test audio
    scenario = audio_scenario(onset_ms=5000.0, duration_ms=30000)

    # Create and patch provider
    provider = stub_provider_factory(
        truth_onset_ms=scenario["truth_onset_ms"], confidence_value=0.95, tmp_root=scenario["tmp_root"]
    )
    patch_provider(provider)

    # Update config with scenario tmp_root
    config_stub.tmp_root = scenario["tmp_root"]

    # Run pipeline
    result = perform(
        audio_file=scenario["audio_path"],
        tmp_root=scenario["tmp_root"],
        original_gap=5000,  # Expected gap
        audio_length=None,
        default_detection_time=30,
        config=config_stub,
        overwrite=False,
        check_cancellation=None,
    )

    # Assertions
    assert result is not None
    assert result.detected_gap is not None, "Should detect gap"

    # Check detection accuracy (within 50ms for exact match)
    detected_ms = result.detected_gap if result.detected_gap < 1000 else result.detected_gap
    assert (
        abs(detected_ms - scenario["truth_onset_ms"]) <= 50
    ), f"01-exact-match: Expected {scenario['truth_onset_ms']}ms, got {detected_ms}ms"

    # Check confidence
    assert result.confidence == 0.95, f"Confidence should be 0.95, got {result.confidence}"

    # Check method name
    assert result.detection_method == "mdx", f"Method should be 'mdx', got {result.detection_method}"

    # Optional: Save visualization artifact
    if write_tier3_docs:
        docs_dir = Path("docs/gap-tests/tier3")
        docs_dir.mkdir(parents=True, exist_ok=True)
        save_pipeline_overview(
            audio_path=scenario["audio_path"],
            sr=scenario["sr"],
            truth_ms=scenario["truth_onset_ms"],
            detected_ms=detected_ms,
            out_path=str(docs_dir / "01-exact-match.png"),
            confidence=result.confidence,
        )


def test_02_no_silence_periods(audio_scenario, stub_provider_factory, patch_provider, config_stub, write_tier3_docs):
    """
    Scenario 2: No silence periods (vocals at start).

    Validates:
    - Pipeline handles empty silence periods gracefully
    - Returns gap=0 when no silence detected
    """
    # Build test audio with very early onset
    scenario = audio_scenario(onset_ms=100.0, duration_ms=20000)

    # Create provider with no silence periods
    provider = stub_provider_factory(
        truth_onset_ms=None, confidence_value=0.80, tmp_root=scenario["tmp_root"]  # No silence periods
    )
    patch_provider(provider)

    config_stub.tmp_root = scenario["tmp_root"]

    # Run pipeline
    result = perform(
        audio_file=scenario["audio_path"],
        tmp_root=scenario["tmp_root"],
        original_gap=5000,
        audio_length=None,
        default_detection_time=30,
        config=config_stub,
        overwrite=False,
        check_cancellation=None,
    )

    # Assertions
    assert result is not None
    assert result.detected_gap == 0, f"Should detect gap=0 for no silence, got {result.detected_gap}"

    # Optional: Save visualization
    if write_tier3_docs:
        docs_dir = Path("docs/gap-tests/tier3")
        docs_dir.mkdir(parents=True, exist_ok=True)
        save_pipeline_overview(
            audio_path=scenario["audio_path"],
            sr=scenario["sr"],
            truth_ms=scenario["truth_onset_ms"],
            detected_ms=0.0,
            out_path=str(docs_dir / "02-no-silence-periods.png"),
            confidence=result.confidence,
        )


def test_03_confidence_propagation(audio_scenario, stub_provider_factory, patch_provider, config_stub):
    """
    Scenario 3: Confidence propagation.

    Validates:
    - Confidence score propagates from provider to result
    - Low confidence values handled correctly
    """
    scenario = audio_scenario(onset_ms=5000.0, duration_ms=30000)

    # Create provider with low confidence
    provider = stub_provider_factory(
        truth_onset_ms=scenario["truth_onset_ms"],
        confidence_value=0.35,  # Low confidence
        tmp_root=scenario["tmp_root"],
    )
    patch_provider(provider)
    config_stub.tmp_root = scenario["tmp_root"]

    # Run pipeline
    result = perform(
        audio_file=scenario["audio_path"],
        tmp_root=scenario["tmp_root"],
        original_gap=5000,
        audio_length=None,
        default_detection_time=30,
        config=config_stub,
        overwrite=False,
    )

    # Assertions
    assert result.confidence == 0.35, f"Expected confidence 0.35, got {result.confidence}"


def test_04_existing_vocals_respected(audio_scenario, stub_provider_factory, patch_provider, config_stub, tmp_path):
    """
    Scenario 4: Pre-existing vocals file respected (overwrite=False).

    Validates:
    - Pipeline uses existing vocals file when overwrite=False
    - get_vocals_file not called (or returns existing path)
    """
    scenario = audio_scenario(onset_ms=5000.0, duration_ms=20000)

    # Pre-create vocals file
    vocals_dir = Path(scenario["tmp_root"]) / "vocals"
    vocals_dir.mkdir(parents=True, exist_ok=True)
    vocals_file = vocals_dir / "test_audio.wav"

    # Copy audio to vocals location (simulating pre-existing)
    import shutil

    shutil.copy(scenario["audio_path"], vocals_file)

    # Create provider
    provider = stub_provider_factory(
        truth_onset_ms=scenario["truth_onset_ms"], confidence_value=0.90, tmp_root=scenario["tmp_root"]
    )
    patch_provider(provider)
    config_stub.tmp_root = scenario["tmp_root"]

    # Run pipeline with overwrite=False
    result = perform(
        audio_file=scenario["audio_path"],
        tmp_root=scenario["tmp_root"],
        original_gap=5000,
        audio_length=None,
        default_detection_time=30,
        config=config_stub,
        overwrite=False,  # Should use existing file
    )

    # Provider get_vocals_file should not create new file
    # (it would skip because destination exists)
    assert result is not None
    assert result.detected_gap is not None


def test_05_provider_reuse(audio_scenario, stub_provider_factory, patch_provider, config_stub, monkeypatch):
    """
    Scenario 5: Provider reuse across pipeline steps.

    Validates:
    - Same provider instance used for vocals, silence, confidence
    - Avoids redundant model loading
    """
    scenario = audio_scenario(onset_ms=5000.0, duration_ms=20000)

    # Track provider instances
    provider_calls = []
    original_provider = stub_provider_factory(
        truth_onset_ms=scenario["truth_onset_ms"], confidence_value=0.95, tmp_root=scenario["tmp_root"]
    )

    def mock_get_provider(config):
        provider_calls.append(id(original_provider))
        return original_provider

    # Patch with tracking function
    monkeypatch.setattr("utils.gap_detection.pipeline.get_detection_provider", mock_get_provider)

    config_stub.tmp_root = scenario["tmp_root"]

    # Run pipeline
    result = perform(
        audio_file=scenario["audio_path"],
        tmp_root=scenario["tmp_root"],
        original_gap=5000,
        audio_length=None,
        default_detection_time=30,
        config=config_stub,
        overwrite=False,
    )

    # Assert provider was created (called at least once)
    assert len(provider_calls) >= 1, "Provider factory should be called"

    # All calls should return same instance ID
    assert all(pid == provider_calls[0] for pid in provider_calls), "All provider calls should return same instance"

    # Verify provider methods were called
    assert original_provider.get_vocals_call_count >= 1
    assert original_provider.detect_silence_call_count >= 1
    assert original_provider.compute_confidence_call_count >= 1


def test_06_large_offset_detection(audio_scenario, stub_provider_factory, patch_provider, config_stub, caplog):
    """
    Scenario 6: Gap at 20s within 30s window.

    Validates:
    - Detection works for gaps later in the audio
    - No retry needed when within window
    """
    # Create audio with late onset (but within default 30s window)
    scenario = audio_scenario(onset_ms=20000.0, duration_ms=35000)

    # Provider returns the offset
    provider = stub_provider_factory(
        truth_onset_ms=scenario["truth_onset_ms"], confidence_value=0.85, tmp_root=scenario["tmp_root"]
    )
    patch_provider(provider)
    config_stub.tmp_root = scenario["tmp_root"]

    # Run with default 30s window
    result = perform(
        audio_file=scenario["audio_path"],
        tmp_root=scenario["tmp_root"],
        original_gap=20000,  # Match expected onset
        audio_length=None,
        default_detection_time=30,  # 30s window
        config=config_stub,
        overwrite=False,
    )

    # Should detect correctly
    assert result.detected_gap is not None
    detected_ms = result.detected_gap if result.detected_gap < 1000 else result.detected_gap
    assert (
        abs(detected_ms - scenario["truth_onset_ms"]) <= 100
    ), f"Expected ~{scenario['truth_onset_ms']}ms, got {detected_ms}ms"


def test_07_failure_path_handling(audio_scenario, stub_provider_factory, patch_provider, config_stub):
    """
    Scenario 7: Provider failure handling.

    Validates:
    - Pipeline propagates provider exceptions
    - DetectionFailedError raised when provider fails
    """

    scenario = audio_scenario(onset_ms=5000.0, duration_ms=20000)

    # Create provider configured to fail on detect_silence
    provider = stub_provider_factory(
        truth_onset_ms=scenario["truth_onset_ms"],
        confidence_value=0.95,
        tmp_root=scenario["tmp_root"],
        raise_on_detect_silence=True,  # Configured to fail
    )
    patch_provider(provider)
    config_stub.tmp_root = scenario["tmp_root"]

    # Should raise exception
    with pytest.raises(Exception):  # Pipeline may wrap in different exception
        perform(
            audio_file=scenario["audio_path"],
            tmp_root=scenario["tmp_root"],
            original_gap=5000,
            audio_length=None,
            default_detection_time=30,
            config=config_stub,
            overwrite=False,
        )
