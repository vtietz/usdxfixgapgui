# MDX Provider Refactoring Plan

**Status**: 🔴 Not Started  
**Target**: Reduce `mdx_provider.py` from 1012 LOC to <500 LOC  
**Start Date**: 2025-10-18  
**Estimated Duration**: 4-7 days

## Goals

1. ✅ Reduce file to maintainable size (<350-500 LOC)
2. ✅ Eliminate global mutable state
3. ✅ Preserve lazy-import semantics for GPU bootstrap
4. ✅ Improve testability and separation of concerns
5. ✅ Maintain public API compatibility (`IDetectionProvider`)

## Current State

**File**: `src/utils/providers/mdx_provider.py`  
**Size**: 1012 lines (CRITICAL - requires immediate refactoring)  
**Issues**:
- Global mutable cache (`_GLOBAL_MODEL_CACHE`, `_MODEL_LOCK`)
- Mixed concerns (config, model loading, separation, detection, confidence, caching)
- Difficult to unit test individual components
- Hard for AI agents to understand and modify

## Target Architecture

```
src/utils/providers/mdx/
├── __init__.py           # Package exports
├── config.py             # MdxConfig dataclass
├── model_loader.py       # ModelLoader (replaces global cache)
├── separator.py          # Full-track & chunk separation
├── detection.py          # Onset detection pipeline
├── confidence.py         # SNR-based confidence scoring
├── cache.py              # VocalsCache (LRU cache)
└── logging.py            # Logging utilities
```

**mdx_provider.py** becomes thin orchestrator (~300-400 LOC)

## Module Responsibilities

### config.py (~80 LOC)
- `MdxConfig` dataclass with validation
- `MdxConfig.from_config()` factory method
- **Moves**: Lines 63-178 from mdx_provider.py

### model_loader.py (~150 LOC)
- `ModelLoader` class with thread-safe caching
- `get_device()` - CUDA/CPU detection
- `get_model(device, use_fp16)` - Model loading with optimizations
- **Moves**: Lines 204-272, removes global cache
- **Replaces**: `_GLOBAL_MODEL_CACHE`, `_MODEL_LOCK`, `_get_demucs_model()`

### separator.py (~200 LOC)
- `separate_full_track(audio_file, ...)` - Full file separation
- `separate_chunk(waveform, ...)` - Chunk-level separation
- Warning suppression, stereo conversion, resampling
- **Moves**: Lines 275-368 (get_vocals_file logic), 761-808 (_separate_vocals_chunk)

### detection.py (~250 LOC)
- `scan_chunks_for_onset(...)` - Expanding window logic
- `detect_onset_in_vocal_chunk(...)` - Onset detection
- `compute_rms(...)` - RMS calculation (vectorized)
- `estimate_noise_floor(...)` - Noise floor estimation
- **Moves**: Lines 577-758, 811-947, 950-981, 984-1011

### confidence.py (~120 LOC)
- `compute_confidence(...)` - SNR-based scoring
- **Moves**: Lines 457-566

### cache.py (~80 LOC)
- `VocalsCache` class with LRU eviction
- `get(audio_file, start_ms, end_ms)`
- `put(key, vocals)`
- **Replaces**: OrderedDict usage scattered across detection/confidence

### logging.py (~30 LOC)
- `flush_logs(logger)` utility
- **Moves**: Lines 137-144

## Refactoring Phases

### Phase 0: Test Scaffolding ⏱️ 0.5-1 day
- [ ] Add unit tests for signal processing functions
  - [ ] Test `_compute_rms()` with synthetic signals
  - [ ] Test `_estimate_noise_floor()` edge cases
  - [ ] Test `_detect_onset_in_vocal_chunk()` with known onsets
- [ ] Add integration test with mocked separator
  - [ ] Test `detect_silence_periods()` end-to-end
  - [ ] Verify lazy torch/demucs import behavior
- [ ] Establish baseline benchmarks
  - [ ] Measure chunk scanning time on 30s fixture
  - [ ] Document current performance characteristics

**Acceptance**: Tests pass without premature torch imports

### Phase 1: Configuration Module ⏱️ 2-4 hours
- [ ] Create `src/utils/providers/mdx/__init__.py`
- [ ] Create `src/utils/providers/mdx/config.py`
  - [ ] Move `MdxConfig` dataclass (lines 63-112)
  - [ ] Move `MdxConfig.from_config()` (lines 113-178)
- [ ] Update `mdx_provider.py` imports
- [ ] Run tests to verify behavior unchanged

