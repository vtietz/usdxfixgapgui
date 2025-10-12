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

- 🎯 **AI-Powered Detection** - Uses Meta's Demucs for accurate vocal onset detection
- ⚡ **GPU Acceleration** - Optional NVIDIA GPU support for 5-10x faster processing ([Setup Guide](docs/gpu-acceleration.md))
- 📊 **Visual Waveforms** - See exactly where vocals start with clear visualizations
- 🎚️ **Audio Normalization** - Automatic volume adjustment for consistent playback
- 📈 **Confidence Scoring** - Know how reliable each detection is
- 🔄 **Batch Processing** - Fix hundreds of songs automatically
- 🎵 **Preview Generation** - Listen to detected timing before applying changes
- 💾 **Smart Caching** - Re-analyze only what changed, save time on re-runs

### **Detection Methods**

Choose the detection method that fits your needs:

- **MDX** (Recommended) - Fast GPU-accelerated chunked scanning
  - ⚡ 10-30 seconds per song with GPU
  - 🎯 Smart early-stop when onset found
  - 🆕 Latest AI technology (Meta Demucs)
  - [→ Learn more](docs/mdx-provider-implementation.md)

- **Spleeter** (Legacy) - Full stem separation
  - ⚠️ Deprecated (unmaintained since 2020)
  - ~30-60 seconds per song
  - Requires TensorFlow dependencies

- **HQ Segment** (Legacy) - Windowed Spleeter
  - ⚠️ Deprecated (wrapper around unmaintained Spleeter)
  - ~15-25 seconds per song

> 💡 **Tip**: Use MDX with GPU acceleration for best performance. See [GPU Acceleration Guide](docs/gpu-acceleration.md) for setup instructions.

## 📖 User Guide

### **Basic Workflow**

1. **Load Songs**
   - Click "Load Songs" or File → Open Directory
   - Select your UltraStar songs folder
   - Songs are scanned and displayed in the table

2. **Detect Gaps**
   - Select songs (or use "Detect All")
   - Click "Detect Gap" button
   - AI analyzes audio and finds vocal onset timing
   - Results show: detected GAP, difference, confidence, status (MATCH/MISMATCH)

3. **Review Results**
   - Click any song to see its waveform
   - Green line = detected GAP
   - Red line = original GAP
   - Shaded area = confidence region
   - Listen to preview audio

4. **Apply Changes**
   - **Keep Original** - Dismiss detection, keep current value
   - **Save Detected** - Accept AI-suggested GAP
   - **Save Player Position** - Manually set GAP to current playback position
   - **Revert** - Undo changes, restore original GAP

### **Interface Overview**

| Component | Description |
|-----------|-------------|
| **Song Table** | Shows all loaded songs with detection results |
| **Waveform Display** | Visual representation of audio with GAP markers |
| **Media Player** | Preview audio and navigate to specific timestamps |
| **Task Queue** | View ongoing/queued detection tasks |
| **Log Viewer** | Troubleshoot issues and monitor processing |

### **Understanding Results**

**Status Column**:
- ✅ **MATCH** - Detected GAP matches original (within tolerance)
- ⚠️ **MISMATCH** - Significant difference detected, review recommended
- 🔄 **PROCESSING** - Detection in progress
- ❌ **ERROR** - Detection failed, check logs

**Confidence Score**:
- **0.8-1.0** - Very confident, safe to auto-apply
- **0.6-0.8** - Good, manual review recommended
- **0.4-0.6** - Uncertain, definitely review
- **<0.4** - Low confidence, consider re-detecting or manual timing

> 💡 **Tip**: Sort by "Diff" column to find songs with largest timing errors first!

## 🚀 Quick Start

### **Option 1: Download Executable (Easiest)**

