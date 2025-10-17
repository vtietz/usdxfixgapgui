# MDX Provider Module Split - Future Task

## Current State
- **File**: `src/utils/providers/mdx_provider.py`
- **Size**: ~1012 lines (too large for maintainability)
- **Complexity**: 3 functions exceed thresholds (107/81 NLOC, 19/15 CCN)

## Objective
Split the monolithic mdx_provider.py into a clean module structure with focused submodules.

## Proposed Structure

```
src/utils/providers/mdx/
├── __init__.py          # Public API: export MdxProvider
├── config.py            # ✅ DONE: MdxConfig dataclass + constants
├── model_loader.py      # Demucs model loading with thread-safe caching
├── separation.py        # Vocal separation (_separate_vocals_chunk)
├── detection.py         # Onset detection (_detect_onset_in_vocal_chunk, RMS computation)
└── scanning.py          # Chunk scanning orchestration (_scan_chunks_for_onset)
```

## Module Breakdown

### `config.py` ✅ CREATED
- [x] `MdxConfig` dataclass with validation
- [x] Constants: `DEMUCS_MODEL_NAME`, `VOCALS_INDEX`, `DEFAULT_RESAMPLE_HZ`, `DEFAULT_FP16`, `MAX_VOCALS_CACHE_SIZE`
- **Lines**: ~95 lines

### `model_loader.py` (TODO)
- [ ] `get_demucs_model(device, config)` - Lazy load with caching
- [ ] `_GLOBAL_MODEL_CACHE` + `_MODEL_LOCK` - Thread-safe cache
- [ ] GPU/CPU optimizations setup
- [ ] Model warm-up logic
- **Estimated lines**: ~100 lines
- **Functions extracted**: `_get_demucs_model()`, cache management

### `separation.py` (TODO)
- [ ] `separate_vocals_chunk(waveform, sample_rate, device, config, check_cancellation)` - Demucs separation
- [ ] `get_vocals_file(audio_file, destination, config, check_cancellation)` - Full track separation
- **Estimated lines**: ~150 lines
- **Functions extracted**: `_separate_vocals_chunk()`, `get_vocals_file()`

### `detection.py` (TODO)
- [ ] `detect_onset_in_chunk(vocals, sample_rate, chunk_start_ms, config)` - Energy-based onset
- [ ] `_compute_rms(audio, frame_samples, hop_samples)` - RMS computation
- [ ] `_estimate_noise_floor(rms_values, noise_floor_frames)` - Noise estimation
- **Estimated lines**: ~200 lines
- **Functions extracted**: `_detect_onset_in_vocal_chunk()`, `_compute_rms()`, `_estimate_noise_floor()`

### `scanning.py` (TODO)
- [ ] `scan_chunks_for_onset(audio_file, expected_gap_ms, device, config, vocals_cache, check_cancellation)` - Main orchestration
- [ ] Helper: `_calculate_search_window(expected_gap, radius, total_duration)`
- [ ] Helper: `_generate_chunk_boundaries(window_start, window_end, chunk_dur, overlap)`
- [ ] Helper: `_sort_chunks_by_distance(chunks, expected_gap)` - For early-exit optimization
- **Estimated lines**: ~250 lines
- **Functions extracted**: `_scan_chunks_for_onset()` + 3-4 helper methods

### `__init__.py` (TODO)
```python
"""MDX provider - Demucs-based vocal onset detection."""

from utils.providers.mdx.provider import MdxProvider

__all__ = ['MdxProvider']
```

### Main `provider.py` (TODO)
- [ ] `MdxProvider` class - Thin orchestrator using submodules
- [ ] `detect_silences()` - Main public API
- [ ] `compute_confidence()` - Confidence computation
- [ ] `_vocals_cache` management with LRU eviction
- **Estimated lines**: ~200 lines

## Benefits

1. **Maintainability**: Each module has single responsibility (~100-250 lines)
2. **Testability**: Easier to unit test individual functions
3. **Complexity**: Breaks down 107 NLOC functions into manageable chunks
4. **Reusability**: Separation/detection logic can be reused independently
5. **Clarity**: Clear boundaries between concerns (loading, separation, detection, scanning)

## Migration Steps

### Phase 1: Extract Config (✅ DONE)
- [x] Create `mdx/config.py` with `MdxConfig` and constants
- [x] Update `from_config()` to use `__dataclass_fields__`

### Phase 2: Extract Model Loader
1. Create `mdx/model_loader.py`
2. Move `_get_demucs_model()`, `_flush_logs()`, cache globals
3. Update imports in main provider
4. Run tests

### Phase 3: Extract Separation
1. Create `mdx/separation.py`
2. Move `_separate_vocals_chunk()`, `get_vocals_file()`
3. Update imports
4. Run tests

### Phase 4: Extract Detection
1. Create `mdx/detection.py`
2. Move `_detect_onset_in_vocal_chunk()`, `_compute_rms()`, `_estimate_noise_floor()`
3. Update imports
4. Run tests

### Phase 5: Extract Scanning
1. Create `mdx/scanning.py`
2. Move `_scan_chunks_for_onset()`
3. Extract helper methods: `_calculate_search_window()`, `_generate_chunk_boundaries()`, `_sort_chunks_by_distance()`
4. Update imports
5. Run tests

### Phase 6: Create Main Provider
1. Create `mdx/provider.py` with slim `MdxProvider` class
2. Update `mdx/__init__.py` to export `MdxProvider`
3. Update all imports: `from utils.providers.mdx_provider import MdxProvider` → `from utils.providers.mdx import MdxProvider`
4. Deprecate old `mdx_provider.py` (add deprecation warning)
5. Run full test suite
6. Update documentation

### Phase 7: Cleanup
1. Remove old `mdx_provider.py` after confirming all imports updated
2. Update `docs/architecture.md`
3. Final test run

## Testing Strategy

- Run `.\run.bat test` after each phase
- Ensure all 82 tests pass
- Verify complexity reduction with `.\run.bat analyze`
- Manual smoke test: detect gap on 2-3 sample songs

## Estimated Effort

- **Phase 1**: ✅ Complete (~30 minutes)
- **Phases 2-7**: ~2-3 hours total
  - Model loader: 20 minutes
  - Separation: 30 minutes
  - Detection: 40 minutes
  - Scanning: 50 minutes
  - Main provider: 30 minutes
  - Testing/cleanup: 30 minutes

## Priority

**Low-Medium** - Current code works well after refactoring improvements. This split is primarily for maintainability and future development ease, not correctness or performance.

## Related Improvements (Can be done during split)

- [ ] Task 3: Refactor `_scan_chunks_for_onset` - extract helper methods
- [ ] Task 4: Fix sample rate mismatch in vocals cache
- [ ] Task 6: Implement early-exit and radial search optimization
- [ ] Task 8: Reduce logging overhead (remove `_flush_logs()` calls)

## Success Criteria

- [x] All tests pass (82/82)
- [ ] No file exceeds 300 lines
- [ ] All functions < 80 NLOC, < 10 CCN
- [ ] Clear module boundaries and responsibilities
- [ ] Backwards compatible import path (deprecation warning on old path)
- [ ] Documentation updated