**Acceptance**: Config works identically, tests pass

### Phase 2: Model Loader ⏱️ 4-6 hours
- [ ] Create `src/utils/providers/mdx/model_loader.py`
  - [ ] Implement `ModelLoader` class
  - [ ] Move `get_device()` logic
  - [ ] Move model loading from `_get_demucs_model()` (lines 204-272)
  - [ ] Add thread-safe caching (replace global cache)
- [ ] Remove `_GLOBAL_MODEL_CACHE` and `_MODEL_LOCK`
- [ ] Update `mdx_provider.py` to use `ModelLoader`
- [ ] Verify lazy import preserved

**Acceptance**: No global mutable state, lazy import works

### Phase 3: Separator Module ⏱️ 6-8 hours
- [ ] Create `src/utils/providers/mdx/separator.py`
  - [ ] Implement `separate_full_track()` (from get_vocals_file)
  - [ ] Implement `separate_chunk()` (from _separate_vocals_chunk)
  - [ ] Centralize warning suppression
  - [ ] Handle stereo conversion consistently
- [ ] Update `mdx_provider.py` to delegate to separator
- [ ] Keep file saving logic in provider

**Acceptance**: Separation works identically, warnings clean

### Phase 4: Detection Pipeline ⏱️ 8-10 hours
- [ ] Create `src/utils/providers/mdx/detection.py`
  - [ ] Move `scan_chunks_for_onset()` (lines 577-758)
  - [ ] Move `detect_onset_in_vocal_chunk()` (lines 811-947)
  - [ ] Move `compute_rms()` (lines 950-981)
  - [ ] Move `estimate_noise_floor()` (lines 984-1011)
  - [ ] Vectorize RMS computation for performance
- [ ] Update `mdx_provider.py` to use detection module
- [ ] Benchmark performance (within ±5% of baseline)

**Acceptance**: Detection behavior identical, performance parity

### Phase 5: Confidence Scoring ⏱️ 4-6 hours
- [ ] Create `src/utils/providers/mdx/confidence.py`
  - [ ] Move `compute_confidence()` (lines 457-566)
  - [ ] Integrate with cache and separator
- [ ] Update `mdx_provider.py` to delegate
- [ ] Verify confidence values match baseline

**Acceptance**: Confidence scoring identical to current

### Phase 6: Vocals Cache ⏱️ 4-6 hours
- [ ] Create `src/utils/providers/mdx/cache.py`
  - [ ] Implement `VocalsCache` with LRU eviction
  - [ ] Add `get()`, `put()`, `evict_oldest()`
  - [ ] Unit tests for capacity and eviction
- [ ] Replace OrderedDict in detection module
- [ ] Replace OrderedDict in confidence module
- [ ] Add cache hit/miss logging

**Acceptance**: Cache capacity respected, eviction works

### Phase 7: Logging Utilities ⏱️ 1-2 hours
- [ ] Create `src/utils/providers/mdx/logging.py`
  - [ ] Move `flush_logs()` (lines 137-144)
  - [ ] Make flush behavior configurable
- [ ] Update callers to use logging module
- [ ] Reduce flush frequency for performance

**Acceptance**: Logging still works, less noisy

### Phase 8: Performance Optimization ⏱️ 4-6 hours
- [ ] Vectorize RMS computation with NumPy
- [ ] Optimize resampling strategy
- [ ] Improve memory management
  - [ ] Use float32 for vocals storage
  - [ ] Free references on cache eviction
- [ ] Parameterize refinement thresholds via config
- [ ] Run performance benchmarks

**Acceptance**: Performance improved or within ±5%

### Phase 9: Rebuild Provider ⏱️ 6-8 hours
- [ ] Refactor `mdx_provider.py` to orchestrator
  - [ ] Keep only public API methods
  - [ ] Delegate to specialized modules
  - [ ] Remove all moved code
  - [ ] Verify file size <500 LOC
- [ ] Update imports and dependencies
- [ ] Run full test suite

**Acceptance**: Provider is thin orchestrator, tests pass

### Phase 10: Error Handling ⏱️ 2-4 hours
- [ ] Normalize `DetectionFailedError` usage
- [ ] Ensure cancellation propagates cleanly
- [ ] Unify error messages
- [ ] Add cancellation checks in detection/separation

**Acceptance**: Error handling consistent, cancellation works

### Phase 11: Documentation ⏱️ 2-4 hours
- [ ] Update `docs/configuration.md`
  - [ ] Document MDX config structure
  - [ ] Document new module organization
