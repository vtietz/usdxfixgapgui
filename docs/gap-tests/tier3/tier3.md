# Tier-3 Integration Tests: Pipeline + Provider

**Status**: ✅ Complete (7 tests, all passing)  
**Location**: `tests/gap_scenarios/test_tier3_pipeline_perform.py`  
**Purpose**: End-to-end integration testing of `perform()` pipeline with stubbed detection provider

---

## Overview

Tier-3 validates the complete gap detection pipeline orchestration:
- **perform()** function execution
- IDetectionProvider integration via monkeypatch
- File I/O operations (vocals extraction, caching)
- Silence period evaluation logic
- Confidence propagation
- Error handling paths

Uses **StubProvider** (extracts right channel as "vocals") to avoid Demucs dependency.

---

## Test Infrastructure

### StubProvider (`tests/test_utils/provider_stub.py`)
- Implements `IDetectionProvider` interface
- **get_vocals_file**: Extracts right channel from stereo test audio
- **detect_silence_periods**: Returns `[(0, truth_onset_ms)]` 
- **compute_confidence**: Returns fixed confidence value
- Call tracking: `get_vocals_call_count`, `detect_silence_call_count`, `compute_confidence_call_count`

### ConfigStub (`tests/test_utils/config_stub.py`)
- Minimal Config duck-type for testing
- Fields: `tmp_root`, `method`, `default_detection_time`, `gap_tolerance`, MDX settings

### Fixtures (`tests/conftest.py`)
- **audio_scenario**: Factory for building test audio with controllable onset
- **stub_provider_factory**: Creates configured StubProvider instances
- **patch_provider**: Monkeypatches `get_detection_provider` at usage site
- **config_stub**: Returns ConfigStub instance
- **write_tier3_docs**: Checks `GAP_TIER3_WRITE_DOCS` env var

### Visualizer (`tests/test_utils/visualize.py`)
- **save_pipeline_overview**: Generates waveform plots with truth/detected markers
- Usage: Set `GAP_TIER3_WRITE_DOCS=1` to generate PNG artifacts

---

## Test Scenarios

### 1. Exact Match (`test_01_exact_match`)
- **Setup**: Onset at 5000ms, original_gap=5000ms
- **Validates**: Detection accuracy within ±50ms, confidence propagation, method name

### 2. No Silence Periods (`test_02_no_silence_periods`)
- **Setup**: Vocals at start (no silence)
- **Validates**: Returns gap=0 when no silence detected

### 3. Confidence Propagation (`test_03_confidence_propagation`)
- **Setup**: Low confidence (0.35)
- **Validates**: Confidence value flows through pipeline correctly

### 4. Existing Vocals Respected (`test_04_existing_vocals_respected`)
- **Setup**: Pre-existing vocals file, overwrite=False
- **Validates**: Skips re-extraction, uses cached vocals

### 5. Provider Reuse (`test_05_provider_reuse`)
- **Setup**: Multiple pipeline steps
- **Validates**: Same provider instance used across get_vocals/detect_silence/compute_confidence

### 6. Large Offset Detection (`test_06_large_offset_detection`)
- **Setup**: Onset at 20000ms (within 30s window)
- **Validates**: Detection works for gaps later in audio

### 7. Failure Path Handling (`test_07_failure_path_handling`)
- **Setup**: Provider raises DetectionFailedError
- **Validates**: Exception propagates correctly, no silent failures

---

## Running Tests

```bash
# Run all Tier-3 tests
.\run.bat test tests\gap_scenarios\test_tier3_pipeline_perform.py -v

# Run specific test
.\run.bat test tests\gap_scenarios\test_tier3_pipeline_perform.py::test_01_exact_match -v

# Generate visualization artifacts
set GAP_TIER3_WRITE_DOCS=1
.\run.bat test tests\gap_scenarios\test_tier3_pipeline_perform.py -v
```

Artifacts saved to `docs/gap-tests/tier3/*.png`

---

## Key Learnings

### Monkeypatch Strategy
- Patch at **usage site**: `utils.gap_detection.pipeline.get_detection_provider`
- Not at factory site: `~~utils.providers.factory.get_detection_provider~~`

### Silence Period Evaluation
- `perform()` evaluates BOTH start and end of each silence period
- Picks whichever is closest to `original_gap_ms`
- Example: `[(0, 5000)]` with original_gap=5000 → picks end=5000 (diff=0)
- Example: `[(0, 20000)]` with original_gap=5000 → picks start=0 (diff=5000)

### Test Audio Structure
- **Left channel**: Music/instrumental (continuous)
- **Right channel**: Vocals (starts at onset_ms)
- StubProvider extracts right channel to simulate vocal separation

---

## Test Execution

**Performance**: ~3.3 seconds for all 7 tests  
**Result**: 371/371 tests passing (full suite)  
**Coverage**: Pipeline integration, provider interface, file I/O, error handling
