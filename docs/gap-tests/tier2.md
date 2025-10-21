# Tier-2 Gap Detection Tests: Scanner Orchestration

**Scope:** Integration tests for scanner orchestration with real chunk I/O and stubbed separation.  
**Target Code:** [`scan_for_onset()`](../../src/utils/providers/mdx/scanner/pipeline.py)

---

## Overview

Tier-2 tests validate the scanner orchestration layer that coordinates:
1. **ChunkIterator** - Generates chunk boundaries with deduplication
2. **ExpansionStrategy** - Manages search window expansion
3. **OnsetDetectorPipeline** - Processes each chunk for onset detection

Tests use stereo WAV files with:
- **Left channel:** Mixture (vocals + instruments)
- **Right channel:** Isolated vocals (ground truth)

A stub replaces `separate_vocals_chunk()` to return the right channel, simulating perfect separation without running Demucs. This allows deterministic, fast integration tests.

---

## Test Files

### 1. Metadata Alignment Tests
**File:** `tests/gap_scenarios/test_tier2_scanner_metadata_alignment.py`  
**Tests:** 5 scenarios

| Test | Onset (ms) | Expected (ms) | Tolerance (ms) | Focus |
|------|------------|---------------|----------------|-------|
| `test_01_exact_match` | 5000 | 5000 | ±100 | Exact match detection |
| `test_02_close_match` | 5400 | 5000 | ±150 | Near-match within first window |
| `test_03_reasonable_offset` | 7000 | 5000 | ±200 | Moderate offset detection |
| `test_04_large_offset_expansion` | 20000 | 2000 | ±300 | Requires multiple expansions |
| `test_05_early_stop_when_close` | 5100 | 5000 | ±200 | Early-stop optimization |

**Purpose:** Validates scanner finds onsets at various distances from expected gap, handling both close matches and cases requiring window expansion.

---

### 2. Edge Case Tests
**File:** `tests/gap_scenarios/test_tier2_scanner_edge_cases.py`  
**Tests:** 5 scenarios

| Test | Scenario | Expected Behavior |
|------|----------|------------------|
| `test_06_vocals_at_zero_expected_far` | Early vocals (1000ms) with late expected gap (8000ms) | Detects within first expansion window |
| `test_07_multiple_onsets_choose_closest` | Two onsets (2000ms, 21000ms), expected 2050ms | Selects closest onset |
| `test_08_no_vocals` | Silent vocal channel | Returns `None` gracefully |
| `test_09_very_late_vocals` | Onset at 70s with 2s expected | Tests max window limit behavior |
| `test_10_quiet_vocals_with_instruments` | Low-amplitude vocals with loud instruments | Stub ensures clean separation |

**Purpose:** Validates boundary conditions, multiple onset handling, and graceful failure cases.

---

### 3. Performance & Optimization Tests
**File:** `tests/gap_scenarios/test_tier2_scanner_performance.py`  
**Tests:** 3 scenarios

| Test | Focus | Validation Method |
|------|-------|-------------------|
| `test_11_vocals_cache_reuse` | VocalsCache prevents redundant separation | Multiple scans with shared cache |
| `test_12_early_stop_optimization` | Early-stop when onset within tolerance | Cache inspection for processed regions |
| `test_13_resample_to_44100` | Timing accuracy after resampling | 48kHz input, verify onset timestamp |

**Purpose:** Validates caching behavior, early-stop optimization, and robustness to different sample rates.

---

## Test Infrastructure

### Audio Factory
**File:** `tests/test_utils/audio_factory.py`

Generates deterministic stereo test audio:
- **VocalEvent:** Harmonic tones with configurable onset, duration, fade-in, amplitude
- **InstrumentBed:** Noise floor with optional transient spikes
- **Stereo WAV output:** L=mixture, R=vocals

```python
audio_result = build_stereo_test(
    output_path=tmp_path / "test.wav",
    duration_ms=30000,
    vocal_events=[
        VocalEvent(onset_ms=5000, duration_ms=10000, fade_in_ms=100, amp=0.7)
    ],
    instrument_bed=InstrumentBed(noise_floor_db=-60.0)
)
```

### Separation Stub
**File:** `tests/test_utils/separation_stub.py`

Replaces `separate_vocals_chunk()` to return right channel (vocals) without Demucs:

```python
def stub_separate_vocals_chunk(model, waveform, sample_rate, device, use_fp16, check_cancellation):
    # Extract right channel (ground truth vocals)
    vocals_mono = waveform[1:2, :]
    return np.repeat(vocals_mono, 2, axis=0)  # Return as stereo
```

### Fixtures
**File:** `tests/conftest.py`

- **`patch_separator`:** Monkeypatches separator with stub
- **`mdx_config_tight`:** Fast config (20s/10s/60s windows, 7.5s radius)
- **`mdx_config_loose`:** Wide config (30s/15s/90s windows, 10s radius)
- **`model_placeholder`:** Mock Demucs model (samplerate=44100, segment=4.0)

---

## Running Tests

```bash
# Run all Tier-2 tests
.\run.bat test tests\gap_scenarios\test_tier2_scanner*.py -v

# Run specific test file
.\run.bat test tests\gap_scenarios\test_tier2_scanner_metadata_alignment.py -v

# Run single test
.\run.bat test tests\gap_scenarios\test_tier2_scanner_metadata_alignment.py::test_01_exact_match -v
```

---

## Results Summary

**Total Tests:** 13  
**Status:** ✅ All passing  
**Execution Time:** ~2.7 seconds  
**Coverage:** Scanner orchestration, chunk iteration, expansion strategy, vocals caching

### Key Validations

✅ **Metadata Alignment:** Scanner finds onsets at various offsets (0ms to 18000ms from expected)  
✅ **Expansion Strategy:** Multiple expansions work when initial window doesn't contain onset  
✅ **Early-Stop:** Scanner stops searching when onset found within tolerance  
✅ **Edge Cases:** Handles multiple onsets, no vocals, very late vocals gracefully  
✅ **Caching:** VocalsCache reuses separated chunks across scans  
✅ **Resampling:** Timestamps remain accurate with non-44100Hz input  

---

## Next Steps

### Tier-3 (Future)
**Scope:** End-to-end tests with real Demucs separation  
**Purpose:** Validate full pipeline with actual audio separation on real song files

**Prerequisites:**
- GPU/CPU Demucs model loading
- Real UltraStar song samples
- Longer execution time (minutes vs seconds)
- Ground truth annotation for validation

---

## Architecture Notes

### Test Pyramid

```
       Tier-3: E2E (real Demucs)        ← Slow, comprehensive
      /                              \
     Tier-2: Integration (stubbed)    ← Fast, deterministic  ✅ Current
    /                                  \
   Tier-1: Unit (pure logic)            ← Fastest, isolated  ✅ Complete
```

### Stubbing Benefits

1. **Speed:** No Demucs model loading/inference (~100x faster)
2. **Determinism:** Ground truth vocals = right channel (no model variance)
3. **Isolation:** Tests scanner logic without separation quality concerns
4. **CI-Friendly:** No GPU required, runs in seconds

### Real Separation Coverage

Real Demucs integration is tested in:
- `tests/test_separate_audio.py` (separation quality)
- `tests/test_gap_detection.py` (end-to-end with real audio)
- `tests/test_vocal_window.py` (vocals preview with real files)

---

**Related Documentation:**
- [Tier-1 Tests (Energy Detection)](tier1.md)
- [MDX Scanner Architecture](../architecture.md)
- [Detection Complexity Reduction](../refactoring/complexity-reduction-plan.md)
