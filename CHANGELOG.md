# Changelog

All notable changes to USDXFixGap will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### ⚠️ BREAKING CHANGES
- **Storage Location Changed**: User data now stored in platform-standard locations instead of app directory
  - **Windows**: `%LOCALAPPDATA%\USDXFixGap\` (was: `<app_directory>\`)
  - **Linux**: `~/.local/share/USDXFixGap/` (follows XDG standard)
  - **macOS**: `~/Library/Application Support/USDXFixGap/`
  - **What this means**: Your config, cache, and logs will be in a new location on first run
  - **Action needed**: None - app creates new config automatically. Old data remains in app directory if you need it.

### ✨ Added
- **Cross-Platform Storage**: Proper support for Windows, Linux, and macOS
  - Follows OS conventions (LOCALAPPDATA, XDG, Apple guidelines)
  - Respects environment variables like `XDG_DATA_HOME`
  - Portable mode fallback if platform detection fails
- **Cross-Platform GPU Pack**: GPU acceleration installer now supports Linux
  - Automatically downloads correct PyTorch wheel for your OS (Windows/Linux)
  - Linux support: Uses LD_LIBRARY_PATH for shared libraries
  - Windows support: Uses add_dll_directory for DLLs
  - Platform detection via sys.platform
- **Unified Data Directory**: All user data now in one predictable location
  - Config file (`config.ini`)
  - Song metadata cache (`cache.db`)
  - Application logs (`usdxfixgap.log`)
  - AI models (Demucs, Spleeter)
  - Temporary processing files
  - GPU Pack runtime
- **Configurable Model Paths**: Set custom locations for AI models in `config.ini`
  - Support for network shares (e.g., `\\server\shared\models\`)
  - Custom drive locations (e.g., `E:\AI_Models\`)
  - Environment variable expansion supported

### 🐛 Fixed
- **MDX Detection Crash**: Songs with vocals starting immediately (no intro) no longer fail detection
  - Now correctly returns `gap=0` instead of crashing
  - Affects songs like "101 Dalmatiner - Cruella De Vil"
  - Graceful handling of edge case
- **TorchAudio Warnings**: Suppressed harmless `MPEG_LAYER_III` warnings when loading MP3 files
  - Cleaner console output
  - No functional impact

### 🔧 Changed
- Model downloads now go to centralized location instead of hidden cache folders
  - Demucs models: `<data_dir>/models/demucs/` (~350 MB)
  - Spleeter models: `<data_dir>/models/spleeter/` (~40 MB)
  - More transparent and user-friendly

### 📚 Documentation
- Added comprehensive cross-platform storage guide
- Added file storage analysis documentation
- Added bug fixes summary
- Added session implementation notes

---

## [1.0.0] - Previous Release

### Initial Features
- AI-powered gap detection using Meta's Demucs
- GPU acceleration support
- Visual waveform generation
- Audio normalization
- Batch processing
- Multiple detection methods (MDX, Spleeter, VAD)
- Confidence scoring
- Preview generation
- Smart caching

---

## Migration Guide for Existing Users

### What Changed?

**Before:**
```
<app_directory>\
├── config.ini
├── cache.db
├── usdxfixgap.log
└── ...
```

**After (Windows):**
```
%LOCALAPPDATA%\USDXFixGap\
├── config.ini
├── cache.db
├── usdxfixgap.log
├── models\
│   ├── demucs\
│   └── spleeter\
└── gpu_runtime\
```

### Do I Need to Do Anything?

**No, the app handles it automatically:**
1. On first run after update, app creates new config in new location
2. Uses default settings (same as first install)
3. Old data remains in app directory (not deleted)

### Can I Keep My Old Settings?

**Yes, manually copy if needed:**

**Windows:**
1. Open old location: `<where_you_installed_app>\`
2. Find `config.ini`, `cache.db`
3. Copy to: `%LOCALAPPDATA%\USDXFixGap\`

**Linux:**
1. Open old location: `<where_you_installed_app>\`
2. Find `config.ini`, `cache.db`
3. Copy to: `~/.local/share/USDXFixGap/`

**macOS:**
1. Open old location: `<where_you_installed_app>\`
2. Find `config.ini`, `cache.db`
3. Copy to: `~/Library/Application Support/USDXFixGap/`

### Why This Change?

**Benefits:**
- ✅ **Multi-user friendly**: Each user has their own settings
- ✅ **Update-safe**: Your data survives app updates
- ✅ **Standard compliance**: Follows OS conventions
- ✅ **Cleaner**: Separates user data from app binaries

---

## Upgrade Instructions

### From Any Previous Version

1. **Download** the new version
2. **Extract** to your preferred location
3. **Run** the app - it will create the new data directory automatically
4. **(Optional)** Copy old `config.ini` to new location if you want to keep settings

### First-Time Installation

No changes - install as normal! The app will use the new locations from the start.

---

## Questions?

### Where is my data now?

**Windows:** Press `Win+R`, type `%LOCALAPPDATA%\USDXFixGap`, press Enter

**Linux:** Open terminal, run `cd ~/.local/share/USDXFixGap && ls`

**macOS:** Open Finder, press `Cmd+Shift+G`, paste `~/Library/Application Support/USDXFixGap`

### Can I change the model storage location?

**Yes!** Edit `config.ini`:
```ini
[Paths]
models_directory = E:\AI_Models\USDXFixGap
```

Or use a network share:
```ini
[Paths]
models_directory = \\server\shared\USDXFixGap\models
```

### Will models re-download?

**First time after update:** Yes, models will download to new location (~390 MB total)

**Solution:** Manually move models from old location to new:
- Old: `~/.cache/torch/` and `~/.cache/spleeter/`
- New: `<data_dir>/models/demucs/` and `<data_dir>/models/spleeter/`

---

[Unreleased]: https://github.com/vtietz/usdxfixgapgui/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/vtietz/usdxfixgapgui/releases/tag/v1.0.0
