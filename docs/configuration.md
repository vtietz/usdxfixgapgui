# Configuration Reference

USDXFixGap stores its configuration in `config.ini` located at:
- **Windows**: `%LOCALAPPDATA%\USDXFixGap\config.ini`
- **Linux**: `~/.local/share/USDXFixGap/config.ini`

The configuration file is created automatically with default values on first run. This document explains each setting and its valid values.

## [Paths]

### tmp_root
**Default**: `%LOCALAPPDATA%\.tmp` (Windows) or `~/.local/share/.tmp` (Linux)  
**Description**: Directory for temporary files during audio processing (separated vocals, waveforms, etc.)  
**Valid values**: Any valid directory path

### default_directory
**Default**: `%LOCALAPPDATA%\samples` (Windows) or `~/.local/share/samples` (Linux)  
**Description**: Default directory shown when opening songs  
**Valid values**: Any valid directory path

### last_directory
**Default**: Empty (uses default_directory)  
**Description**: Last directory used in file browser - automatically updated by the application  
**Valid values**: Any valid directory path

### models_directory
**Default**: Empty (uses `%LOCALAPPDATA%\models`)  
**Description**: Directory containing AI models for vocal separation (Spleeter/Demucs). Leave empty to use default location.  
**Valid values**: Any valid directory path, or empty for default

## [Detection]

### default_detection_time
**Default**: `30`  
**Description**: Default time window (in seconds) to analyze when detecting gaps  
**Valid values**: Positive integer (recommended: 20-60)

### gap_tolerance
**Default**: `500`  
**Description**: Maximum acceptable gap (in milliseconds) between vocals and note timing. Gaps larger than this are flagged.  
**Valid values**: Positive integer (recommended: 300-1000)

## [Colors]

### detected_gap_color
**Default**: `blue`  
**Description**: Color for visualizing detected gap regions in the waveform  
**Valid values**: Color names (`red`, `blue`, `green`, etc.) or hex codes (`#FF0000`)

### playback_position_color
**Default**: `red`  
**Description**: Color for the playback position indicator line  
**Valid values**: Color names or hex codes

### waveform_color
**Default**: `gray`  
**Description**: Color for the audio waveform display  
**Valid values**: Color names or hex codes

### silence_periods_color
**Default**: `105,105,105,128`  
**Description**: RGBA color for silence period visualization (R,G,B,Alpha values 0-255)  
**Valid values**: Four comma-separated integers (0-255)

## [Player]

### adjust_player_position_step_audio
**Default**: `100`  
**Description**: Milliseconds to skip forward/backward when adjusting original audio position  
**Valid values**: Positive integer (recommended: 50-500)

### adjust_player_position_step_vocals
**Default**: `10`  
**Description**: Milliseconds to skip forward/backward when fine-tuning separated vocals position  
**Valid values**: Positive integer (recommended: 5-50)

## [Processing]

### method
**Default**: `mdx`  
**Description**: AI vocal separation method  
**Valid values**:
- `mdx` - Demucs-based (recommended, fastest with GPU, best quality)
- `spleeter` - Legacy Spleeter engine (slower, still supported)
- `hq_segment` - Windowed Spleeter (legacy, highest quality but slowest)

### normalization_level
**Default**: `-20`  
**Description**: Target dB level for audio normalization  
**Valid values**: Negative integer (recommended: -20 to -6)

### auto_normalize
**Default**: `false`  
**Description**: Whether to automatically normalize audio during processing  
**Valid values**: `true`, `false`

## [spleeter]

### silence_detect_params
**Default**: `silencedetect=noise=-30dB:d=0.2`  
**Description**: FFmpeg silencedetect filter parameters for Spleeter method  
**Valid values**: FFmpeg filter syntax (e.g., `silencedetect=noise=-30dB:d=0.2`)

## [hq_segment]

### hq_preview_pre_ms
**Default**: `3000`  
**Description**: Milliseconds of audio before detected onset to include in preview  
**Valid values**: Positive integer (recommended: 1000-5000)

### hq_preview_post_ms
**Default**: `9000`  
**Description**: Milliseconds of audio after detected onset to include in preview  
**Valid values**: Positive integer (recommended: 5000-15000)

### silence_detect_params
**Default**: `-30dB d=0.3`  
**Description**: Silence detection parameters for HQ segment method  
**Valid values**: String format `<noise_level>dB d=<duration_seconds>`

## [mdx]

MDX (Demucs-based) method settings for high-quality, GPU-accelerated vocal separation.

### Chunked Processing

#### chunk_duration_ms
**Default**: `12000`  
**Description**: Duration of each audio chunk for Demucs processing (12 seconds)  
**Valid values**: Positive integer (recommended: 8000-20000)

#### chunk_overlap_ms
**Default**: `6000`  
**Description**: Overlap between consecutive chunks (50% of chunk_duration_ms recommended)  
**Valid values**: Positive integer, typically 30-70% of chunk_duration_ms

### Energy Analysis

#### frame_duration_ms
**Default**: `25`  
**Description**: Duration of each frame for RMS (energy) computation  
**Valid values**: Positive integer (recommended: 20-50)

