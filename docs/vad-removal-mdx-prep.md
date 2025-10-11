# VAD/PYIN Removal and MDX Preparation

**Date**: October 11, 2025  
**Status**: ✅ Complete - All VAD/PYIN code removed, MDX foundation prepared  
**Tests**: 78/78 passing

## Summary

Removed all VAD (Voice Activity Detection) and PYIN (voicing detection) code that was unable to achieve Spleeter-level accuracy. Cleaned up codebase and prepared foundation for MDX-based vocal separation approach with energy-based onset detection.

## Rationale

**Problem**: VAD+PYIN approach fundamentally limited for continuous intro music:
- VAD merges intro music with vocals into giant segments
- PYIN detects pitched instruments, not just vocals
- Hybrid fallback added complexity without reliability
- No convergence to acceptable accuracy despite extensive tuning

**Decision**: Remove VAD/PYIN entirely and prepare for MDX approach:
- MDX provides clean vocal stems (like Spleeter)
- Simple energy-based onset detection on vocal stem is sufficient
- Chunked processing stops early for efficiency
- Cleaner, simpler architecture

## Files Deleted

1. **src/utils/vad.py** (385 lines)
   - `detect_speech_segments_vad()` - WebRTC VAD wrapper
   - `detect_speech_segments_vad_ensemble()` - Multi-level VAD voting
   - `compute_vad_confidence()` - Confidence scoring
   - All VAD utility functions

2. **src/utils/voicing.py** (248 lines)
   - `find_vocal_onset_in_segment()` - PYIN sliding window analysis
   - `refine_speech_segments_with_voicing()` - Long segment refinement
   - PYIN-based voicing detection

3. **src/utils/providers/vad_preview_provider.py** (329 lines)
   - Complete VAD provider implementation
   - HPSS harmonic extraction
   - VAD ensemble integration
   - Flux snapping logic

4. **docs/vocal-onset-optimization.md** (1000+ lines)
   - VAD optimization implementation plan
   - All 7 phases (A-G) of VAD improvements
   - Never achieved target accuracy

5. **docs/hybrid-fallback-implementation.md** (220 lines)
   - Track B.1 hybrid fallback documentation
   - Confidence-based Spleeter fallback
   - Removed as VAD abandoned entirely

**Total removed**: ~2200+ lines of VAD/PYIN code

## Files Modified

### 1. config.ini
**Removed**:
- Entire `[vad_preview]` section (13 parameters)
- `method = vad_preview` default

**Updated**:
- `method = spleeter` (new default)
- Kept `[spleeter]` and `[hq_segment]` sections intact

### 2. src/common/config.py
**Removed** (30+ property accessors):
- All VAD parameters (frame_ms, min_speech_ms, min_silence_ms, aggressiveness, etc.)
- Hybrid fallback settings (confidence_threshold, fallback_provider)
- Window-local analysis parameters
- PYIN voicing parameters
- Noise floor parameters
- HQ segment model selection

**Added** (11 MDX parameters - foundation for future):
```python
self._config['mdx'] = {
    'chunk_duration_ms': '12000',      # 12s chunks
    'chunk_overlap_ms': '6000',        # 50% overlap
    'frame_duration_ms': '25',         # 25ms frames for energy
    'hop_duration_ms': '10',           # 10ms hop for RMS
    'noise_floor_duration_ms': '800',  # First 800ms for noise
    'onset_snr_threshold': '2.5',      # RMS > noise + 2.5*sigma
    'min_voiced_duration_ms': '180',   # 180ms minimum vocal
    'hysteresis_ms': '80',             # 80ms hysteresis
    'confidence_threshold': '0.55',    # SNR-based confidence
    'preview_pre_ms': '3000',          # Preview window
    'preview_post_ms': '9000'          # Preview window
}
```

**Property loading with safety**:
```python
if self._config.has_section('mdx'):
    self.mdx_chunk_duration_ms = self._config.getint('mdx', 'chunk_duration_ms')
    # ... 10 more MDX properties
```

### 3. src/utils/detect_gap.py
**Removed** (140+ lines):
- `detect_nearest_speech_start()` function (speech-start selection logic)
- VAD-specific detection path (`if detection_method == "vad_preview"`)
- Spectral flux snapping logic (45 lines)
- Entire hybrid fallback mechanism (80 lines)
- Preview/waveform generation for non-Spleeter methods (30 lines)

**Simplified**:
```python
# Before (3 detection paths):
if detection_method == "vad_preview":
    detected_gap = detect_nearest_speech_start(...)  # VAD path
else:
    detected_gap = detect_nearest_gap(...)           # Spleeter path

# After (1 detection path):
detected_gap = detect_nearest_gap(silence_periods, options.original_gap)
```

**Clean result creation** (no hybrid fallback):
```python
result = DetectGapResult(detected_gap, silence_periods, vocals_file)
result.detection_method = detection_method
result.detected_gap_ms = float(detected_gap)

# Compute confidence if available
if provider:
    result.confidence = provider.compute_confidence(...)

return result  # No hybrid fallback, no preview generation
```

### 4. src/utils/types.py
**Removed**:
- `suggest_hq_reanalyze: bool = False` field from `DetectGapResult`