1. Download the latest release for your platform:
   - [Windows Release](https://github.com/vtietz/usdxfixgapgui/releases) (.exe)
   - [Linux Release](https://github.com/vtietz/usdxfixgapgui/releases) (AppImage)

2. **Install FFmpeg** (required):
   - Windows: Download from [ffmpeg.org](https://www.ffmpeg.org/download.html) and add to PATH
   - Linux: `sudo apt install ffmpeg` or `sudo pacman -S ffmpeg`
   - macOS: `brew install ffmpeg`

3. **Run the application** and start fixing gaps!

4. **(Optional) Enable GPU Acceleration**:
   - Have an NVIDIA GPU with driver ≥531? 
   - The app will automatically offer to download GPU Pack (~1GB) for 5-10x faster processing
   - [→ GPU Acceleration Guide](docs/gpu-acceleration.md)

### **Option 2: Run from Source (For Developers)**

#### **Easy Way (Recommended)**

```bash
# Windows
.\run.bat start

# Linux/macOS
./run.sh start
```

The run script automatically handles environment setup and dependencies!

#### **Manual Setup**

<details>
<summary>Click to expand manual installation steps</summary>

1. **Create conda environment:**
   ```bash
   conda create -n usdxfixgapgui python=3.8
   conda activate usdxfixgapgui
   ```

2. **Install dependencies:**
   ```bash
   python -m pip install pip setuptools --upgrade
   pip install -r requirements.txt
   ```

3. **Run the application:**
   ```bash
   cd src
   python usdxfixgap.py
   ```

4. **(Optional) GPU Setup:**
   - See [GPU Acceleration Guide](docs/gpu-acceleration.md) for CUDA installation

</details>

### **Using the Run Scripts**

The provided run scripts (`run.bat` / `run.sh`) make development easy:

```bash
# Show available commands
.\run.bat          # Windows
./run.sh           # Linux/macOS

# Common commands
.\run.bat start    # Start the application
.\run.bat test     # Run tests
.\run.bat install  # Install/update dependencies
.\run.bat clean    # Clean cache files
.\run.bat info     # Show environment info
```

> 💡 **Note**: Run scripts automatically detect NVIDIA GPU and install CUDA support if available!

## ⚙️ Configuration

Configuration is stored in `config.ini` in your user data directory. Most settings can be adjusted through the GUI, but advanced users can edit the file directly.

### **Key Settings**

#### **Paths**
```ini
[Paths]
default_directory = C:\Users\YourName\UltraStar\songs
tmp_root = %LOCALAPPDATA%\USDXFixGap\temp
```

#### **Detection**
```ini
[Detection]
# Which detection method to use
method = mdx               # mdx, spleeter (legacy), hq_segment (legacy)

# Analysis window duration
default_detection_time = 30

# Tolerance for MATCH vs MISMATCH (milliseconds)
gap_tolerance = 150
```

#### **GPU Acceleration** (Optional)
```ini
[General]
# Enable GPU acceleration (requires GPU Pack download)
GpuOptIn = false

# CUDA flavor (auto-detected, or manually set to cu121/cu124)
GpuFlavor = cu121
```

#### **Processing**
```ini
[Processing]
# Automatic audio normalization after detection
auto_normalize = true
normalization_level = -20.0

# Method-specific settings
[mdx]
chunk_duration_ms = 12000
onset_snr_threshold = 2.5
confidence_threshold = 0.55

[spleeter]
silence_detect_params = silencedetect=noise=-30dB:d=0.2
```

### **Customizing Detection**

For fine-tuning detection behavior, see:
- [Detection Methods Guide](docs/detection-methods.md) - Compare methods and their parameters
- [MDX Provider Documentation](docs/mdx-provider-implementation.md) - Deep dive into MDX chunked scanning
- [GPU Acceleration Guide](docs/gpu-acceleration.md) - Setup and troubleshooting

> 💡 **Quick Settings Access**: File → Preferences or Edit → Settings in the GUI

## 🛠️ For Developers

Want to contribute or understand how the code works?

### **Documentation**

- **[Architecture Guide](docs/architecture.md)** - System design, layers, component responsibilities
- **[Coding Standards](docs/coding-standards.md)** - DRY principles, SOLID patterns, best practices
- **[Signal Usage Guide](docs/signals.md)** - Event communication patterns
- **[Detection Methods](docs/detection-methods.md)** - Compare detection approaches
- **[MDX Implementation](docs/mdx-provider-implementation.md)** - Deep dive into chunked scanning
- **[GPU Acceleration](docs/gpu-acceleration.md)** - GPU Pack architecture and implementation
- **[Performance Optimization](docs/performance-optimization.md)** - Qt TableView optimization patterns

### **Development Setup**

```bash
# Clone repository
git clone https://github.com/vtietz/usdxfixgapgui.git
cd usdxfixgapgui

# Install dependencies (auto-detects GPU)
.\run.bat install     # Windows
./run.sh install      # Linux/macOS

# Run tests
.\run.bat test        # 78 tests should pass

# Start development
.\run.bat start
```

### **Project Structure**

```
src/
├── actions/       # Orchestration layer (business workflow)
├── services/      # Business logic (stateless operations)
├── model/         # Data structures and state
├── ui/            # PySide6 user interface components
├── workers/       # Background tasks and async operations
├── utils/         # Shared utilities and helpers
└── app/           # Application state and DI container
```

### **Architecture Highlights**

- **Layered Architecture**: Models → Services → Actions → UI
- **Dependency Injection**: AppData container for loose coupling
- **Signal-Based Communication**: Asynchronous event-driven updates
- **Worker Queue**: Background task management with cancellation
- **Provider Pattern**: Pluggable detection methods (MDX, Spleeter, HQ Segment)

### **Testing**

All code changes should include tests:

```bash
# Run all tests
.\run.bat test

# Run specific test file
.\run.bat pytest tests/test_gap_actions_detect_gap_finished.py -v

# Check test coverage
.\run.bat pytest --cov=src tests/
```

See [Coding Standards](docs/coding-standards.md) for testing guidelines.

### **Building Executables**

```bash
# Windows
build.bat

# Linux/macOS
./build_linux.sh    # or ./build_macos.sh
```

Output in `build/usdxfixgap/` directory.

## 🤝 Contributing

Contributions are welcome! Whether it's bug reports, feature requests, or code contributions:

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/amazing-feature`
3. **Make your changes** (follow [Coding Standards](docs/coding-standards.md))
4. **Run tests**: `.\run.bat test` (all tests must pass)
5. **Commit your changes**: `git commit -m 'Add amazing feature'`
6. **Push to branch**: `git push origin feature/amazing-feature`
7. **Open a Pull Request**

### **Reporting Issues**

Found a bug? Have a suggestion?

1. Check [existing issues](https://github.com/vtietz/usdxfixgapgui/issues)
2. Create a new issue with:
   - Clear description of the problem/request
   - Steps to reproduce (for bugs)
   - Your environment (OS, Python version, GPU if relevant)
   - Relevant logs (from log viewer or `gpu_diagnostics.txt`)

## 📄 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgements

This project wouldn't be possible without these amazing open-source projects:

- **[Demucs](https://github.com/facebookresearch/demucs)** by Meta Research - State-of-the-art music source separation
- **[PyTorch](https://pytorch.org/)** - Deep learning framework powering AI detection
- **[Spleeter](https://github.com/deezer/spleeter)** by Deezer - Original vocal separation (legacy support)
- **[FFmpeg](https://github.com/FFmpeg/FFmpeg)** - Audio processing and normalization
- **[PySide6](https://www.qt.io/qt-for-python)** - Cross-platform GUI framework
- **[USDB](https://usdb.animux.de/)** - Community karaoke song database
- **[USDB Syncer](https://github.com/bohning/usdb_syncer)** - Download tool for USDB songs

Special thanks to the UltraStar Deluxe community for keeping karaoke alive! 🎤

---

**Made with ❤️ for the UltraStar community**

If this tool helped you fix your songs, consider ⭐ starring the repo!
