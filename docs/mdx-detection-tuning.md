# MDX Detection Parameter Tuning Guide

## Overview

The MDX detection method uses energy-based onset detection on separated vocal stems. This guide explains how to tune parameters when detection is too early or too late.

## Current Optimized Settings (v2.1)

```ini
[mdx]
# Energy Analysis
frame_duration_ms = 25           # Time window for RMS computation
hop_duration_ms = 20             # Stride between frames (12.5ms actual overlap)
noise_floor_duration_ms = 1200   # Initial silence duration for noise estimation

# Onset Detection Thresholds (Optimized for gradual fade-ins)
onset_snr_threshold = 6.5        # Signal-to-noise ratio multiplier
onset_abs_threshold = 0.020      # Minimum absolute RMS level (2.0%)
min_voiced_duration_ms = 200     # Minimum sustained energy duration
hysteresis_ms = 300              # Look-back window for onset refinement
```

### Algorithm Improvements in v2.1

**Better Gradual Fade-In Detection:**
- Changed onset refinement from "steepest rise" to "first consistent rise"
- Increased refinement window from 200ms to 300ms
- Uses adaptive threshold (50% of mean derivative) to find onset start
- Works better for both abrupt starts AND gradual fade-ins

## Problem Symptoms & Solutions

### 🔴 Detection Too Late (Missing Early Vocals)

**Symptoms:**
- Blue line appears after vocals have started
- Missing vocal intro/fade-ins
- Works better on songs with abrupt starts

**Solutions** (try in order):

1. **Reduce `min_voiced_duration_ms`** (current: 250ms)
   - Try: `200ms` → `150ms` → `100ms`
   - Effect: Catches shorter vocal onsets
   - Trade-off: May detect more false positives

2. **Increase `hysteresis_ms`** (current: 250ms)
   - Try: `300ms` → `350ms` → `400ms`
   - Effect: Looks further back for onset start
   - Trade-off: May find pre-vocal noise

3. **Lower `onset_snr_threshold`** (current: 7.0)
   - Try: `6.0` → `5.0` → `4.0`
   - Effect: More sensitive to quiet starts
   - Trade-off: Detects more background noise

4. **Lower `onset_abs_threshold`** (current: 0.025)
   - Try: `0.020` → `0.015` → `0.010`
   - Effect: Catches quieter vocals
   - Trade-off: More false positives from noise

### 🔵 Detection Too Early (Before Actual Vocals)

**Symptoms:**
- Blue line appears in instrumental intro
- Detecting breath sounds, instrumental bleed, or noise
- Works on loud vocals but fails on quiet intros

**Solutions** (try in order):

1. **Increase `onset_snr_threshold`** (current: 7.0)
   - Try: `8.0` → `9.0` → `10.0`
   - Effect: Requires stronger signal above noise
   - Trade-off: May miss quiet vocal starts

2. **Increase `onset_abs_threshold`** (current: 0.025)
   - Try: `0.030` → `0.035` → `0.040`
   - Effect: Higher minimum energy required
   - Trade-off: Misses soft vocal intros

3. **Increase `noise_floor_duration_ms`** (current: 1200ms)
   - Try: `1500ms` → `2000ms` → `2500ms`
   - Effect: Better noise floor estimation
   - Trade-off: Requires longer intro silence

4. **Increase `min_voiced_duration_ms`** (current: 250ms)
   - Try: `300ms` → `350ms` → `400ms`
   - Effect: Ignores brief noise spikes
   - Trade-off: Misses short vocal phrases

## Parameter Reference

### Energy Analysis Parameters

| Parameter | Default | Range | Effect |
|-----------|---------|-------|--------|
| `frame_duration_ms` | 25 | 10-50 | Window size for RMS. Smaller = finer detail but noisier |
| `hop_duration_ms` | 20 | 5-30 | Stride between frames. Smaller = better precision but slower |
| `noise_floor_duration_ms` | 1200 | 500-3000 | How much initial silence to analyze. Longer = more accurate |

### Detection Threshold Parameters

| Parameter | Default | Range | Effect |
|-----------|---------|-------|--------|
| `onset_snr_threshold` | 7.0 | 3.0-12.0 | SNR multiplier. Higher = less sensitive, fewer false positives |
| `onset_abs_threshold` | 0.025 | 0.005-0.100 | Minimum RMS level. Higher = ignores quiet sounds |
| `min_voiced_duration_ms` | 250 | 100-500 | How long energy must stay high. Longer = fewer false positives |
| `hysteresis_ms` | 250 | 100-500 | Look-back window for onset start. Longer = catches earlier onsets |

