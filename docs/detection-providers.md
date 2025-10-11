# Detection Providers - Understanding "Extracted Voices"

## Overview

USDXFixGap uses a **provider pattern** for gap detection, offering three distinct methods optimized for different use cases. Each provider has different semantics for what "extracted voices" means and how gap boundaries are detected.

## Architecture

### Module Structure

The detection system is organized into a clean, modular architecture:

```
src/utils/
├── providers/               # Provider package (pluggable strategies)
│   ├── __init__.py         # Public API exports
│   ├── base.py             # IDetectionProvider interface
│   ├── factory.py          # Provider selection logic
│   ├── exceptions.py       # Provider-specific exceptions
│   ├── spleeter_provider.py      # Full-track AI separation
│   ├── vad_preview_provider.py   # Fast VAD + HPSS preview
│   └── hq_segment_provider.py    # Windowed Spleeter
├── types.py                # Dataclass definitions (DetectGapResult, etc.)
└── detect_gap.py           # Orchestration layer (perform() function)
```

### Provider Interface

All providers implement the `IDetectionProvider` interface with four core methods:

```python
class IDetectionProvider(ABC):
    def get_vocals_file(...) -> str:
        """Get or create vocals/preview file for gap detection"""
        
    def detect_silence_periods(...) -> List[Tuple[float, float]]:
        """Detect silence or speech boundary periods in audio"""
        
    def compute_confidence(...) -> float:
        """Compute confidence score for the detected gap"""
        
    def get_method_name() -> str:
        """Return provider identifier ('vad_preview', 'spleeter', etc.)"""
```

### Factory Pattern

Provider selection is handled by `get_detection_provider(config)`:

```python
from utils.providers import get_detection_provider

provider = get_detection_provider(config)
method = provider.get_method_name()  # 'vad_preview', 'spleeter', 'hq_segment'
```

Falls back to `VadPreviewProvider` for unknown methods.

### Exception Hierarchy

Custom exceptions provide clear error handling:

- `ProviderError`: Base exception for all provider errors
- `ProviderInitializationError`: Provider cannot be initialized (missing config, dependencies)
- `DetectionFailedError`: Gap detection failed during processing (includes provider name and cause)

### Data Flow

```mermaid
graph LR
    A[Config] --> B[Factory]
    B --> C[Provider Instance]
    C --> D[get_vocals_file]
    D --> E[detect_silence_periods]
    E --> F[Boundary Selection]
    F --> G[compute_confidence]
    G --> H[DetectGapResult]
```

### Adding New Providers

To add a new detection provider:

1. Create `utils/providers/my_provider.py`
2. Implement `IDetectionProvider` interface
3. Add to `factory.py` method selection
4. Export in `providers/__init__.py`
5. Add configuration section to `Config`
6. Update documentation with provider details

## Provider Types

### 1. VAD Preview (`vad_preview`) - Default Method

**Purpose**: Fast vocal onset detection for debugging gap timing

**What You Get**:
- **NOT a true isolated vocal stem**
- A **vocal-forward preview snippet** designed for onset verification
- Processed audio segment centered around the detected gap

**Detection Pipeline**:
1. **Band-limited HPSS**: Extracts harmonic component from original audio with vocal-range band-pass filter (80Hz-8000Hz)
2. **VAD Analysis**: WebRTC Voice Activity Detection identifies speech segments
3. **Speech-Start Selection**: Finds nearest vocal onset (speech segment START) to original gap
4. **Spectral Flux Snap** (optional): Refines boundary to local onset peak within ±150ms window
5. **Preview Generation**: Creates 12s snippet (3s pre + 9s post gap) with:
   - HPSS blend (80% harmonic + 20% percussive)
   - VAD gating (-9dB attenuation for non-speech regions)
   - Clarity filter (vocal enhancement)

**Confidence Score**: 70% VAD probability + 30% spectral flux magnitude

**Performance**: 0.5-2 seconds per song

**Best For**:
- Quick gap verification
- Batch processing large libraries
- Visual waveform analysis
- When true stems aren't needed

**Limitations**:
- Preview audio is NOT a clean vocal stem
- Contains residual music/harmonics
- Optimized for timing accuracy, not separation quality

---

### 2. Spleeter (`spleeter`) - Legacy Full-Stem Method

**Purpose**: High-quality vocal isolation for the entire track

**What You Get**:
- **True isolated vocal stem** for the full song
- Clean separation of vocals from instrumentation
- Suitable for playback and detailed analysis