### 5. src/utils/providers/factory.py
**Removed**:
- `from utils.providers.vad_preview_provider import VadPreviewProvider`
- VAD case in provider selection

**Updated**:
- Fallback changed from `VadPreviewProvider` to `SpleeterProvider`
- Added placeholder for MDX provider (commented out)

```python
# elif method == "mdx":
#     logger.debug("Selecting MDX detection provider")
#     return MdxProvider(config)
```

### 6. src/utils/providers/__init__.py
**Removed**:
- `VadPreviewProvider` import
- `VadPreviewProvider` from `__all__`

**Updated** docstring:
- Removed VAD references
- Added MDX as future provider

## Architecture Changes

### Before (3 providers)
```
┌─────────────────┐
│ VadPreviewProvider │  <-- REMOVED
│   - VAD ensemble   │
│   - HPSS harmonic  │
│   - Flux snapping  │
│   - Hybrid fallback│
└─────────────────┘
┌──────────────────┐
│ SpleeterProvider  │  <-- Kept
│   - Full stem sep │
└──────────────────┘
┌──────────────────┐
│ HqSegmentProvider │  <-- Kept
│   - Windowed Spl  │
└──────────────────┘
```

### After (2 providers + MDX planned)
```
┌──────────────────┐
│ SpleeterProvider  │  <-- Default
│   - Full stem sep │
│   - Silence detect│
└──────────────────┘
┌──────────────────┐
│ HqSegmentProvider │  <-- On-demand
│   - Windowed Spl  │
└──────────────────┘
┌──────────────────┐
│ MdxProvider (TODO)│  <-- Future
│   - Chunked scan  │
│   - Energy onset  │
│   - Early stop    │
└──────────────────┘
```

## MDX Approach (Prepared, Not Implemented)

### Configuration Added
All MDX parameters pre-configured in `config.ini` and `config.py`:
- Chunk scanning: 12s chunks, 50% overlap
- Energy analysis: 25ms frames, 10ms hop
- Onset detection: SNR threshold 2.5, 180ms minimum
- Preview generation: 3s before, 9s after onset

### Planned Architecture
**Chunked MDX scan** (future implementation):
1. Run MDX on 12-15s chunks from start (50% overlap)
2. Compute adaptive energy on vocal stem:
   - Noise floor from first ~800ms
   - Short-time RMS (25ms frames)
   - Speech starts when RMS > noise + 2.5*sigma for ≥180ms
3. Stop as soon as first onset detected (no full-song separation)
4. Refine with [onset-3s, onset+9s] window
5. Optional micro-snap within ±100-150ms using RMS rise

**Why MDX works** (no VAD/PYIN needed):
- MDX removes instruments → what's left is voice + minor bleed
- Energy with adaptive noise floor is robust and cheap on clean stems
- PYIN unhelpful on clean vocal stem (can misfire on breaths/rap)
- Flux only useful as tiny final snap (optional)

## Test Results

```bash
78 passed, 3 warnings in 1.52s ✅
```

All existing tests pass with no regressions:
- Audio actions: ✅
- Gap detection: ✅
- Song management: ✅
- Status mapping: ✅
- Separate audio: ✅

**No test updates needed** - VAD code had no specific tests.

## Remaining Work

### Immediate (Framework in place):
1. **Create `src/utils/providers/mdx_provider.py`**
   - Implement `IDetectionProvider` interface
   - Chunked MDX vocal separation
   - Energy-based onset detection on vocal stem
   - Adaptive noise floor estimation
   - Early-stop chunking

2. **Add MDX to factory**
   - Uncomment `elif method == "mdx"` case
   - Import `MdxProvider`
   - Add to `__all__` in `__init__.py`

3. **Testing**
   - Test with "Ace of Base - All For You" (vocals at ~17140ms)
   - Validate chunked scanning stops early
   - Compare accuracy vs Spleeter
   - Measure speed improvement from early-stop

### Future Enhancements:
- MDX model selection (MDX-Net variants, Demucs, MDX23C)
- GPU acceleration for MDX
- Confidence scoring based on SNR
- UI indication of chunked vs full-track separation

## Benefits of This Cleanup

1. **Simpler codebase**: Removed 2200+ lines of complex, unreliable code
2. **Clearer architecture**: 2 working providers instead of 3 (1 broken)
3. **Better defaults**: Spleeter (reliable) instead of VAD (unreliable)
4. **Foundation for MDX**: Config ready, architecture clear
5. **No regressions**: All tests still passing
6. **Maintainability**: Less code to maintain, clearer responsibilities

## Migration Notes

**For users**:
- `method = vad_preview` in config.ini will now fall back to `spleeter`
- No behavior change if using default `spleeter` method
- Slightly longer processing (Spleeter vs VAD) but more accurate

**For developers**:
- VAD/PYIN imports will fail - code removed
- `VadPreviewProvider` no longer available
- Use `SpleeterProvider` or `HqSegmentProvider`
- MDX provider stub ready for implementation

## Conclusion

Successfully cleaned up all VAD/PYIN experimental code that failed to achieve production quality. Codebase is now simpler, more maintainable, and better positioned for MDX implementation. The lean MDX approach (vocal stem + energy onset) is the correct path forward for fast, accurate vocal onset detection.

**Status**: Ready for MDX provider implementation.