## Algorithm Overview

The detection process:

1. **Separate vocals** using Demucs (isolate vocal stem)
2. **Compute RMS energy** using sliding windows (25ms frames, 20ms hop)
3. **Estimate noise floor** from first 1200ms of audio
4. **Find sustained energy** above threshold for ≥250ms
5. **Refine onset** by looking back within hysteresis window
6. **Find steepest rise** using energy derivative for precise timing

## Testing Strategy

When tuning parameters:

1. **Test on diverse songs:**
   - Abrupt vocal starts (rock, pop)
   - Gradual fade-ins (ballads)
   - Quiet intros (acoustic)
   - Noisy intros (live recordings)

2. **Check log output** (set `loglevel = DEBUG` in config.ini):
   ```
   Chunk analysis - Noise floor=0.001234, sigma=0.000567, max_rms=0.123456
   Thresholds - SNR_threshold=0.005123, Absolute_threshold=0.025000, Combined=0.025000
   Onset detected at 5234.5ms (RMS=0.034567, threshold=0.025000)
   ```

3. **Iterate on failure cases:**
   - If too late: make MORE sensitive (lower thresholds, shorter durations)
   - If too early: make LESS sensitive (higher thresholds, longer durations)

## Advanced: Per-Song Override

For problematic songs, you can create genre-specific presets or use the GUI to manually adjust after auto-detection.

---

## Edge Case: Negative Gap Values

### Problem
In rare cases, the UI may show **negative gap values** (e.g., -22ms), even though the detection algorithm filters negative onsets.

### Root Causes
1. **Float precision issues** when converting onset timestamps
2. **Rounding errors** in millisecond conversions
3. **Edge cases** in chunk boundary handling

### Safeguards in Place
The pipeline now has **multiple layers of protection**:

```python
# Layer 1: Scanner filters negative onsets (mdx/scanner/pipeline.py)
valid_onsets = [o for o in onsets if o >= 0.0]

# Layer 2: Clamp onset before silence conversion (mdx_provider.py)  
onset_ms = max(0.0, onset_ms)

# Layer 3: Validate final gap value (gap_detection/pipeline.py)
if detected_gap < 0:
    logger.warning(f"Negative gap ({detected_gap}ms), clamping to 0ms")
    detected_gap = 0
```

**Result:** Even if bugs exist elsewhere, the final gap value **cannot be negative**.

If you see a warning in the logs about negative gaps being clamped, please report it as a bug with the song file for investigation.

---

## Version History

### Recent Improvements (v2.0.0 development)

**Gap=0 Edge Case Fix + Negative Gap Safety Net:**
- Fixed `detect_gap_from_silence()` returning wrong boundary for gap=0 songs
  - Changed from "closest boundary" to "end of first silence period"
  - Fixes Disney Duck scenario where scanner detected 2600ms but pipeline returned 0ms
- Added triple-layer negative gap protection:
  - Layer 1: Scanner filters negative onsets
  - Layer 2: MDX provider clamps onset >= 0
  - Layer 3: Pipeline validates detected_gap >= 0
- Optimized thresholds (4.5/0.012/150/350) for gradual fade-ins

**Detection Sensitivity Improvements (v2.2):**
- Real-world testing showed songs with 2+ second gradual fade-ins detected 1.5s late
- Adjusted defaults for better early detection:
  - `onset_snr_threshold`: 6.5 → **5.0** (more sensitive to quiet starts)
  - `onset_abs_threshold`: 0.020 → **0.015** (catches 1.5% energy vs 2.0%)
  - `min_voiced_duration_ms`: 200 → **150** (shorter phrases)
  - `hysteresis_ms`: 300 → **400** (looks further back)
- Added test case `test_02b_very_gradual_fade_in` (2s fade-in validation)
- Trade-off: May occasionally detect breath sounds or pre-vocal artifacts

**Algorithm Improvements (v2.1):**
- Changed onset refinement from "steepest rise" to "first consistent rise"
- Increased refinement window from 200ms to 300ms
- Uses adaptive threshold (50% of mean derivative) to find onset start
- Better for both abrupt starts AND gradual fade-ins

### Earlier Versions
- **v2.0** (2025-10-21): Balanced settings (7.0/0.025/250/250) - compromise between early/late detection
- **v1.0** (Initial): Conservative settings (6.0/0.02/300/200) - favored late over false positives

## See Also

- `src/utils/providers/mdx/detection.py` - Core detection algorithm
- `src/utils/providers/mdx/config.py` - MdxConfig dataclass
- `docs/architecture.md` - System architecture overview

