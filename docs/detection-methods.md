# Vocal Onset Detection Methods

This document describes the configurable detection methods available in USDXFixGap for identifying vocal onset timing and gap detection.

## Overview

USDXFixGap now supports multiple detection methods that can be selected via configuration. Each method offers different trade-offs between speed, accuracy, and resource requirements.

## Detection Methods

### 1. **vad_preview** (Default - Recommended)

**Fast, CPU-only onset detection using Voice Activity Detection (VAD) and Harmonic-Percussive Source Separation (HPSS).**

#### How it works:
1. **HPSS Separation**: Splits audio into harmonic (tonal/vocal) and percussive (rhythmic) components using librosa
2. **VAD Processing**: Applies WebRTC Voice Activity Detection on the harmonic channel to identify speech segments
3. **Onset Detection**: Uses speech boundaries to locate vocal onsets with spectral flux snap for precision
4. **Preview Generation**: Creates a focused preview window (3s before, 9s after detected gap) with:
   - Blended HPSS (80% harmonic + 20% percussive)
   - VAD-based gating to suppress non-vocal frames
   - Voice clarity filters
5. **Confidence Scoring**: Combines VAD probability (70%) and spectral flux (30%) to assess detection quality

#### Advantages:
- **Fast**: No full-track stem separation required (~500ms typical processing time)
- **CPU-Only**: No GPU dependencies
- **Accurate**: Optimized for soft vocal entries that Spleeter might miss
- **Generates Preview**: Automatically creates a focused preview audio and waveform JSON for UI

#### Configuration (`[vad_preview]` section):
```ini
preview_pre_ms = 3000          # Milliseconds before gap in preview
preview_post_ms = 9000         # Milliseconds after gap in preview
vad_frame_ms = 30              # VAD frame duration (10, 20, or 30)
vad_min_speech_ms = 120        # Minimum speech segment duration
vad_min_silence_ms = 200       # Minimum silence to split segments
flux_snap_window_ms = 150      # Window for spectral flux onset snap
vad_aggressiveness = 3         # VAD sensitivity (0-3, higher = more aggressive)
```

#### Dependencies:
- `librosa` - HPSS and spectral analysis
- `webrtcvad` - Voice activity detection
- `soundfile` - Audio I/O
- `numpy`, `scipy` - Signal processing

---

### 2. **spleeter** (Legacy)

**Original Spleeter-based full stem separation.**

#### How it works:
1. Full 2-stem separation using Spleeter's pre-trained models
2. FFmpeg silence detection on isolated vocals
3. Nearest gap boundary detection
4. Voice clarity filters applied to vocals

#### Advantages:
- **Proven**: Battle-tested method used in previous versions
- **High Quality**: Full stem separation provides clean vocals
- **Familiar**: Existing workflow and configuration

#### Disadvantages:
- **Slow**: Full-track separation takes 30-60 seconds
- **Heavy**: Requires TensorFlow and pre-trained models
- **Less Precise**: Fixed silence thresholds may miss soft vocal entries

#### Configuration (`[spleeter]` section):
```ini
silence_detect_params = silencedetect=noise=-30dB:d=0.2
```

#### Dependencies:
- `spleeter` - Stem separation
- TensorFlow (included with Spleeter)
- Pre-trained models (downloaded automatically)

---

### 3. **hq_segment** (Future - Placeholder)

**High-quality short-window stem separation for on-demand re-analysis.**

#### Planned features:
- Small MDX or Demucs models for compact, high-quality stems
- Only processes the preview window (not full track)
- Triggered when confidence < threshold or user requests "Re-analyze (HQ)"

#### Current status:
- Falls back to `vad_preview` method
- Placeholder for future implementation

---

## Method Selection

### In `config.ini`:

```ini
[Processing]
method = vad_preview    # Options: vad_preview, spleeter, hq_segment
```

### Choosing a Method:

| Use Case | Recommended Method | Why |
|----------|-------------------|-----|
| **General use** | `vad_preview` | Fast, accurate, generates previews |
| **Soft vocal entries** | `vad_preview` | Better detection of subtle onsets |
| **Legacy compatibility** | `spleeter` | Matches previous behavior |
| **Low confidence cases** | `hq_segment` (future) | High-quality re-analysis |
| **No dependencies** | `spleeter` | Already installed in existing setup |

