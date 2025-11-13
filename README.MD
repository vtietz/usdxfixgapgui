<p align="center">
    <img width="150" src="./src/assets/usdxfixgap-icon.png" alt="Logo">
    <h3 align="center">Effortlessly synchronize your Ultrastar Deluxe songs with AI-powered GAP detection and correction for the ultimate karaoke experience!</h3>
    <br/>
</p>
<p align="center">
    <img style="width:80%;" src="./screenshot.png" alt="Screenshot">
    <br/>
</p>

# Ultrastar Deluxe (USDX) Fix Gap Gui

**Automatically fix timing issues in your UltraStar karaoke songs using AI-powered gap detection!**

Ultrastar Deluxe (USDX) Fix Gap Gui helps you quickly verify and correct GAP values in your UltraStar song collection. The GAP value defines when lyrics start (in milliseconds) - getting it right is crucial for a great karaoke experience.

### **Why do you need this?**

When downloading songs from [USDB](https://usdb.animux.de/) using [USDB Syncer](https://github.com/bohning/usdb_syncer), audio files are created from YouTube videos. This can cause timing mismatches:
- YouTube videos may have intro variations
- Community-set GAP values may not match your downloaded video
- Manual verification of hundreds of songs is time-consuming

**This tool solves these problems automatically** using AI to detect when vocals actually start, then suggests the correct GAP value with visual confirmation.

### **How it works**

1. **Load your song collection** - point to your UltraStar songs folder
2. **Detect gaps** - AI analyzes audio and finds vocal onset timing
3. **Review results** - see waveform visualization with detected vs. original GAP
4. **Apply fixes** - accept suggested values or fine-tune manually

The app uses state-of-the-art AI vocal separation (Meta's Demucs) with smart chunked processing to find the exact moment vocals start.

## ✨ Key Features

- 🎯 **AI-Powered Detection** - Uses Meta's Demucs (MDX) for accurate vocal onset detection
- ⚡ **GPU Acceleration** - Optional NVIDIA GPU support for 5-10x faster processing
- 🧙 **Smart Startup Wizard** - Guided setup with automatic system health checks
- 📊 **Visual Waveforms** - See exactly where vocals start with clear visualizations
- 🎚️ **Audio Normalization** - Automatic volume adjustment for consistent playback
- 🔄 **Batch Processing** - Fix hundreds of songs automatically
- 💾 **Smart Caching** - Re-analyze only what changed, save time on re-runs
- 👁️ **Watch Mode** - Automatically monitor your song directory for changes

## 📖 User Guide

### **Basic Workflow**

1. **Load Songs**
   - Click "Load Songs" or File → Open Directory
   - Select your UltraStar songs folder
   - Songs appear in the table with their current GAP values

2. **Detect Gaps**
   - Select songs to analyze (or use "Detect All")
   - Click "Detect Gap" button
   - AI analyzes audio and finds vocal onset timing
   - Results show: detected GAP, difference (ms), status

3. **Review Results**
   - Click any song to see its waveform visualization
   - **Green line** = AI-detected GAP (where vocals actually start)
   - **Red line** = original GAP (current value in .txt file)
   - Listen to preview audio to verify timing

4. **Apply Changes**
   - **Save Detected** - Accept AI-suggested GAP
   - **Keep Original** - Dismiss detection, keep current value
   - **Save Player Position** - Manually set GAP to playback position
   - **Revert** - Undo changes, restore original GAP

### **Understanding Results**

**Status Column**:
- ✅ **MATCH** - Detected GAP matches original (within 500ms tolerance)
- ⚠️ **MISMATCH** - Significant difference detected, review recommended
- 🔄 **PROCESSING** - Detection in progress
- ❌ **ERROR** - Detection failed, check logs

**Diff Column**: Shows timing difference in milliseconds
- Positive value = detected GAP is later than original
- Negative value = detected GAP is earlier than original
- Large differences (>1000ms) usually indicate wrong original GAP

> 💡 **Tip**: Sort by "Diff" column to find songs with largest timing errors first!

### **Watch Mode**

Watch Mode automatically monitors your song directory for changes:

1. Load your song directory normally
2. Click "Watch Mode" button to enable
3. App automatically detects:
   - **New songs** → scanned and added
   - **Modified files** → gap detection queued
   - **Deleted songs** → removed from cache
4. Click "Watch Mode" again to disable

**Configuration** (`config.ini`):
```ini
[WatchMode]
watch_mode_default = false         # Auto-enable on directory load
watch_debounce_ms = 500            # Wait time after changes before processing
```

## 🚀 Quick Start

### **Download & Install**

1. **Download** the latest release for your platform:
   - [**Windows**](https://github.com/vtietz/usdxfixgapgui/releases) - Fully tested and supported
   - [Linux/macOS](https://github.com/vtietz/usdxfixgapgui/releases) - Experimental builds

2. **Install FFmpeg** (required for audio processing):
   - **Windows**: Download from [ffmpeg.org](https://www.ffmpeg.org/download.html) and add to PATH
   - **Linux**: `sudo apt install ffmpeg` or `sudo pacman -S ffmpeg`
   - **macOS**: `brew install ffmpeg`

   > **Note**: VLC runtime is automatically included in Windows builds for better audio stability

3. **Run the application**:
   - Windows: Extract and run `usdxfixgap.exe`
   - Linux: Make executable (`chmod +x`) and run the AppImage
   - First launch shows health check - verifying PyTorch, GPU, and FFmpeg
   - App starts automatically when ready

4. **(Optional) Enable GPU Acceleration**:
   - Have an NVIDIA GPU with driver ≥531?
   - App will offer to download GPU Pack (~1GB) for 5-10x faster processing
   - See [GPU Setup Guide](docs/configuration.md#gpu-acceleration-settings)

> **Note**: Windows Defender may show a false positive (common with PyInstaller). The executable is safe - source code is open for inspection.

## ⚙️ Configuration

Configuration file: `%LOCALAPPDATA%\USDXFixGap\config.ini` (Windows) or `~/.local/share/USDXFixGap/config.ini` (Linux)

Most settings can be adjusted through **File → Preferences** in the GUI.

### **Common Settings**

**Enable GPU Acceleration**:
```ini
[General]
gpu_opt_in = true
```

**Adjust Gap Tolerance** (default: 500ms):
```ini
[Detection]
gap_tolerance = 500    # Milliseconds
```

**Change Detection Method**:
```ini
[Processing]
method = mdx    # Recommended: mdx, spleeter (legacy), hq_segment (legacy)
```

### **Advanced: Environment Variables**

For portable deployments or power users:

```bash
# Override GPU Pack location
set USDXFIXGAP_GPU_PACK_DIR=E:\GPUPacks\torch-2.4.1-cu121

# Override config directory
set USDXFIXGAP_DATA_DIR=D:\MyCustomConfig

# Force CPU mode (disable GPU)
set USDXFIXGAP_FORCE_CPU=1
```

**Portable Mode**: Onedir builds (folder with `_internal/` subdirectory) automatically use app directory for all files instead of user profile.

See [Configuration Reference](docs/configuration.md) for all settings.

## 🛠️ For Developers

**Documentation**:
- [Development Guide](docs/DEVELOPMENT.md) - Setup, testing, building
- [Architecture Guide](docs/architecture.md) - System design, patterns
- [Coding Standards](docs/coding-standards.md) - Code quality guidelines
- [Configuration Reference](docs/configuration.md) - Complete settings documentation

**Quick Start**:
```bash
git clone https://github.com/vtietz/usdxfixgapgui.git
cd usdxfixgapgui
.\run.bat install     # Windows
./run.sh install      # Linux/macOS
.\run.bat setup-vlc   # Windows only: setup VLC for development (optional, recommended)
.\run.bat test        # Run tests
.\run.bat start       # Start development
```

**Dependency Profiles**:

| Profile | File | Purpose | PyTorch Variant |
|---------|------|---------|-----------------|
| Runtime (dev/portable CPU default) | `requirements.txt` | Flexible versions + CPU torch for universal run | Ranges (CPU) |
| Shared base | `requirements-base.txt` | Common non-PyTorch libs (librosa, demucs, PySide6, etc.) | n/a |
| Windows build | `requirements-build.txt` | Pinned for reproducible PyInstaller build, CPU torch | torch==2.4.1 / torchaudio==2.4.1 |
| Linux build | `requirements-build-linux.txt` | Pinned + `+cpu` suffix to avoid CUDA wheels | torch==2.4.1+cpu / torchaudio==2.4.1+cpu |
| macOS build | `requirements-build-macos.txt` | Pinned standard (includes MPS acceleration) | torch==2.4.1 / torchaudio==2.4.1 |

**GPU Development (Optional)**:
Install CUDA-enabled PyTorch into the venv (does not affect builds):
```bash
run.bat install --gpu        # Windows
./run.sh install --gpu       # Linux/macOS (if supported)
```
The executable distributes CPU-only PyTorch. End users opt-in to the GPU Pack through the app UI or `--setup-gpu` CLI.


**Project Structure**:
```
src/
├── actions/       # Business workflow orchestration
├── services/      # Stateless business logic
├── model/         # Data structures and state
├── ui/            # PySide6 interface components
├── workers/       # Background tasks
├── utils/         # Shared utilities
└── app/           # Application state (DI container)
```

See [Development Guide](docs/DEVELOPMENT.md) for complete details.

## 📄 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgements

Built with these amazing open-source projects:
- [**Demucs**](https://github.com/facebookresearch/demucs) by Meta Research - AI music source separation
- [**PyTorch**](https://pytorch.org/) - Deep learning framework
- [**FFmpeg**](https://github.com/FFmpeg/FFmpeg) - Audio processing
- [**PySide6**](https://www.qt.io/qt-for-python) - Cross-platform GUI
- [**USDB**](https://usdb.animux.de/) - Community karaoke database
- [**USDB Syncer**](https://github.com/bohning/usdb_syncer) - Song download tool

Special thanks to the UltraStar Deluxe community! 🎤

---

**Made with ❤️ for the UltraStar community**

⭐ Star the repo if this tool helped you!