- [ ] Update `docs/performance-optimization.md`
  - [ ] Add MDX-specific performance notes
  - [ ] Document FP16, cuDNN, resampling options
- [ ] Add inline docstrings to new modules
- [ ] Update architecture.md if needed

**Acceptance**: Documentation complete and accurate

### Phase 12: Validation ⏱️ 4-6 hours
- [ ] Unit tests for all mdx/* modules
- [ ] Integration tests with mocked ModelLoader
- [ ] Smoke test with samples/ audio
- [ ] Performance benchmarks vs baseline
- [ ] Verify factory lazy-import behavior
- [ ] Run `run.bat analyze` - confirm <500 LOC

**Acceptance**: All tests pass, file length acceptable

## Code Movement Map

| Current Location | New Location | LOC |
|-----------------|--------------|-----|
| `MdxConfig` (63-178) | `mdx/config.py` | ~80 |
| `_get_demucs_model()` (204-272) | `mdx/model_loader.py` | ~70 |
| `get_vocals_file()` logic (275-368) | `mdx/separator.py` | ~90 |
| `compute_confidence()` (457-566) | `mdx/confidence.py` | ~110 |
| `_scan_chunks_for_onset()` (577-758) | `mdx/detection.py` | ~180 |
| `_separate_vocals_chunk()` (761-808) | `mdx/separator.py` | ~50 |
| `_detect_onset_in_vocal_chunk()` (811-947) | `mdx/detection.py` | ~135 |
| `_compute_rms()` (950-981) | `mdx/detection.py` | ~30 |
| `_estimate_noise_floor()` (984-1011) | `mdx/detection.py` | ~25 |
| `_flush_logs()` (137-144) | `mdx/logging.py` | ~10 |
| Global cache/lock | `mdx/model_loader.py` | - |
| OrderedDict cache | `mdx/cache.py` | ~80 |

**Total moved**: ~860 LOC  
**Provider remaining**: ~150 LOC (orchestration + public API)

## Risk Mitigation

### Risk 1: Premature torch/demucs imports
**Impact**: GPU bootstrap fails  
**Mitigation**: 
- Ensure mdx/model_loader imports heavy libs only in `get_model()`
- Add import guard tests
- Test factory lazy-import behavior

### Risk 2: Behavioral drift in detection
**Impact**: Different gap detection results  
**Mitigation**:
- Unit tests with golden signals
- Config-driven thresholds
- Preserve all default values
- Compare outputs on sample files

### Risk 3: Cache eviction bugs
**Impact**: Memory leaks or incorrect cache hits  
**Mitigation**:
- Dedicated VocalsCache unit tests
- Test capacity limits
- Test eviction order (LRU)
- Monitor memory usage

### Risk 4: Performance regression
**Impact**: Slower gap detection  
**Mitigation**:
- Benchmark each phase
- Optimize RMS with vectorization
- Profile hot paths
- Target ±5% of baseline

## Success Metrics

- ✅ mdx_provider.py < 500 LOC (target: ~350-400)
- ✅ All tests passing
- ✅ No global mutable state
- ✅ Lazy import preserved
- ✅ Performance within ±5% of baseline
- ✅ Full test coverage for new modules
- ✅ Documentation updated
- ✅ No regression in GPU/CPU detection

## Progress Tracking

**Overall**: 0/12 phases complete (0%)

```
Phase 0:  ⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜  0%
Phase 1:  ⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜  0%
Phase 2:  ⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜  0%
Phase 3:  ⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜  0%
Phase 4:  ⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜  0%
Phase 5:  ⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜  0%
Phase 6:  ⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜  0%
Phase 7:  ⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜  0%
Phase 8:  ⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜  0%
Phase 9:  ⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜  0%
Phase 10: ⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜  0%
Phase 11: ⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜  0%
Phase 12: ⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜  0%
```

## Next Steps

1. **Review and approve this plan** - Ensure stakeholders agree on approach
2. **Start Phase 0** - Set up test scaffolding and baseline
3. **Execute phases sequentially** - Don't skip ahead
4. **Update this document** - Check off tasks as completed
5. **Run analysis after each phase** - Verify progress with `run.bat analyze`

## Notes

- This refactoring should be done on a dedicated branch
- Commit after each phase completion
- Keep commits focused and atomic
- Update this document as you discover issues
- If a phase takes >2x estimated time, reassess approach

---

**Last Updated**: 2025-10-18  
**Next Review**: Start of Phase 0