#### hop_duration_ms
**Default**: `20`  
**Description**: Time between consecutive frames (smaller = more precise but slower)  
**Valid values**: Positive integer (recommended: 10-30)

#### noise_floor_duration_ms
**Default**: `800`  
**Description**: Duration at start of audio used to estimate background noise level  
**Valid values**: Positive integer (recommended: 500-2000)

### Onset Detection

#### onset_snr_threshold
**Default**: `6.0`  
**Description**: Signal-to-noise ratio threshold for detecting vocal onset (RMS must exceed noise + 6.0×sigma)  
**Valid values**: Float (recommended: 4.0-10.0, higher = stricter)

#### onset_abs_threshold
**Default**: `0.02`  
**Description**: Absolute minimum RMS threshold (2% amplitude) to prevent false positives in quiet sections  
**Valid values**: Float 0.0-1.0 (recommended: 0.01-0.05)

#### min_voiced_duration_ms
**Default**: `300`  
**Description**: Minimum duration of sustained vocals to confirm onset (filters out transients)  
**Valid values**: Positive integer (recommended: 200-500)

#### hysteresis_ms
**Default**: `200`  
**Description**: Backward refinement window for precise onset timing  
**Valid values**: Positive integer (recommended: 100-500)

### Expanding Search

#### initial_radius_ms
**Default**: `7500`  
**Description**: Initial search window radius around expected gap (±7.5 seconds)  
**Valid values**: Positive integer (recommended: 5000-15000)

#### radius_increment_ms
**Default**: `7500`  
**Description**: How much to expand search window on each iteration  
**Valid values**: Positive integer (recommended: 5000-10000)

#### max_expansions
**Default**: `3`  
**Description**: Maximum number of search window expansions (3 = ±30s total coverage)  
**Valid values**: Positive integer (recommended: 2-5)

### Performance Optimizations

#### use_fp16
**Default**: `false`  
**Description**: Use 16-bit floating point for GPU processing (faster but less precise)  
**Note**: Currently disabled due to type compatibility issues  
**Valid values**: `true`, `false`

#### resample_hz
**Default**: `0`  
**Description**: Downsample audio for faster CPU processing (0 = disabled)  
**Valid values**: 0 (disabled), or sample rate like 32000, 22050

### Confidence and Preview

#### confidence_threshold
**Default**: `0.55`  
**Description**: Minimum SNR-based confidence score to accept detected onset  
**Valid values**: Float 0.0-1.0 (recommended: 0.4-0.7, higher = stricter)

#### preview_pre_ms
**Default**: `3000`  
**Description**: Preview window before detected onset (3 seconds)  
**Valid values**: Positive integer (recommended: 1000-5000)

#### preview_post_ms
**Default**: `9000`  
**Description**: Preview window after detected onset (9 seconds)  
**Valid values**: Positive integer (recommended: 5000-15000)

## [General]

### DefaultOutputPath
**Default**: `%LOCALAPPDATA%\output` (Windows) or `~/.local/share/output` (Linux)  
**Description**: Default directory for saving processed audio files  
**Valid values**: Any valid directory path

### LogLevel
**Default**: `INFO`  
**Description**: Logging verbosity level  
**Valid values**: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`

### GPU Acceleration Settings

#### GpuOptIn
**Default**: `false`  
**Description**: Enable GPU acceleration for AI vocal separation (5-10x faster)  
**Valid values**: `true`, `false`

#### GpuFlavor
**Default**: `cu121`  
**Description**: CUDA version for GPU Pack  
**Valid values**: `cu121` (CUDA 12.1), `cu124` (CUDA 12.4)

#### GpuPackInstalledVersion
**Default**: Empty  
**Description**: Version of installed GPU Pack (automatically managed)  
**Valid values**: Version string (e.g., `2.4.1+cu121`) or empty

#### GpuPackPath
**Default**: Empty  
**Description**: Installation path of GPU Pack (automatically managed)  
**Valid values**: Valid directory path or empty

#### GpuLastHealth
**Default**: Empty  
**Description**: Last GPU health check result (automatically managed)  
**Valid values**: Health status string or empty

#### GpuLastError
**Default**: Empty  
**Description**: Last GPU error message for diagnostics (automatically managed)  
**Valid values**: Error message string or empty

#### GpuPackDialogDontShow
**Default**: `false`  
**Description**: Suppress GPU Pack download dialog at startup  
**Valid values**: `true`, `false`

## [Audio]

### DefaultVolume
**Default**: `0.5`  
**Description**: Default playback volume (0.0 = muted, 1.0 = maximum)  
**Valid values**: Float 0.0-1.0

### AutoPlay
**Default**: `False`  
**Description**: Automatically start playback when loading audio  
**Valid values**: `True`, `False`

## Editing Configuration

You can manually edit `config.ini` while the application is closed. The application will validate settings on startup and use defaults for any invalid values.

**Location**: 
```
Windows: %LOCALAPPDATA%\USDXFixGap\config.ini
Linux:   ~/.local/share/USDXFixGap/config.ini
```

**Tip**: Delete `config.ini` to reset all settings to defaults.
