# Configuration Reference# Configuration Reference# Configuration Reference



USDXFixGap stores its configuration in `config.ini` located at:

- **Windows**: `%LOCALAPPDATA%\USDXFixGap\config.ini`USDXFixGap stores its configuration in `config.ini` located at:USDXF## Editing Configuration

- **Linux**: `~/.local/share/USDXFixGap/config.ini`

- **Windows**: `%LOCALAPPDATA%\USDXFixGap\config.ini`

The configuration file is created automatically with default values on first run. This document explains each setting and its valid values.

- **Linux**: `~/.local/share/USDXFixGap/config.ini`You can manually edit `config.ini` while the application is closed. The application will validate settings on startup and use defaults for any invalid values.

## [Paths]



### tmp_rootThe configuration file is created automatically with default values on first run. This document explains each setting and its valid values.**Location**:

**Default**: `%LOCALAPPDATA%\.tmp` (Windows) or `~/.local/share/.tmp` (Linux)

**Description**: Directory for temporary files during audio processing (separated vocals, waveforms, etc.)  ```

**Valid values**: Any valid directory path## [Paths]Windows: %LOCALAPPDATA%\USDXFixGap\config.ini

Linux:   ~/.local/share/USDXFixGap\config.ini

### default_directory### tmp_root```

**Default**: `%LOCALAPPDATA%\samples` (Windows) or `~/.local/share/samples` (Linux)  **Default**: `%LOCALAPPDATA%\.tmp` (Windows) or `~/.local/share/.tmp` (Linux)

**Description**: Default directory shown when opening songs  **Description**: Directory for temporary files during audio processing (separated vocals, waveforms, etc.)  **Tip**: Delete `config.ini` to reset all settings to defaults.

**Valid values**: Any valid directory path**Valid values**: Any valid directory path

---

### last_directory

**Default**: Empty (uses default_directory)  ### default_directory

**Description**: Last directory used in file browser - automatically updated by the application

**Valid values**: Any valid directory path**Default**: `%LOCALAPPDATA%\samples` (Windows) or `~/.local/share/samples` (Linux)  ## MDX Detection Tuning



### models_directory**Description**: Default directory shown when opening songs

**Default**: Empty (uses `%LOCALAPPDATA%\models`)

**Description**: Directory containing AI models for vocal separation (Demucs). Leave empty to use default location.  **Valid values**: Any valid directory path### Overview

**Valid values**: Any valid directory path, or empty for default



## [Detection]

### last_directoryThe MDX detection method uses energy-based onset detection on separated vocal stems. This section explains how to tune parameters when detection is too early or too late.

### default_detection_time

**Default**: `30`  **Default**: Empty (uses default_directory)

**Description**: Default time window (in seconds) to analyze when detecting gaps

**Valid values**: Positive integer (recommended: 20-60)**Description**: Last directory used in file browser - automatically updated by the application  ### Problem Symptoms & Solutions



### gap_tolerance**Valid values**: Any valid directory path

**Default**: `500`

**Description**: Maximum acceptable gap (in milliseconds) between vocals and note timing. Gaps larger than this are flagged.  #### 🔴 Detection Too Late (Missing Early Vocals)

**Valid values**: Positive integer (recommended: 300-1000)

### models_directory

## [Colors]

**Default**: Empty (uses `%LOCALAPPDATA%\models`)  **Symptoms:**

### detected_gap_color

**Default**: `blue`  **Description**: Directory containing AI models for vocal separation (Demucs). Leave empty to use default location.  - Blue line appears after vocals have started

**Description**: Color for visualizing detected gap regions in the waveform

**Valid values**: Color names (`red`, `blue`, `green`, etc.) or hex codes (`#FF0000`)**Valid values**: Any valid directory path, or empty for default- Missing vocal intro/fade-ins



### playback_position_color- Works better on songs with abrupt starts

**Default**: `red`

**Description**: Color for the playback position indicator line  ## [Detection]

**Valid values**: Color names or hex codes

**Solutions** (try in order):

### waveform_color

**Default**: `gray`  ### default_detection_time

**Description**: Color for the audio waveform display

**Valid values**: Color names or hex codes**Default**: `30`  1. **Reduce `min_voiced_duration_ms`** (default: 150ms)



### silence_periods_color**Description**: Default time window (in seconds) to analyze when detecting gaps     - Try: `100ms` → `80ms` → `50ms`

**Default**: `105,105,105,128`

**Description**: RGBA color for silence period visualization (R,G,B,Alpha values 0-255)  **Valid values**: Positive integer (recommended: 20-60)   - Effect: Catches shorter vocal onsets

**Valid values**: Four comma-separated integers (0-255)

   - Trade-off: May detect more false positives

## [Player]

### gap_tolerance

### adjust_player_position_step_audio

**Default**: `100`  **Default**: `500`  2. **Increase `hysteresis_ms`** (default: 350ms)

**Description**: Milliseconds to skip forward/backward when adjusting original audio position

**Valid values**: Positive integer (recommended: 50-500)**Description**: Maximum acceptable gap (in milliseconds) between vocals and note timing. Gaps larger than this are flagged.     - Try: `400ms` → `450ms` → `500ms`



### adjust_player_position_step_vocals**Valid values**: Positive integer (recommended: 300-1000)   - Effect: Looks further back for onset start

**Default**: `10`

**Description**: Milliseconds to skip forward/backward when fine-tuning separated vocals position     - Trade-off: May find pre-vocal noise

**Valid values**: Positive integer (recommended: 5-50)

## [Colors]

## [Processing]

3. **Lower `onset_snr_threshold`** (default: 4.5)

### method

**Default**: `mdx`  ### detected_gap_color   - Try: `4.0` → `3.5` → `3.0`

**Description**: AI vocal separation method

**Valid values**:**Default**: `blue`     - Effect: More sensitive to quiet starts

- `mdx` - Demucs-based (recommended, fastest with GPU, best quality)

**Description**: Color for visualizing detected gap regions in the waveform     - Trade-off: Detects more background noise

### normalization_level

**Default**: `-20`  **Valid values**: Color names (`red`, `blue`, `green`, etc.) or hex codes (`#FF0000`)

**Description**: Target dB level for audio normalization

**Valid values**: Negative integer (recommended: -20 to -6)4. **Lower `onset_abs_threshold`** (default: 0.012)