**Detection Pipeline**:
1. **Full Stem Separation**: Spleeter AI model processes entire audio file
2. **Silence Detection**: FFmpeg silencedetect on vocals track
3. **Boundary Selection**: Finds nearest silence boundary to original gap
4. **No Spectral Snap**: Uses silence boundaries as-is

**Confidence Score**: Not computed (legacy method)

**Performance**: 30-60 seconds per song

**Best For**:
- When you need actual isolated vocals for listening
- Manual gap adjustment with clean audio
- Songs with complex arrangements
- Quality over speed

**Limitations**:
- Slow processing time
- Higher CPU/memory usage
- Overkill for simple gap verification

---

### 3. HQ Segment (`hq_segment`) - Windowed Stem Method

**Purpose**: True local vocal stem only for the preview window

**What You Get**:
- **True isolated vocal stem** for a focused time window around the gap
- Quality comparable to full Spleeter, but only for the preview region
- Fast processing by analyzing only the relevant segment

**Detection Pipeline**:
1. **Window Extraction**: Extract focused segment (3s pre + 9s post gap) from audio
2. **Windowed Stem Separation**: Run Spleeter on the segment only (not full track)
3. **Silence Detection**: FFmpeg silencedetect on windowed vocal stem
4. **Boundary Selection**: Finds nearest silence boundary within the window
5. **Fallback**: If processing fails, automatically falls back to VAD preview

**Confidence Score**: 85% (high quality stem, but windowed context)

**Performance**: 3-5 seconds per song (significantly faster than full Spleeter)

**Best For**:
- When you need true vocal isolation but full-track processing is too slow
- Quality vocal playback for the gap region
- Songs where VAD preview is insufficient but full Spleeter is overkill
- Balanced speed/quality tradeoff

**Limitations**:
- Only processes the preview window (not full track)
- Requires more time than VAD preview
- Window boundaries may affect very early/late gaps

**Configuration**:
```ini
[hq_segment]
hq_preview_pre_ms = 3000    # Time before gap to extract
hq_preview_post_ms = 9000   # Time after gap to extract
# Uses same silence detection as spleeter
silence_detect_params = -30dB d=0.3
```

---

## Configuration

### Selecting a Provider

In `config.ini`:

```ini
[Processing]
method = vad_preview  # Options: vad_preview, spleeter, hq_segment
```

### VAD Preview Settings

```ini
[vad_preview]
# HPSS parameters
hpss_kernel_size = 31
hpss_power = 2.0
hpss_margin = 1.0

# VAD parameters
vad_frame_ms = 30
vad_min_speech_ms = 120
vad_min_silence_ms = 200
vad_aggressiveness = 3  # 0-3, higher = more aggressive

# Spectral flux snap
flux_snap_enabled = true
flux_snap_window_ms = 150

# Preview generation
preview_pre_ms = 3000   # 3s before gap
preview_post_ms = 9000  # 9s after gap
harmonic_weight = 0.8
percussive_weight = 0.2
vad_gate_attenuation_db = -9
```

### Spleeter Settings

```ini
[spleeter]
silence_detect_params = -30dB,0.5  # threshold,duration
output_path = ./output/spleeter
model = 2stems  # vocals + accompaniment
```

### HQ Segment Settings

```ini
[hq_segment]
hq_reanalyze_threshold = 0.6  # Trigger HQ if confidence < this
hq_model = mdx_small          # Options: mdx_small, demucs_segment
preview_pre_ms = 3000
preview_post_ms = 9000
```

---

## Technical Details

### Why Different Detection Methods?

Each provider answers a different question:

1. **VAD Preview**: "When does the vocal onset occur?" → Speech-start selection
2. **Spleeter**: "Where is the nearest silence in vocals?" → Silence boundary selection
3. **HQ Segment**: "What does the isolated vocal sound like here?" → Local stem + onset

### Speech Segments vs. Silence Periods

**Critical Distinction**:

- **VAD returns speech segments** (when voice is present)
- **Spleeter returns silence periods** (when voice is absent)

The code handles this in `perform()`:

```python
if detection_method == "vad_preview":
    # Speech segments → find nearest SPEECH START (vocal onset)
    detected_gap = detect_nearest_speech_start(speech_segments, original_gap)
else:
    # Silence periods → find nearest SILENCE BOUNDARY
    detected_gap = detect_nearest_gap(silence_periods, original_gap)
```

### Spectral Flux Snapping

Only applied to `vad_preview` method:

1. Initial detection finds approximate vocal onset via VAD
2. `find_flux_peak()` searches ±150ms window for local onset maximum
3. Detected gap snaps to spectral flux peak (actual transient)

