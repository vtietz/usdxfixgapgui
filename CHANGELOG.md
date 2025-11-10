# Changelog

All notable changes to USDXFixGap will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

---

## [1.2.0-rc6] - 2025-11-10

### Fixed
- Fix: MDX gap detection now analyzes expected gap region (distance-based band gating replaces absolute-time gating)
- Fix: UI freezes during gap detection (media player unloads before queuing workers)
- Fix: Media player auto-unloads when song status transitions to PROCESSING

### Added
- New: Test coverage for distance gating with visualization (test_15, all 617 tests passing)
- New: Comprehensive logging for distance-gated search band traceability

---

## [1.2.0-rc5] - 2025-11-09

### Added
- New: Resizable UI panels with two dynamic splitters (song list / waveform+task/log)
- New: Flexible waveform height (100px minimum, expands with splitter)
- New: Smart startup dialog auto-checks "Don't show again" (GPU mode or CPU-only)
- New: Version display in startup dialog title (e.g., "v1.2.0-rc5")

### Changed
- Chore: Config schema added `main_splitter_pos` and `second_splitter_pos` to Window section
- Chore: Log viewer height removed 150px maximum for flexible expansion

### Fixed
- Fix: UI layout space distribution improved between panels

---

## [1.2.0-rc4] - 2025-11-08

### Added
- New: Wizard-based startup splash with multi-page experience
- New: Health check page auto-detects PyTorch, CUDA, FFmpeg with visual feedback
- New: GPU Pack offer page with smart installation prompt (auto-skips if CUDA detected)
- New: Download progress page with real-time tracking
- New: Smart page flow auto-skips pages based on system state
- New: Test detection automatically skips UI when running unit tests
- New: Close & Exit button always visible during startup
- New: Config persistence for "Don't show again" preferences
- New: Pure Palette styling uses app's global Fusion dark theme