---

## Detection Metadata

All methods now save enhanced metadata to `usdxfixgap.info`:

```json
{
  "status": "MATCH",
  "detected_gap": 12500,
  "confidence": 0.85,
  "detection_method": "vad_preview",
  "preview_wav_path": "path/to/vocals_preview.wav",
  "waveform_json_path": "path/to/waveform.json",
  "detected_gap_ms": 12500.0,
  "tolerance_band_ms": 500
}
```

### Fields:
- **detection_method**: Which method was used
- **confidence**: Detection confidence (0.0-1.0)
- **preview_wav_path**: Path to preview audio (for non-Spleeter methods)
- **waveform_json_path**: Path to waveform visualization data
- **detected_gap_ms**: Raw detected gap in milliseconds
- **tolerance_band_ms**: Configured tolerance from settings

---

## Performance Comparison

| Method | Typical Time | CPU Usage | GPU Required | Accuracy (soft onsets) |
|--------|--------------|-----------|--------------|------------------------|
| `vad_preview` | 0.5-2s | Moderate | No | Excellent |
| `spleeter` | 30-60s | High | Optional | Good |
| `hq_segment` | 5-10s | High | Optional | Excellent |

*Times for a 3-minute track on typical hardware*

---

## Migration from Old Config

If you have an existing `config.ini` with:

```ini
[Processing]
spleeter = true
```

The system will automatically:
1. Read `method` if present
2. Fall back to `spleeter` if `spleeter = true` (backward compatibility)
3. Default to `vad_preview` if neither is set

To migrate to the new system:
```ini
[Processing]
method = vad_preview  # Replace 'spleeter = true' with this
```

---

## Troubleshooting

### VAD Method Issues

**Problem**: VAD detection fails or returns empty segments

**Solutions**:
1. Check webrtcvad is installed: `pip install webrtcvad`
2. Verify audio file format (must be compatible with ffmpeg)
3. Adjust `vad_aggressiveness` (try lower values like 1 or 2)
4. Increase `vad_min_speech_ms` to filter out noise
5. Check logs for specific error messages

**Fallback**: System automatically falls back to FFmpeg silence detection if VAD fails

---

### Dependency Installation

**VAD Preview method requires**:
```bash
pip install librosa webrtcvad soundfile numpy scipy
```

**Or use the project's requirements.txt**:
```bash
run.bat install
```

---

### Confidence Scores

**Interpreting confidence values**:
- **> 0.8**: High confidence - detection likely accurate
- **0.6 - 0.8**: Moderate confidence - worth reviewing
- **< 0.6**: Low confidence - consider manual review or HQ re-analysis (future)

**What affects confidence**:
- VAD probability at onset point (70% weight)
- Spectral flux magnitude (30% weight)
- Audio quality and background noise
- Clarity of vocal entry

---

## API Changes

### Backward Compatibility

All existing code continues to work:
- `detect_gap.perform()` returns same `DetectGapResult` structure
- `get_vocals_file()` returns path to vocals/preview file
- Worker and Actions signatures unchanged

### Extended Fields

New optional fields in `DetectGapResult`:
```python
result.confidence          # Optional[float]
result.detection_method    # str
result.preview_wav_path    # Optional[str]
result.waveform_json_path  # Optional[str]
result.detected_gap_ms     # Optional[float]
```

### Provider System

For advanced usage, you can directly access providers:

```python
from utils.detection_provider import get_detection_provider

provider = get_detection_provider(config)
method_name = provider.get_method_name()
confidence = provider.compute_confidence(audio_file, gap_ms)
```

---

## Future Enhancements

1. **HQ Segment Implementation**: MDX/Demucs integration for high-quality re-analysis
2. **UI Integration**: "Re-analyze (HQ)" button when confidence < threshold
3. **Silero VAD**: Alternative to WebRTC VAD with neural network approach
4. **Onset Snap**: Spectral flux-based fine-tuning of detected boundaries
5. **Multi-method**: Run multiple methods and choose best confidence

---

## References

- **WebRTC VAD**: https://github.com/wiseman/py-webrtcvad
- **Librosa HPSS**: https://librosa.org/doc/main/generated/librosa.effects.hpss.html
- **Spleeter**: https://github.com/deezer/spleeter

---

**Last Updated**: 2025-10-11