Example:
```
VAD detection:     1250ms
Flux peak found:   1263ms
Final gap:         1263ms  (Δ+13ms)
```

Disable via `flux_snap_enabled = false` in config.

---

## Migration Guide

### From Spleeter-Only Workflow

**Before**:
```ini
[Processing]
spleeter = true  # Old style
```

**After**:
```ini
[Processing]
method = spleeter  # Explicit provider selection
```

The code maintains backward compatibility:
```python
# In config.py
self.spleeter = (self.method == 'spleeter')  # Old property still works
```

### Switching to VAD Preview

1. Update `config.ini`:
   ```ini
   method = vad_preview
   ```

2. Understand what changes:
   - **Preview audio**: No longer a full vocal stem, now a vocal-enhanced snippet
   - **Detection speed**: 30-60x faster
   - **Gap accuracy**: May differ slightly due to onset vs. silence detection

3. Re-run gap detection on test songs to verify results

---

## Troubleshooting

### "VAD detection failed, falling back to silence detection"

**Cause**: `librosa` or `webrtcvad` not installed

**Solution**:
```bash
.\run.bat install  # Installs all dependencies
```

### "Preview audio still has music in it"

**Expected Behavior**: VAD preview is NOT a clean vocal stem. It's a vocal-forward **debug snippet**.

**Solutions**:
- Use `method = spleeter` for true isolated vocals
- Wait for `hq_segment` implementation for local stems
- Accept that preview is for timing verification, not listening quality

### "Gap detection is off by 10-20ms"

**Possible Causes**:
1. Spectral flux snap disabled
2. VAD aggressiveness too high/low
3. Speech segment merging too aggressive

**Solutions**:
- Enable flux snap: `flux_snap_enabled = true`
- Adjust `vad_aggressiveness` (try 2 instead of 3)
- Increase `vad_min_speech_ms` to reduce false positives

### "Confidence score always low"

**Causes**:
- Dense instrumentation masking vocals
- Songs without clear vocal onset
- VAD can't detect speech in passage

**Solutions**:
1. Check if first note actually has vocals
2. Try `method = spleeter` for silence-based detection
3. Manually adjust gap if auto-detection unreliable

---

## API Reference

### Provider Interface

All providers implement `IDetectionProvider`:

```python
class IDetectionProvider(ABC):
    @abstractmethod
    def get_vocals_file(
        self, audio_file: str, temp_root: str, 
        destination: str, duration: int, 
        overwrite: bool, check_cancellation
    ) -> str:
        """Return path to vocals/preview audio file."""
        
    @abstractmethod
    def detect_silence_periods(
        self, audio_file: str, vocals_file: str, 
        check_cancellation
    ) -> List[Tuple[float, float]]:
        """Return speech segments OR silence periods (provider-dependent)."""
        
    @abstractmethod
    def compute_confidence(
        self, audio_file: str, detected_gap_ms: float,
        check_cancellation
    ) -> Optional[float]:
        """Return confidence score 0.0-1.0, or None if unavailable."""
        
    @abstractmethod
    def get_method_name(self) -> str:
        """Return provider identifier: 'vad_preview', 'spleeter', 'hq_segment'."""
```

### Factory Function

```python
from utils.detection_provider import get_detection_provider

provider = get_detection_provider(config)
method = provider.get_method_name()  # 'vad_preview', 'spleeter', etc.
```

---

## Summary

| Feature              | VAD Preview            | Spleeter               | HQ Segment              |
|---------------------|------------------------|------------------------|-------------------------|
| **Output**          | Vocal-forward snippet  | Full vocal stem        | Local vocal stem        |
| **Speed**           | 0.5-2s                 | 30-60s                 | 3-5s                    |
| **Quality**         | Debug/timing quality   | Listening quality      | Listening quality       |
| **Detection**       | Speech-start (onset)   | Silence boundary       | Silence boundary (windowed) |
| **Confidence**      | Yes (VAD + flux)       | No                     | Yes (0.85)              |
| **Use Case**        | Batch gap verification | Manual adjustment      | Balanced speed/quality  |
| **Isolated Vocals** | ❌ No                   | ✅ Yes (full track)     | ✅ Yes (window only)     |
| **Fallback**        | N/A                    | N/A                    | VAD preview on error    |

**Recommendation**: Use `vad_preview` for fast batch processing, `hq_segment` for quality results with reasonable speed, or `spleeter` when you need full-track vocal stems.