### Removed
- **DefaultOutputPath Configuration**: Removed unused 'DefaultOutputPath' configuration option and automatic 'output' directory creation
  - Runtime artifacts (vocals, waveforms) continue to be cached under `%LOCALAPPDATA%\USDXFixGap\.tmp\`
  - Cleanup scripts (`run.bat clean`, `run.sh clean`) no longer remove a top-level 'output' folder
  - Existing config files with legacy `DefaultOutputPath` key are safely ignored (no warnings or errors)
  - See documentation for details on `.tmp` cache behavior and artifact management

---

## [2.0.0] - October 2025

### ⚠️ BREAKING CHANGES
- **Python Environment Migration (Conda → Venv)**: No longer requires Anaconda/Miniconda
  - **Now uses**: System Python 3.8+ with project-local `.venv`
  - **Setup**: Automatic on first `run.bat`/`run.sh` execution
  - **Benefits**: 6x faster bootstrap, simpler setup, better IDE integration
- **Spleeter Detection Method Removed**: Only MDX (Demucs) detection is now supported
  - **Removed**: `spleeter` and `hq_segment` detection methods
  - **Why**: Enable Python 3.12+ support, better performance, simpler codebase
  - **Impact**: Existing configs automatically use MDX with warning
- **Storage Location Changed** (from v1.1.0): User data now stored in platform-standard locations instead of app directory
  - **Windows**: `%LOCALAPPDATA%\USDXFixGap\` (was: `<app_directory>\`)
  - **Linux**: `~/.local/share/USDXFixGap/` (follows XDG standard)
  - **macOS**: `~/Library/Application Support/USDXFixGap/`
  - **What this means**: Your config, cache, and logs will be in a new location on first run
  - **Action needed**: None - app creates new config automatically. Old data remains in app directory if you need it.

### ✨ Added
- **Python 3.12+ Support**: Full compatibility with modern Python versions
  - Previously blocked by spleeter dependency (limited to Python 3.8-3.11)
  - Automatic version detection in wrapper scripts (py -3.10 → py -3.8 → python)
  - Future-proof - not tied to legacy dependencies
- **Automatic Venv Creation**: Project-local virtual environments with zero manual setup
  - Creates `.venv` on first `run.bat`/`run.sh` execution
  - Explicit executable paths (no shell activation required)
  - Deterministic execution across all platforms
- **PowerShell Syntax Support**: Added documentation for Windows PowerShell users
  - `.\run.bat` syntax required in PowerShell (not `run.bat`)
  - Updated all developer documentation with PowerShell examples
- **Cross-Platform Storage** (from v1.1.0): Proper support for Windows, Linux, and macOS
  - Follows OS conventions (LOCALAPPDATA, XDG, Apple guidelines)
  - Respects environment variables like `XDG_DATA_HOME`
  - Portable mode fallback if platform detection fails
- **Cross-Platform GPU Pack** (from v1.1.0): GPU acceleration installer now supports Linux
  - Automatically downloads correct PyTorch wheel for your OS (Windows/Linux)
  - Linux support: Uses LD_LIBRARY_PATH for shared libraries
  - Windows support: Uses add_dll_directory for DLLs
  - Platform detection via sys.platform
- **Unified Data Directory** (from v1.1.0): All user data now in one predictable location
  - Config file (`config.ini`)
  - Song metadata cache (`cache.db`)
  - Application logs (`usdxfixgap.log`)
  - AI models (Demucs only - Spleeter removed)
  - Temporary processing files
  - GPU Pack runtime
- **Configurable Model Paths** (from v1.1.0): Set custom locations for AI models in `config.ini`
  - Support for network shares (e.g., `\\server\shared\models\`)
  - Custom drive locations (e.g., `E:\AI_Models\`)
  - Environment variable expansion supported

### 🐛 Fixed
- **Python 3.12+ Compatibility**: Removed spleeter dependency blocking modern Python versions
- **Environment Setup Complexity**: 6x faster bootstrap (~10s vs 60s with conda)
- **GPU Detection**: Fixed automatic detection on fresh installations
- **Cross-Platform Consistency**: Unified wrapper behavior on Windows/Linux/macOS
- **MDX Detection Crash** (from v1.1.0): Songs with vocals starting immediately (no intro) no longer fail detection
  - Now correctly returns `gap=0` instead of crashing
  - Affects songs like "101 Dalmatiner - Cruella De Vil"
  - Graceful handling of edge case
- **TorchAudio Warnings** (from v1.1.0): Suppressed harmless `MPEG_LAYER_III` warnings when loading MP3 files
  - Cleaner console output
  - No functional impact

### ❌ Removed
- **Spleeter Dependency**: Removed `spleeter==2.4.0` from requirements.txt
  - Was blocking Python 3.12+ support
  - Slower and less accurate than MDX (Demucs)
- **Spleeter Detection Provider**: Removed full-track AI vocal separation method
- **HQ Segment Detection Provider**: Removed windowed Spleeter wrapper method
- **Conda Environment Requirement**: No longer requires Anaconda/Miniconda installation
- **Legacy Detection Provider File**: Removed unused `detection_provider.py`

### 🔧 Changed
- **Python Requirement**: Python 3.8+ (now includes 3.12+, was limited to 3.8-3.11)
- **Environment Location**: `.venv` in project root (was: conda env in `~/anaconda3/envs/`)
- **Bootstrap Speed**: ~10 seconds (was: ~60 seconds with conda)
- **Default Detection Method**: MDX only (was: MDX/Spleeter/HQ Segment)
- **Config Structure**: Removed `[spleeter]` and `[hq_segment]` sections
- **Model Downloads** (from v1.1.0): Now go to centralized location instead of hidden cache folders
  - Demucs models: `<data_dir>/models/demucs/` (~350 MB)
  - ~~Spleeter models: `<data_dir>/models/spleeter/` (~40 MB)~~ (removed)
  - More transparent and user-friendly
- **Wrapper Architecture**: Explicit executable paths, no shell activation needed
  - Windows: `.venv\Scripts\python.exe`, `.venv\Scripts\pip.exe`
  - Linux/macOS: `.venv/bin/python`, `.venv/bin/pip`

### 📚 Documentation
- Updated README.md with venv setup instructions
- Updated .github/copilot-instructions.md with venv workflow and PowerShell syntax
- Added comprehensive migration documentation (7 new files)
- Rewritten PYTHON_VERSION_COMPATIBILITY.md for Python 3.12+ support
- Updated architecture documentation to reflect MDX-only design
- Added cross-platform storage guide (from v1.1.0)
- Added file storage analysis documentation (from v1.1.0)
- Added bug fixes summary (from v1.1.0)

---

## [1.1.0] - Previous Release

### Major Features (See v1.1.0 Release Notes)
- MDX Detection Method (5-10x faster than previous methods)
- GPU Acceleration Support (Optional NVIDIA CUDA)
- Cross-Platform Storage (Windows/Linux/macOS)
- Configurable Model Storage

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