### auto_normalize### playback_position_color   - Try: `0.010` → `0.008` → `0.005`

**Default**: `false`

**Description**: Whether to automatically normalize audio during processing  **Default**: `red`     - Effect: Catches quieter vocals

**Valid values**: `true`, `false`

**Description**: Color for the playback position indicator line     - Trade-off: More false positives from noise

## [mdx]

**Valid values**: Color names or hex codes

MDX (Demucs-based) method settings for high-quality, GPU-accelerated vocal separation and onset detection.

#### 🔵 Detection Too Early (Before Actual Vocals)

> **💡 Tuning Guide**: See the [MDX Detection Tuning](#mdx-detection-tuning) section below for help with songs where detection is too early or too late.

### waveform_color

### Chunked Processing

**Default**: `gray`  **Symptoms:**

#### chunk_duration_ms

**Default**: `12000`  **Description**: Color for the audio waveform display  - Blue line appears in instrumental intro

**Description**: Duration of each audio chunk for Demucs processing (12 seconds)

**Valid values**: Positive integer (recommended: 8000-20000)**Valid values**: Color names or hex codes- Detecting breath sounds, instrumental bleed, or noise



#### chunk_overlap_ms- Works on loud vocals but fails on quiet intros

**Default**: `6000`

**Description**: Overlap between consecutive chunks (50% of chunk_duration_ms recommended)  ### silence_periods_color

**Valid values**: Positive integer, typically 30-70% of chunk_duration_ms

**Default**: `105,105,105,128`  **Solutions** (try in order):

### Energy Analysis

**Description**: RGBA color for silence period visualization (R,G,B,Alpha values 0-255)

#### frame_duration_ms

**Default**: `25`  **Valid values**: Four comma-separated integers (0-255)1. **Increase `onset_snr_threshold`** (default: 4.5)

**Description**: Duration of each frame for RMS (energy) computation

**Valid values**: Positive integer (recommended: 20-50)   - Try: `5.0` → `6.0` → `7.0`



#### hop_duration_ms## [Player]   - Effect: Requires stronger signal above noise

**Default**: `20`

**Description**: Time between consecutive frames (smaller = more precise but slower)     - Trade-off: May miss quiet vocal starts

**Valid values**: Positive integer (recommended: 10-30)

### adjust_player_position_step_audio

#### noise_floor_duration_ms

**Default**: `1200`  **Default**: `100`  2. **Increase `onset_abs_threshold`** (default: 0.012)

**Description**: Duration at start of audio used to estimate background noise level

**Valid values**: Positive integer (recommended: 1000-2000)**Description**: Milliseconds to skip forward/backward when adjusting original audio position     - Try: `0.015` → `0.020` → `0.025`



### Onset Detection**Valid values**: Positive integer (recommended: 50-500)   - Effect: Higher minimum energy required



#### onset_snr_threshold   - Trade-off: Misses soft vocal intros

**Default**: `4.5`

**Description**: Signal-to-noise ratio threshold for detecting vocal onset (RMS must exceed noise + 4.5×sigma)  ### adjust_player_position_step_vocals

**Valid values**: Float (recommended: 3.0-10.0, higher = stricter)

**Default**: `10`  3. **Increase `noise_floor_duration_ms`** (default: 1200ms)

#### onset_abs_threshold

**Default**: `0.012`  **Description**: Milliseconds to skip forward/backward when fine-tuning separated vocals position     - Try: `1500ms` → `2000ms` → `2500ms`

**Description**: Absolute minimum RMS threshold (1.2% amplitude) to prevent false positives in quiet sections

**Valid values**: Float 0.0-1.0 (recommended: 0.005-0.05)**Valid values**: Positive integer (recommended: 5-50)   - Effect: Better noise floor estimation



#### min_voiced_duration_ms   - Trade-off: Requires longer intro silence

**Default**: `150`

**Description**: Minimum duration of sustained vocals to confirm onset (filters out transients)  ## [Processing]

**Valid values**: Positive integer (recommended: 100-500)

4. **Increase `min_voiced_duration_ms`** (default: 150ms)

#### hysteresis_ms

**Default**: `350`  ### method   - Try: `200ms` → `250ms` → `300ms`

**Description**: Backward refinement window for precise onset timing

**Valid values**: Positive integer (recommended: 200-500)**Default**: `mdx`     - Effect: Ignores brief noise spikes



### Expanding Search**Description**: AI vocal separation method     - Trade-off: Misses short vocal phrases



#### initial_radius_ms**Valid values**:

**Default**: `7500`

**Description**: Initial search window radius around expected gap (±7.5 seconds)  - `mdx` - Demucs-based (recommended, fastest with GPU, best quality)### Parameter Reference Table

**Valid values**: Positive integer (recommended: 5000-15000)



#### radius_increment_ms

**Default**: `7500`  ### normalization_level| Parameter | Default | Range | Effect |

**Description**: How much to expand search window on each iteration

**Valid values**: Positive integer (recommended: 5000-10000)**Default**: `-20`  |-----------|---------|-------|--------|



#### max_expansions**Description**: Target dB level for audio normalization  | **Energy Analysis** |

**Default**: `3`

**Description**: Maximum number of search window expansions (3 = ±30s total coverage)  **Valid values**: Negative integer (recommended: -20 to -6)| `frame_duration_ms` | 25 | 10-50 | Window size for RMS. Smaller = finer detail but noisier |

**Valid values**: Positive integer (recommended: 2-5)

| `hop_duration_ms` | 20 | 5-30 | Stride between frames. Smaller = better precision but slower |

### Performance Optimizations

### auto_normalize| `noise_floor_duration_ms` | 1200 | 1000-3000 | How much initial silence to analyze. Longer = more accurate |

#### use_fp16

**Default**: `false`  **Default**: `false`  | **Detection Thresholds** |

**Description**: Use 16-bit floating point for GPU processing (faster but less precise)

**Note**: Currently disabled due to type compatibility issues  **Description**: Whether to automatically normalize audio during processing  | `onset_snr_threshold` | 4.5 | 3.0-10.0 | SNR multiplier. Higher = less sensitive, fewer false positives |

**Valid values**: `true`, `false`

**Valid values**: `true`, `false`| `onset_abs_threshold` | 0.012 | 0.005-0.050 | Minimum RMS level. Higher = ignores quiet sounds |

#### resample_hz

**Default**: `0`  | `min_voiced_duration_ms` | 150 | 50-500 | How long energy must stay high. Longer = fewer false positives |

**Description**: Downsample audio for faster CPU processing (0 = disabled)

**Valid values**: 0 (disabled), or sample rate like 32000, 22050## [mdx]| `hysteresis_ms` | 350 | 200-500 | Look-back window for onset start. Longer = catches earlier onsets |



### Confidence and Preview



#### confidence_thresholdMDX (Demucs-based) method settings for high-quality, GPU-accelerated vocal separation and onset detection.### Algorithm Overview

**Default**: `0.55`

**Description**: Minimum SNR-based confidence score to accept detected onset

**Valid values**: Float 0.0-1.0 (recommended: 0.4-0.7, higher = stricter)

> **💡 Tuning Guide**: See the [MDX Detection Tuning](#mdx-detection-tuning) section below for help with songs where detection is too early or too late.The detection process:

#### preview_pre_ms

**Default**: `3000`

**Description**: Preview window before detected onset (3 seconds)

**Valid values**: Positive integer (recommended: 1000-5000)### Chunked Processing1. **Separate vocals** using Demucs (isolate vocal stem)



#### preview_post_ms2. **Compute RMS energy** using sliding windows (25ms frames, 20ms hop)

**Default**: `9000`

**Description**: Preview window after detected onset (9 seconds)  #### chunk_duration_ms3. **Estimate noise floor** from first 1200ms of audio

**Valid values**: Positive integer (recommended: 5000-15000)

**Default**: `12000`  4. **Find sustained energy** above threshold for ≥150ms

## [General]

**Description**: Duration of each audio chunk for Demucs processing (12 seconds)  5. **Refine onset** by looking back within hysteresis window (350ms)

### Runtime Artifacts and Cache

**Valid values**: Positive integer (recommended: 8000-20000)6. **Find first consistent rise** using energy derivative for precise timing

**Runtime artifacts** (separated vocals, waveform images) are automatically cached under:

- **Windows**: `%LOCALAPPDATA%\USDXFixGap\.tmp\<hash>\<song-basename>\`

- **Linux**: `~/.local/share/USDXFixGap/.tmp\<hash>\<song-basename>\`

- **macOS**: `~/Library/Application Support/USDXFixGap/.tmp\<hash>\<song-basename>\`#### chunk_overlap_ms### Testing Strategy



These files are temporary and managed automatically by the application. They are not persisted outside the `.tmp` cache unless explicitly exported. The cache is automatically cleaned up based on usage patterns.**Default**: `6000`



### log_level**Description**: Overlap between consecutive chunks (50% of chunk_duration_ms recommended)  When tuning parameters:

**Default**: `INFO`

**Description**: Logging verbosity level  **Valid values**: Positive integer, typically 30-70% of chunk_duration_ms

**Valid values**: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`

1. **Test on diverse songs:**

### GPU Acceleration Settings

### Energy Analysis   - Abrupt vocal starts (rock, pop)

#### gpu_opt_in

**Default**: `false`     - Gradual fade-ins (ballads)

**Description**: Enable GPU acceleration for AI vocal separation (5-10x faster)

**Valid values**: `true`, `false`#### frame_duration_ms   - Quiet intros (acoustic)



#### gpu_flavor**Default**: `25`     - Noisy intros (live recordings)

**Default**: `cu121`

**Description**: CUDA version for GPU Pack  **Description**: Duration of each frame for RMS (energy) computation

**Valid values**: `cu121` (CUDA 12.1), `cu124` (CUDA 12.4)

**Valid values**: Positive integer (recommended: 20-50)2. **Check log output** (set `log_level = DEBUG` in config.ini):

#### gpu_pack_installed_version

**Default**: Empty     ```

**Description**: Version of installed GPU Pack (automatically managed)

**Valid values**: Version string (e.g., `2.4.1+cu121`) or empty#### hop_duration_ms   Chunk analysis - Noise floor=0.001234, sigma=0.000567, max_rms=0.123456



#### gpu_pack_path**Default**: `20`     Thresholds - SNR_threshold=0.005123, Absolute_threshold=0.012000, Combined=0.012000

**Default**: Empty

**Description**: Installation path of GPU Pack (automatically managed)  **Description**: Time between consecutive frames (smaller = more precise but slower)     Onset detected at 5234.5ms (RMS=0.034567, threshold=0.012000)

**Valid values**: Valid directory path or empty

**Valid values**: Positive integer (recommended: 10-30)   ```

#### gpu_last_health

**Default**: Empty

**Description**: Last GPU health check result (automatically managed)

**Valid values**: Health status string or empty#### noise_floor_duration_ms3. **Iterate on failure cases:**



#### gpu_last_error**Default**: `1200`     - If too late: make MORE sensitive (lower thresholds, shorter durations)

**Default**: Empty

**Description**: Last GPU error message for diagnostics (automatically managed)  **Description**: Duration at start of audio used to estimate background noise level     - If too early: make LESS sensitive (higher thresholds, longer durations)

**Valid values**: Error message string or empty

**Valid values**: Positive integer (recommended: 1000-2000)

#### splash_dont_show_health

**Default**: `false`

**Description**: Skip health check page in startup wizard (system capabilities will still be checked in background)

**Valid values**: `true`, `false`

#### gpu_pack_dont_ask

**Default**: `false`

**Description**: Skip GPU Pack offer page in startup wizard (you can still install via Tools menu)

**Valid values**: `true`, `false`

#### gpu_pack_dialog_dont_show

**Default**: `false`  ### Advanced: Per-Song Manual Adjustment

**Description**: Suppress GPU Pack download dialog at startup (legacy - use gpu_pack_dont_ask instead)

**Valid values**: `true`, `false`### Onset Detection



## [Audio]For problematic songs where auto-detection fails, you can use the GUI to manually adjust the gap value after detection completes.



### default_volume#### onset_snr_threshold

**Default**: `0.5`

**Description**: Default playback volume (0.0 = muted, 1.0 = maximum)  **Default**: `4.5`  ---

**Valid values**: Float 0.0-1.0

**Description**: Signal-to-noise ratio threshold for detecting vocal onset (RMS must exceed noise + 4.5×sigma)

### auto_play

**Default**: `false`  **Valid values**: Float (recommended: 3.0-10.0, higher = stricter)## Related Documentation

**Description**: Automatically start playback when loading audio

**Valid values**: `true`, `false`



## [Window]#### onset_abs_threshold- [Architecture](architecture.md) - System architecture and design patterns



### width**Default**: `0.012`  - [Development Guide](DEVELOPMENT.md) - Setup, testing, and code quality toolss its configuration in `config.ini` located at:

**Default**: `1024`

**Description**: Window width in pixels (automatically saved when closing the application)  **Description**: Absolute minimum RMS threshold (1.2% amplitude) to prevent false positives in quiet sections  - **Windows**: `%LOCALAPPDATA%\USDXFixGap\config.ini`

**Valid values**: Positive integer (minimum: 600)

**Valid values**: Float 0.0-1.0 (recommended: 0.005-0.05)- **Linux**: `~/.local/share/USDXFixGap/config.ini`

### height

**Default**: `768`

**Description**: Window height in pixels (automatically saved when closing the application)

**Valid values**: Positive integer (minimum: 600)#### min_voiced_duration_msThe configuration file is created automatically with default values on firs**Default**: `False`



### x**Default**: `150`  **Description**: Automatically start playback when loading audio

**Default**: `-1`

**Description**: Window X position on screen (-1 = centered by OS, automatically saved when closing)  **Description**: Minimum duration of sustained vocals to confirm onset (filters out transients)  **Valid values**: `True`, `False`

**Valid values**: Integer (-1 for auto-center, or screen coordinates)

**Valid values**: Positive integer (recommended: 100-500)

### y

**Default**: `-1`  ## [Window]

**Description**: Window Y position on screen (-1 = centered by OS, automatically saved when closing)

**Valid values**: Integer (-1 for auto-center, or screen coordinates)#### hysteresis_ms



## [WatchMode]**Default**: `350`  ### width



Watch Mode provides real-time filesystem monitoring to automatically update caches and schedule gap detection when songs are added, modified, or removed.**Description**: Backward refinement window for precise onset timing  **Default**: `1024`



### watch_mode_default**Valid values**: Positive integer (recommended: 200-500)**Description**: Window width in pixels (automatically saved when closing the application)

**Default**: `false`

**Description**: Automatically enable watch mode when a directory is loaded  **Valid values**: Positive integer (minimum: 600)

**Valid values**: `true`, `false`

### Expanding Search

### watch_debounce_ms

**Default**: `500`  ### height

**Description**: Milliseconds to wait after the last filesystem event before processing changes. This prevents processing storms during bulk file operations (e.g., copying multiple songs).

**Valid values**: Positive integer (recommended: 300-1000)#### initial_radius_ms**Default**: `768`



### watch_ignore_patterns**Default**: `7500`  **Description**: Window height in pixels (automatically saved when closing the application)

**Default**: `.tmp,~,.crdownload,.part`

**Description**: Comma-separated list of file extension patterns to ignore. These are typically temporary files created by editors, browsers, or download managers.  **Description**: Initial search window radius around expected gap (±7.5 seconds)  **Valid values**: Positive integer (minimum: 600)

**Valid values**: Comma-separated string of patterns (e.g., `.tmp,.bak,~,.swp,.crdownload,.part`)

**Valid values**: Positive integer (recommended: 5000-15000)

**How Watch Mode Works**:

- **Created**: New .txt files or folders are detected and scheduled for scanning### x

- **Modified**: Changes to .txt, .mp3, or .wav files automatically queue gap detection

- **Deleted**: Removed songs are deleted from cache and UI#### radius_increment_ms**Default**: `-1`

- **Moved/Renamed**: Treated as delete + create for cache consistency

**Default**: `7500`  **Description**: Window X position on screen (-1 = centered by OS, automatically saved when closing)

**Performance Notes**:

- Uses OS-native filesystem watchers (Windows ReadDirectoryChangesW, macOS FSEvents, Linux inotify)**Description**: How much to expand search window on each iteration  **Valid values**: Integer (-1 for auto-center, or screen coordinates)

- Debouncing prevents duplicate processing during rapid file changes

- Only changed songs are processed, not the entire directory**Valid values**: Positive integer (recommended: 5000-10000)

- At-most-one detection task per song prevents duplicates

### y

## Editing Configuration

#### max_expansions**Default**: `-1`

You can manually edit `config.ini` while the application is closed. The application will validate settings on startup and use defaults for any invalid values.

**Default**: `3`  **Description**: Window Y position on screen (-1 = centered by OS, automatically saved when closing)

**Location**:

```**Description**: Maximum number of search window expansions (3 = ±30s total coverage)  **Valid values**: Integer (-1 for auto-center, or screen coordinates)

Windows: %LOCALAPPDATA%\USDXFixGap\config.ini

Linux:   ~/.local/share/USDXFixGap\config.ini**Valid values**: Positive integer (recommended: 2-5)

```

## Editing Configuration

**Tip**: Delete `config.ini` to reset all settings to defaults.

### Performance Optimizations

---

You can manually edit `config.ini` while the application is closed. The application will validate settings on startup and use defaults for any invalid values.

## MDX Detection Tuning

#### use_fp16

### Overview

**Default**: `false`  **Location**:

The MDX detection method uses energy-based onset detection on separated vocal stems. This section explains how to tune parameters when detection is too early or too late.

**Description**: Use 16-bit floating point for GPU processing (faster but less precise)  ```

### Problem Symptoms & Solutions

**Note**: Currently disabled due to type compatibility issues  Windows: %LOCALAPPDATA%\USDXFixGap\config.ini

#### 🔴 Detection Too Late (Missing Early Vocals)

**Valid values**: `true`, `false`Linux:   ~/.local/share/USDXFixGap/config.ini

**Symptoms:**

- Blue line appears after vocals have started```

- Missing vocal intro/fade-ins

- Works better on songs with abrupt starts#### resample_hz



**Solutions** (try in order):**Default**: `0`  **Tip**: Delete `config.ini` to reset all settings to defaults.



1. **Reduce `min_voiced_duration_ms`** (default: 150ms)**Description**: Downsample audio for faster CPU processing (0 = disabled)  ment explains each setting and its valid values.

   - Try: `100ms` → `80ms` → `50ms`

   - Effect: Catches shorter vocal onsets**Valid values**: 0 (disabled), or sample rate like 32000, 22050

   - Trade-off: May detect more false positives

## [Paths]

2. **Increase `hysteresis_ms`** (default: 350ms)

   - Try: `400ms` → `450ms` → `500ms`### Confidence and Preview

   - Effect: Looks further back for onset start

   - Trade-off: May find pre-vocal noise### tmp_root



3. **Lower `onset_snr_threshold`** (default: 4.5)#### confidence_threshold**Default**: `%LOCALAPPDATA%\.tmp` (Windows) or `~/.local/share/.tmp` (Linux)

   - Try: `4.0` → `3.5` → `3.0`

   - Effect: More sensitive to quiet starts**Default**: `0.55`  **Description**: Directory for temporary files during audio processing (separated vocals, waveforms, etc.)

   - Trade-off: Detects more background noise

**Description**: Minimum SNR-based confidence score to accept detected onset  **Valid values**: Any valid directory path

4. **Lower `onset_abs_threshold`** (default: 0.012)

   - Try: `0.010` → `0.008` → `0.005`**Valid values**: Float 0.0-1.0 (recommended: 0.4-0.7, higher = stricter)

   - Effect: Catches quieter vocals

   - Trade-off: More false positives from noise### default_directory



#### 🔵 Detection Too Early (Before Actual Vocals)#### preview_pre_ms**Default**: `%LOCALAPPDATA%\samples` (Windows) or `~/.local/share/samples` (Linux)



**Symptoms:****Default**: `3000`  **Description**: Default directory shown when opening songs

- Blue line appears in instrumental intro

- Detecting breath sounds, instrumental bleed, or noise**Description**: Preview window before detected onset (3 seconds)  **Valid values**: Any valid directory path

- Works on loud vocals but fails on quiet intros

**Valid values**: Positive integer (recommended: 1000-5000)

**Solutions** (try in order):

### last_directory

1. **Increase `onset_snr_threshold`** (default: 4.5)

   - Try: `5.0` → `6.0` → `7.0`#### preview_post_ms**Default**: Empty (uses default_directory)

   - Effect: Requires stronger signal above noise

   - Trade-off: May miss quiet vocal starts**Default**: `9000`  **Description**: Last directory used in file browser - automatically updated by the application



2. **Increase `onset_abs_threshold`** (default: 0.012)**Description**: Preview window after detected onset (9 seconds)  **Valid values**: Any valid directory path

   - Try: `0.015` → `0.020` → `0.025`

   - Effect: Higher minimum energy required**Valid values**: Positive integer (recommended: 5000-15000)

   - Trade-off: Misses soft vocal intros

### models_directory

3. **Increase `noise_floor_duration_ms`** (default: 1200ms)

   - Try: `1500ms` → `2000ms` → `2500ms`## [General]**Default**: Empty (uses `%LOCALAPPDATA%\models`)

   - Effect: Better noise floor estimation

   - Trade-off: Requires longer intro silence**Description**: Directory containing AI models for vocal separation (Demucs). Leave empty to use default location.



4. **Increase `min_voiced_duration_ms`** (default: 150ms)### Runtime Artifacts and Cache**Valid values**: Any valid directory path, or empty for default

   - Try: `200ms` → `250ms` → `300ms`

   - Effect: Ignores brief noise spikes

   - Trade-off: Misses short vocal phrases

**Runtime artifacts** (separated vocals, waveform images) are automatically cached under:## [Detection]

### Parameter Reference Table

- **Windows**: `%LOCALAPPDATA%\USDXFixGap\.tmp\<hash>\<song-basename>\`

| Parameter | Default | Range | Effect |

|-----------|---------|-------|--------|- **Linux**: `~/.local/share/USDXFixGap/.tmp\<hash>\<song-basename>\`### default_detection_time

| **Energy Analysis** |

| `frame_duration_ms` | 25 | 10-50 | Window size for RMS. Smaller = finer detail but noisier |- **macOS**: `~/Library/Application Support/USDXFixGap/.tmp\<hash>\<song-basename>\`**Default**: `30`

| `hop_duration_ms` | 20 | 5-30 | Stride between frames. Smaller = better precision but slower |

| `noise_floor_duration_ms` | 1200 | 1000-3000 | How much initial silence to analyze. Longer = more accurate |**Description**: Default time window (in seconds) to analyze when detecting gaps

| **Detection Thresholds** |

| `onset_snr_threshold` | 4.5 | 3.0-10.0 | SNR multiplier. Higher = less sensitive, fewer false positives |These files are temporary and managed automatically by the application. They are not persisted outside the `.tmp` cache unless explicitly exported. The cache is automatically cleaned up based on usage patterns.**Valid values**: Positive integer (recommended: 20-60)

| `onset_abs_threshold` | 0.012 | 0.005-0.050 | Minimum RMS level. Higher = ignores quiet sounds |

| `min_voiced_duration_ms` | 150 | 50-500 | How long energy must stay high. Longer = fewer false positives |

| `hysteresis_ms` | 350 | 200-500 | Look-back window for onset start. Longer = catches earlier onsets |

### log_level### gap_tolerance

### Algorithm Overview

**Default**: `INFO`  **Default**: `500`

The detection process:

**Description**: Logging verbosity level  **Description**: Maximum acceptable gap (in milliseconds) between vocals and note timing. Gaps larger than this are flagged.

1. **Separate vocals** using Demucs (isolate vocal stem)

2. **Compute RMS energy** using sliding windows (25ms frames, 20ms hop)**Valid values**: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`**Valid values**: Positive integer (recommended: 300-1000)

3. **Estimate noise floor** from first 1200ms of audio

4. **Find sustained energy** above threshold for ≥150ms

5. **Refine onset** by looking back within hysteresis window (350ms)

6. **Find first consistent rise** using energy derivative for precise timing### GPU Acceleration Settings## [Colors]



### Testing Strategy



When tuning parameters:#### gpu_opt_in### detected_gap_color



1. **Test on diverse songs:****Default**: `false`  **Default**: `blue`

   - Abrupt vocal starts (rock, pop)

   - Gradual fade-ins (ballads)**Description**: Enable GPU acceleration for AI vocal separation (5-10x faster)  **Description**: Color for visualizing detected gap regions in the waveform

   - Quiet intros (acoustic)

   - Noisy intros (live recordings)**Valid values**: `true`, `false`**Valid values**: Color names (`red`, `blue`, `green`, etc.) or hex codes (`#FF0000`)



2. **Check log output** (set `log_level = DEBUG` in config.ini):

   ```

   Chunk analysis - Noise floor=0.001234, sigma=0.000567, max_rms=0.123456#### gpu_flavor### playback_position_color

   Thresholds - SNR_threshold=0.005123, Absolute_threshold=0.012000, Combined=0.012000

   Onset detected at 5234.5ms (RMS=0.034567, threshold=0.012000)**Default**: `cu121`  **Default**: `red`

   ```

**Description**: CUDA version for GPU Pack  **Description**: Color for the playback position indicator line

3. **Iterate on failure cases:**

   - If too late: make MORE sensitive (lower thresholds, shorter durations)**Valid values**: `cu121` (CUDA 12.1), `cu124` (CUDA 12.4)**Valid values**: Color names or hex codes

   - If too early: make LESS sensitive (higher thresholds, longer durations)



### Advanced: Per-Song Manual Adjustment

#### gpu_pack_installed_version### waveform_color

For problematic songs where auto-detection fails, you can use the GUI to manually adjust the gap value after detection completes.

**Default**: Empty  **Default**: `gray`

---

**Description**: Version of installed GPU Pack (automatically managed)  **Description**: Color for the audio waveform display

## Related Documentation

**Valid values**: Version string (e.g., `2.4.1+cu121`) or empty**Valid values**: Color names or hex codes

- [Architecture](architecture.md) - System architecture and design patterns

- [Development Guide](DEVELOPMENT.md) - Setup, testing, and code quality tools


#### gpu_pack_path### silence_periods_color

**Default**: Empty  **Default**: `105,105,105,128`

**Description**: Installation path of GPU Pack (automatically managed)  **Description**: RGBA color for silence period visualization (R,G,B,Alpha values 0-255)

**Valid values**: Valid directory path or empty**Valid values**: Four comma-separated integers (0-255)



#### gpu_last_health## [Player]

**Default**: Empty

**Description**: Last GPU health check result (automatically managed)  ### adjust_player_position_step_audio

**Valid values**: Health status string or empty**Default**: `100`

**Description**: Milliseconds to skip forward/backward when adjusting original audio position

#### gpu_last_error**Valid values**: Positive integer (recommended: 50-500)

**Default**: Empty

**Description**: Last GPU error message for diagnostics (automatically managed)  ### adjust_player_position_step_vocals

**Valid values**: Error message string or empty**Default**: `10`

**Description**: Milliseconds to skip forward/backward when fine-tuning separated vocals position

#### gpu_pack_dialog_dont_show**Valid values**: Positive integer (recommended: 5-50)

**Default**: `false`

**Description**: Suppress GPU Pack download dialog at startup  ## [Processing]

**Valid values**: `true`, `false`

### method

## [Audio]**Default**: `mdx`

**Description**: AI vocal separation method

### default_volume**Valid values**:

**Default**: `0.5`  - `mdx` - Demucs-based (recommended, fastest with GPU, best quality)

**Description**: Default playback volume (0.0 = muted, 1.0 = maximum)

**Valid values**: Float 0.0-1.0### normalization_level

**Default**: `-20`

### auto_play**Description**: Target dB level for audio normalization

**Default**: `false`  **Valid values**: Negative integer (recommended: -20 to -6)

**Description**: Automatically start playback when loading audio

**Valid values**: `true`, `false`### auto_normalize

**Default**: `false`

## [Window]**Description**: Whether to automatically normalize audio during processing

**Valid values**: `true`, `false`

### width

**Default**: `1024`  ## [mdx]

**Description**: Window width in pixels (automatically saved when closing the application)

**Valid values**: Positive integer (minimum: 600)MDX (Demucs-based) method settings for high-quality, GPU-accelerated vocal separation and onset detection.



### height> **💡 Tuning Guide**: See the [MDX Detection Tuning](#mdx-detection-tuning) section below for help with songs where detection is too early or too late.

**Default**: `768`

**Description**: Window height in pixels (automatically saved when closing the application)  ### Chunked Processing

**Valid values**: Positive integer (minimum: 600)

#### chunk_duration_ms

### x**Default**: `12000`

**Default**: `-1`  **Description**: Duration of each audio chunk for Demucs processing (12 seconds)

**Description**: Window X position on screen (-1 = centered by OS, automatically saved when closing)  **Valid values**: Positive integer (recommended: 8000-20000)

**Valid values**: Integer (-1 for auto-center, or screen coordinates)

#### chunk_overlap_ms

### y**Default**: `6000`

**Default**: `-1`  **Description**: Overlap between consecutive chunks (50% of chunk_duration_ms recommended)

**Description**: Window Y position on screen (-1 = centered by OS, automatically saved when closing)  **Valid values**: Positive integer, typically 30-70% of chunk_duration_ms

**Valid values**: Integer (-1 for auto-center, or screen coordinates)

### Energy Analysis

## [WatchMode]

#### frame_duration_ms

Watch Mode provides real-time filesystem monitoring to automatically update caches and schedule gap detection when songs are added, modified, or removed.**Default**: `25`

**Description**: Duration of each frame for RMS (energy) computation

### watch_mode_default**Valid values**: Positive integer (recommended: 20-50)

**Default**: `false`

**Description**: Automatically enable watch mode when a directory is loaded  #### hop_duration_ms

**Valid values**: `true`, `false`**Default**: `20`

**Description**: Time between consecutive frames (smaller = more precise but slower)

### watch_debounce_ms**Valid values**: Positive integer (recommended: 10-30)

**Default**: `500`

**Description**: Milliseconds to wait after the last filesystem event before processing changes. This prevents processing storms during bulk file operations (e.g., copying multiple songs).  #### noise_floor_duration_ms

**Valid values**: Positive integer (recommended: 300-1000)**Default**: `1200`

**Description**: Duration at start of audio used to estimate background noise level

### watch_ignore_patterns**Valid values**: Positive integer (recommended: 1000-2000)

**Default**: `.tmp,~,.crdownload,.part`

**Description**: Comma-separated list of file extension patterns to ignore. These are typically temporary files created by editors, browsers, or download managers.  ### Onset Detection

**Valid values**: Comma-separated string of patterns (e.g., `.tmp,.bak,~,.swp,.crdownload,.part`)

#### onset_snr_threshold

**How Watch Mode Works**:**Default**: `4.5`

- **Created**: New .txt files or folders are detected and scheduled for scanning**Description**: Signal-to-noise ratio threshold for detecting vocal onset (RMS must exceed noise + 4.5×sigma)

- **Modified**: Changes to .txt, .mp3, or .wav files automatically queue gap detection**Valid values**: Float (recommended: 3.0-10.0, higher = stricter)

- **Deleted**: Removed songs are deleted from cache and UI

- **Moved/Renamed**: Treated as delete + create for cache consistency#### onset_abs_threshold

**Default**: `0.012`

**Performance Notes**:**Description**: Absolute minimum RMS threshold (1.2% amplitude) to prevent false positives in quiet sections

- Uses OS-native filesystem watchers (Windows ReadDirectoryChangesW, macOS FSEvents, Linux inotify)**Valid values**: Float 0.0-1.0 (recommended: 0.005-0.05)

- Debouncing prevents duplicate processing during rapid file changes

- Only changed songs are processed, not the entire directory#### min_voiced_duration_ms

- At-most-one detection task per song prevents duplicates**Default**: `150`

**Description**: Minimum duration of sustained vocals to confirm onset (filters out transients)

## Editing Configuration**Valid values**: Positive integer (recommended: 100-500)



You can manually edit `config.ini` while the application is closed. The application will validate settings on startup and use defaults for any invalid values.#### hysteresis_ms

**Default**: `350`

**Location**: **Description**: Backward refinement window for precise onset timing

```**Valid values**: Positive integer (recommended: 200-500)

Windows: %LOCALAPPDATA%\USDXFixGap\config.ini

Linux:   ~/.local/share/USDXFixGap\config.ini### Expanding Search

```

#### initial_radius_ms

**Tip**: Delete `config.ini` to reset all settings to defaults.**Default**: `7500`

**Description**: Initial search window radius around expected gap (±7.5 seconds)

---**Valid values**: Positive integer (recommended: 5000-15000)



## MDX Detection Tuning#### radius_increment_ms

**Default**: `7500`

### Overview**Description**: How much to expand search window on each iteration

**Valid values**: Positive integer (recommended: 5000-10000)

The MDX detection method uses energy-based onset detection on separated vocal stems. This section explains how to tune parameters when detection is too early or too late.

#### max_expansions

### Problem Symptoms & Solutions**Default**: `3`

**Description**: Maximum number of search window expansions (3 = ±30s total coverage)

#### 🔴 Detection Too Late (Missing Early Vocals)**Valid values**: Positive integer (recommended: 2-5)



**Symptoms:**### Performance Optimizations

- Blue line appears after vocals have started

- Missing vocal intro/fade-ins#### use_fp16

- Works better on songs with abrupt starts**Default**: `false`

**Description**: Use 16-bit floating point for GPU processing (faster but less precise)

**Solutions** (try in order):**Note**: Currently disabled due to type compatibility issues

**Valid values**: `true`, `false`

1. **Reduce `min_voiced_duration_ms`** (default: 150ms)

   - Try: `100ms` → `80ms` → `50ms`#### resample_hz

   - Effect: Catches shorter vocal onsets**Default**: `0`

   - Trade-off: May detect more false positives**Description**: Downsample audio for faster CPU processing (0 = disabled)

**Valid values**: 0 (disabled), or sample rate like 32000, 22050

2. **Increase `hysteresis_ms`** (default: 350ms)

   - Try: `400ms` → `450ms` → `500ms`### Confidence and Preview

   - Effect: Looks further back for onset start

   - Trade-off: May find pre-vocal noise#### confidence_threshold

**Default**: `0.55`

3. **Lower `onset_snr_threshold`** (default: 4.5)**Description**: Minimum SNR-based confidence score to accept detected onset

   - Try: `4.0` → `3.5` → `3.0`**Valid values**: Float 0.0-1.0 (recommended: 0.4-0.7, higher = stricter)

   - Effect: More sensitive to quiet starts

   - Trade-off: Detects more background noise#### preview_pre_ms

**Default**: `3000`

4. **Lower `onset_abs_threshold`** (default: 0.012)**Description**: Preview window before detected onset (3 seconds)

   - Try: `0.010` → `0.008` → `0.005`**Valid values**: Positive integer (recommended: 1000-5000)

   - Effect: Catches quieter vocals

   - Trade-off: More false positives from noise#### preview_post_ms

**Default**: `9000`

#### 🔵 Detection Too Early (Before Actual Vocals)**Description**: Preview window after detected onset (9 seconds)

**Valid values**: Positive integer (recommended: 5000-15000)

**Symptoms:**

- Blue line appears in instrumental intro## [General]

- Detecting breath sounds, instrumental bleed, or noise

- Works on loud vocals but fails on quiet intros### Runtime Artifacts and Cache



**Solutions** (try in order):**Runtime artifacts** (separated vocals, waveform images) are automatically cached under:

- **Windows**: `%LOCALAPPDATA%\USDXFixGap\.tmp\<hash>\<song-basename>\`

1. **Increase `onset_snr_threshold`** (default: 4.5)- **Linux**: `~/.local/share/USDXFixGap/.tmp\<hash>\<song-basename>\`

   - Try: `5.0` → `6.0` → `7.0`- **macOS**: `~/Library/Application Support/USDXFixGap/.tmp\<hash>\<song-basename>\`

   - Effect: Requires stronger signal above noise

   - Trade-off: May miss quiet vocal startsThese files are temporary and managed automatically by the application. They are not persisted outside the `.tmp` cache unless explicitly exported. The cache is automatically cleaned up based on usage patterns.



2. **Increase `onset_abs_threshold`** (default: 0.012)### LogLevel

   - Try: `0.015` → `0.020` → `0.025`**Default**: `INFO`

   - Effect: Higher minimum energy required**Description**: Logging verbosity level

   - Trade-off: Misses soft vocal intros**Valid values**: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`



3. **Increase `noise_floor_duration_ms`** (default: 1200ms)### GPU Acceleration Settings

   - Try: `1500ms` → `2000ms` → `2500ms`

   - Effect: Better noise floor estimation#### GpuOptIn

   - Trade-off: Requires longer intro silence**Default**: `false`

**Description**: Enable GPU acceleration for AI vocal separation (5-10x faster)

4. **Increase `min_voiced_duration_ms`** (default: 150ms)**Valid values**: `true`, `false`

   - Try: `200ms` → `250ms` → `300ms`

   - Effect: Ignores brief noise spikes#### GpuFlavor

   - Trade-off: Misses short vocal phrases**Default**: `cu121`

**Description**: CUDA version for GPU Pack

### Parameter Reference Table**Valid values**: `cu121` (CUDA 12.1), `cu124` (CUDA 12.4)



| Parameter | Default | Range | Effect |#### GpuPackInstalledVersion

|-----------|---------|-------|--------|**Default**: Empty

| **Energy Analysis** |**Description**: Version of installed GPU Pack (automatically managed)

| `frame_duration_ms` | 25 | 10-50 | Window size for RMS. Smaller = finer detail but noisier |**Valid values**: Version string (e.g., `2.4.1+cu121`) or empty

| `hop_duration_ms` | 20 | 5-30 | Stride between frames. Smaller = better precision but slower |

| `noise_floor_duration_ms` | 1200 | 1000-3000 | How much initial silence to analyze. Longer = more accurate |#### GpuPackPath

| **Detection Thresholds** |**Default**: Empty

| `onset_snr_threshold` | 4.5 | 3.0-10.0 | SNR multiplier. Higher = less sensitive, fewer false positives |**Description**: Installation path of GPU Pack (automatically managed)

| `onset_abs_threshold` | 0.012 | 0.005-0.050 | Minimum RMS level. Higher = ignores quiet sounds |**Valid values**: Valid directory path or empty

| `min_voiced_duration_ms` | 150 | 50-500 | How long energy must stay high. Longer = fewer false positives |

| `hysteresis_ms` | 350 | 200-500 | Look-back window for onset start. Longer = catches earlier onsets |#### GpuLastHealth

**Default**: Empty

### Algorithm Overview**Description**: Last GPU health check result (automatically managed)

**Valid values**: Health status string or empty

The detection process:

#### GpuLastError

1. **Separate vocals** using Demucs (isolate vocal stem)**Default**: Empty

2. **Compute RMS energy** using sliding windows (25ms frames, 20ms hop)**Description**: Last GPU error message for diagnostics (automatically managed)

3. **Estimate noise floor** from first 1200ms of audio**Valid values**: Error message string or empty

4. **Find sustained energy** above threshold for ≥150ms

5. **Refine onset** by looking back within hysteresis window (350ms)#### GpuPackDialogDontShow

6. **Find first consistent rise** using energy derivative for precise timing**Default**: `false`

**Description**: Suppress GPU Pack download dialog at startup

### Testing Strategy**Valid values**: `true`, `false`



When tuning parameters:## [Audio]



1. **Test on diverse songs:**### DefaultVolume

   - Abrupt vocal starts (rock, pop)**Default**: `0.5`

   - Gradual fade-ins (ballads)**Description**: Default playback volume (0.0 = muted, 1.0 = maximum)

   - Quiet intros (acoustic)**Valid values**: Float 0.0-1.0

   - Noisy intros (live recordings)

### AutoPlay

2. **Check log output** (set `log_level = DEBUG` in config.ini):**Default**: `False`

   ```**Description**: Automatically start playback when loading audio

   Chunk analysis - Noise floor=0.001234, sigma=0.000567, max_rms=0.123456**Valid values**: `True`, `False`

   Thresholds - SNR_threshold=0.005123, Absolute_threshold=0.012000, Combined=0.012000

   Onset detected at 5234.5ms (RMS=0.034567, threshold=0.012000)## [WatchMode]

   ```

Watch Mode provides real-time filesystem monitoring to automatically update caches and schedule gap detection when songs are added, modified, or removed.

3. **Iterate on failure cases:**

   - If too late: make MORE sensitive (lower thresholds, shorter durations)### watch_mode_default

   - If too early: make LESS sensitive (higher thresholds, longer durations)**Default**: `false`

**Description**: Automatically enable watch mode when a directory is loaded

### Advanced: Per-Song Manual Adjustment**Valid values**: `true`, `false`



For problematic songs where auto-detection fails, you can use the GUI to manually adjust the gap value after detection completes.### watch_debounce_ms

**Default**: `500`

---**Description**: Milliseconds to wait after the last filesystem event before processing changes. This prevents processing storms during bulk file operations (e.g., copying multiple songs).

**Valid values**: Positive integer (recommended: 300-1000)

## Related Documentation

### watch_ignore_patterns

- [Architecture](architecture.md) - System architecture and design patterns**Default**: `.tmp,~,.crdownload,.part`

- [Development Guide](DEVELOPMENT.md) - Setup, testing, and code quality tools**Description**: Comma-separated list of file extension patterns to ignore. These are typically temporary files created by editors, browsers, or download managers.

**Valid values**: Comma-separated string of patterns (e.g., `.tmp,.bak,~,.swp,.crdownload,.part`)

**How Watch Mode Works**:
- **Created**: New .txt files or folders are detected and scheduled for scanning
- **Modified**: Changes to .txt, .mp3, or .wav files automatically queue gap detection
- **Deleted**: Removed songs are deleted from cache and UI
- **Moved/Renamed**: Treated as delete + create for cache consistency

**Performance Notes**:
- Uses OS-native filesystem watchers (Windows ReadDirectoryChangesW, macOS FSEvents, Linux inotify)
- Debouncing prevents duplicate processing during rapid file changes
- Only changed songs are processed, not the entire directory
- At-most-one detection task per song prevents duplicates

## Editing Configuration

You can manually edit `config.ini` while the application is closed. The application will validate settings on startup and use defaults for any invalid values.

**Location**:
```
Windows: %LOCALAPPDATA%\USDXFixGap\config.ini
Linux:   ~/.local/share/USDXFixGap/config.ini
```

**Tip**: Delete `config.ini` to reset all settings to defaults.
