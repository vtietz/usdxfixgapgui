# Configuration Reference

USDXFixGap persists all user preferences in `config.ini`. The application validates every value on load and falls back to safe defaults whenever a key is missing or invalid.

## File Location & Lifecycle

- **Windows**: `%LOCALAPPDATA%\USDXFixGap\config.ini`
- **Linux**: `~/.local/share/USDXFixGap/config.ini`
- **macOS**: `~/Library/Application Support/USDXFixGap/config.ini`
- **Portable mode**: `config.ini` lives next to `usdxfixgap.exe` and uses relative paths for app-owned folders.

The file is created automatically on first launch. Delete it to reset all settings. You may edit it while the app is closed; when the UI is active the configuration is reloaded automatically before every gap-detection run if the file timestamp changes.

## Editing Tips

1. Keep backups before large edits—`config.ini.bak` files are ignored by the app.
2. Use lowercase `true`/`false` for booleans; numbers accept decimal notation.
3. Paths may be absolute or relative. On portable builds the app resolves `./something` against the executable directory.
4. Invalid values are logged at `DEBUG` level; configure `General.log_level = DEBUG` to audit parsing.

---

## Section Reference

### [Paths]

| Key | Default | Purpose |
| --- | --- | --- |
| `tmp_root` | `%LOCALAPPDATA%\.tmp` (Windows) / `~/.local/share/.tmp` (Linux/macOS) | Scratch space for separated vocals, cached waveforms, and Demucs intermediates. Use a fast SSD with several GB free. |
| `default_directory` | `%LOCALAPPDATA%\samples` or `~/.local/share/samples` | Initial folder shown when opening songs. Portable builds default to `./samples`. |
| `last_directory` | empty (falls back to `default_directory`) | Automatically updated by the file picker to restore the most recent browse location. |
| `models_directory` | empty (`%LOCALAPPDATA%\models` fallback) | Optional override for Demucs/MDX model files. Leave blank to use the managed cache. |

### [Detection]

| Key | Default | Notes |
| --- | --- | --- |
| `default_detection_time` | `20` (seconds) | Window analyzed when manual detection is triggered. Increase for long intros. |
| `gap_tolerance` | `400` (ms) | Maximum allowable difference between charted notes and detected vocals before flagging. |
| `vocal_start_window_sec` | `12` | Initial search radius around the expected gap start. |
| `vocal_window_increment_sec` | `6` | Amount added when expanding the window after each failed attempt. |
| `vocal_window_max_sec` | `36` | Hard cap for the auto-expansion process. |

### [Colors]

Colors accept named values (`red`) or hex codes (`#FF0000`). `silence_periods_color` uses `R,G,B,A` ints (0‑255).

| Key | Default | Purpose |
| --- | --- | --- |
| `detected_gap_color` | `blue` | Visualization for the detected gap marker. |
| `playback_position_color` | `red` | Live playback head overlay. |
| `waveform_color` | `gray` | Base waveform tint. |
| `silence_periods_color` | `105,105,105,128` | Semi-transparent overlay for silence zones. |

### [Player]

| Key | Default | Notes |
| --- | --- | --- |
| `adjust_player_position_step_audio` | `100` ms | Coarse skip interval for the original mix. |
| `adjust_player_position_step_vocals` | `10` ms | Fine skip interval for isolated vocals. |

### [Processing]

| Key | Default | Notes |
| --- | --- | --- |
| `method` | `mdx` | Currently only MDX/Demucs is supported. |
| `normalization_level` | `-20` dBFS | Target RMS level before analysis. |
| `auto_normalize` | `false` | Enable to force normalization during preprocessing. |

### [mdx]

These options come directly from `utils.providers.mdx.config.MdxConfig`. Adjust them only when troubleshooting detection accuracy.

| Group | Keys & Defaults | Guidance |
| --- | --- | --- |
| **Chunking** | `chunk_duration_ms=12000`, `chunk_overlap_ms=6000` | Longer chunks improve quality but require more memory. Overlap should stay at ~50% to avoid seams. |
| **Energy analysis** | `frame_duration_ms=25`, `hop_duration_ms=20`, `noise_floor_duration_ms=1200` | Frames below 20 ms add noise, while hops above 30 ms reduce precision. Extend `noise_floor_duration_ms` for long ambient intros. |
| **Thresholds** | `onset_snr_threshold=5.5`, `onset_abs_threshold=0.025`, `min_voiced_duration_ms=100`, `hysteresis_ms=350` | See [MDX Detection Tuning](#mdx-detection-tuning) for symptom-driven tweaks. |
| **Search radius** | `initial_radius_ms=7500`, `radius_increment_ms=7500`, `max_expansions=3` | Controls how far the algorithm roams from the charted gap before giving up. |
| **Performance** | `use_fp16=false`, `tf32=false`, `resample_hz=0`, `early_stop_tolerance_ms=0` | Leave `use_fp16` disabled—Demucs currently expects FP32 weights. `resample_hz` can be set to `32000` on CPU-only systems to reduce load. |
| **Confidence/preview** | `confidence_threshold=0.55`, `preview_pre_ms=3000`, `preview_post_ms=9000` | Lower the confidence threshold if detections are frequently discarded. Preview windows control how much context the UI plays before/after the gap. |

### [General]

## GPU Acceleration Settings

GPU support is controlled by the `[General]` section. See `gpu_opt_in` and the related `gpu_*` keys below.

| Key | Default | Description |
| --- | --- | --- |
| `log_level` | `INFO` | Accepts standard Python logging levels (`DEBUG`…`CRITICAL`). |
| `gpu_opt_in` | `false` | Enables GPU Pack processing (Demucs runs 5‑10× faster). |
| `gpu_flavor` | `cu121` | CUDA build of the GPU Pack. Only change if you install a different pack. |
| `gpu_pack_installed_version`, `gpu_pack_path`, `gpu_last_health`, `gpu_last_error` | managed | Diagnostic fields written by the app. Leave blank unless support asks you to override them. |
| `gpu_pack_dialog_dont_show`, `gpu_pack_dont_ask`, `splash_dont_show_health` | `false` | Skip onboarding dialogs. |
| `prefer_system_pytorch` | `false` | Advanced: force the app to use your system’s PyTorch instead of the bundled runtime. |
| `song_list_batch_size` | `25` | Number of songs fetched per batch when building the library list (tune for very large collections). |

### [Audio]

| Key | Default | Notes |
| --- | --- | --- |
| `default_volume` | `0.5` | Linear gain from 0.0 (mute) to 1.0 (full scale). |
| `auto_play` | `false` | Start playback automatically after loading stems. |

### [Window]

| Key | Default | Notes |
| --- | --- | --- |
| `width` / `height` | `1024` / `768` | Minimum 600px each. |
| `x` / `y` | `-1` | `-1` lets the OS center the window. |
| `maximized` | `false` | Persisted between sessions. |
| `main_splitter_pos` | `2,1` | Two integers describing the layout ratios of the primary splitter (song list vs waveform). |
| `second_splitter_pos` | `1,1` | Same idea for the bottom panel split. |
| `filter_text`, `filter_statuses` | empty | Stores the last library filter so the UI can restore it after restart. |

### [WatchMode]

| Key | Default | Notes |
| --- | --- | --- |
| `watch_mode_default` | `false` | Automatically enable watch mode when opening a directory. |
| `watch_debounce_ms` | `500` | Time to wait after the last filesystem event before processing (prevents storms during mass file copies). |
| `watch_ignore_patterns` | `.tmp,~,.crdownload,.part,tmp,_processed.` | Comma-separated suffix list ignored by the monitor. Add patterns such as `.bak` or `.swp` as needed. |

---

## Runtime Artifacts & Cache

Temporary processing output (Demucs stems, previews, waveform PNGs) lives under `tmp_root`:

- Windows: `%LOCALAPPDATA%\USDXFixGap\.tmp\<hash>\<song>`
- Linux: `~/.local/share/USDXFixGap/.tmp/<hash>/<song>`
- macOS: `~/Library/Application Support/USDXFixGap/.tmp/<hash>/<song>`

The cache is reference-counted and periodically cleaned. You rarely need to purge it manually; deleting the `tmp_root` folder is safe if the app is closed.

---

## MDX Detection Tuning

The MDX pipeline separates vocals, measures energy, and backtracks within a hysteresis window to find the earliest sustained rise. Use the tables below to correct systematic errors without rewriting charts manually.

### Symptoms → Fixes

**Detection too late (misses early vocals)**

1. Lower `min_voiced_duration_ms` (100 → 80 → 60 → 50). Captures short syllables but may increase noise hits.
2. Raise `hysteresis_ms` (350 → 400 → 450 → 500). Looks further back once energy is confirmed.
3. Decrease `onset_snr_threshold` (5.5 → 5.0 → 4.5). Makes the detector more sensitive to quiet leads.
4. Decrease `onset_abs_threshold` (0.025 → 0.020 → 0.018). Allows quieter RMS levels.

**Detection too early (fires during intros/noise)**

1. Increase `onset_snr_threshold` (5.5 → 6.0 → 6.5). Requires a stronger rise above the noise floor.
2. Increase `onset_abs_threshold` (0.025 → 0.028 → 0.032). Ignores very soft content.
3. Lengthen `noise_floor_duration_ms` (1200 → 1500 → 2000). Builds a better baseline for long ambient intros.
4. Increase `min_voiced_duration_ms` (100 → 150 → 200). Filters out breath noises or plosives.

Whenever you adjust thresholds, monitor the console with `log_level = DEBUG` to observe calculated RMS, sigma, and thresholds for tricky songs.

### Reference Profiles

USDXFixGap now ships with a **strict default profile** that favors avoiding false positives over catching ultra-quiet breaths. Regression tests still cover the **legacy sensitive profile** so you can opt back in when working on whispery intros.

| Profile | `noise_floor_duration_ms` | `onset_snr_threshold` | `onset_abs_threshold` | `hysteresis_ms` | When to use |
| --- | --- | --- | --- | --- | --- |
| Default (strict) | 1200 | 5.5 | 0.025 | 350 | Balanced for modern charts; ignores breaths and click bleed |
| Sensitive (legacy) | 300 | 2.5 | 0.008 | 200 | Recovers very soft syllables; expect more manual cleanup |

Switch between profiles by overriding the `[mdx]` keys in `config.ini`. Start from the default values above and only drop into the sensitive profile for songs that still fail detection after symptom-driven tweaks.

### Manual Overrides

If auto-detection cannot lock onto the correct gap, run detection once and then drag the marker inside the GUI. Manual adjustments are saved per song and survive restarts.

---

## Testing Changes Safely

1. Keep a small playlist of representative songs (abrupt rock, slow ballad, noisy live track) and rerun detection after edits.
2. Enable `log_level = DEBUG` temporarily to inspect raw detection telemetry.
3. When experimenting with MDX internals, clone `config.ini` and pass the copy via `--config` (CLI) or through the developer menu so you can revert quickly.

---

## Related Documentation

- `docs/architecture.md` – high-level system design (AppData, worker queue, signals).
- `docs/DEVELOPMENT.md` – developer tooling, lint/test commands, and coding standards.
- `docs/MEDIA_BACKENDS.md` – audio backend configuration and VLC/runtime expectations.
