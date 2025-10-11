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

Ultrastar Deluxe (USDX) Fix Gap Gui is a Python application designed to scan a directory for Ultrastar files and verify if the given GAP value matches the song or not. The GAP value defines the delay for the start of the lyric in milliseconds. A proper value is crucial for a good karaoke experience.

This semi-automatic tool helps to validate the GAP value after "downloading" songs from [USDB](https://usdb.animux.de/) using [USDB Syncer](https://github.com/bohning/usdb_syncer). Since audio files are created from YouTube videos, the GAP value sometimes does not match. Additionally, the community may not always update or set the correct GAP value for the video. This tool addresses these issues by verifying and suggesting the correct GAP values to a bunch of song files to ensure accurate synchronization.

The app uses AI-powered vocal separation (Demucs) with intelligent chunked scanning to detect silence parts and suggest correct GAP values. The suggested GAP value is marked on a waveform, allowing the user to decide which value should be chosen.

## Features

- Scans directories for Ultrastar files.
- **Multiple detection methods**: Choose between fast chunked scanning or traditional full-track separation
  - **mdx** (default): Fast Demucs-based chunked scanning with early-stop (~5-15s, GPU accelerated)
  - **spleeter**: Full stem separation for high-quality vocal isolation (~30-60s)
  - **hq_segment**: Windowed Spleeter for balanced speed/quality (~15-25s)
  - See [MDX Provider Documentation](docs/mdx-provider-implementation.md) for detailed comparison
- Detects silence parts and vocal onsets to verify the accuracy of the GAP value.
- Provides a graphical user interface (GUI) to visualize the waveform and suggested GAP values.
- Allows users to manually choose the correct GAP value if mismatched.
- Normalizes audio to ensure consistent playback levels.
- **Confidence scoring**: Each detection includes a confidence metric to assess quality
- **Preview generation**: Automatically creates focused audio previews and waveform visualizations
- **Spectral flux snap**: Refines onset detection to precise transient peaks for improved accuracy

## GUI Overview

- **Load Songs:** Button to load Ultrastar files.
- **Detect Gap:** Button to start the GAP detection process.
- **Results Table:** Displays the path, artist, title, length, BPM, original GAP, detected GAP, difference, notes, time, and status for each song.
- **Waveform Display:** Shows the waveform of the song with marked GAP values.
- **Control Buttons:** Options to keep the original GAP, save the play position, save the detected GAP, or revert to the original GAP.

## How It Works

1. **Load Songs:** Load Ultrastar songs from the specified directory.
2. **Detect Gap:** The application uses one of the following methods:
   - **MDX (Default)**: Fast chunked scanning using Demucs vocal separation
     - Processes audio in 12s chunks with 50% overlap
     - Runs Demucs separation on each chunk for clean vocal stems
     - Detects onset using adaptive energy threshold on vocals
     - **Early-stop optimization**: Stops as soon as first onset found (3-5x faster)
     - GPU accelerated for best performance
   - **Spleeter**: Full vocal separation using AI-powered stem separation
     - Separates vocals from accompaniment across entire track
     - Highest accuracy but slower processing
   - **HQ Segment**: Windowed Spleeter for balanced speed/quality
     - Separates vocals only in detection window
     - Faster than full Spleeter, maintains quality
3. **Check Gap:** Verifies if the given GAP value matches the detected vocal onset.
4. **Display Results:** Displays the results in the GUI, showing the detected GAP, difference, confidence score (SNR-based), and status (MATCH or MISMATCH).
5. **Manual Adjustment:** If a mismatch is detected, the user can view the suggested GAP on the waveform and manually choose the correct value.

For detailed information about the MDX implementation, see the [MDX Provider Documentation](docs/mdx-provider-implementation.md).

## Installation

### Run with executables (recommended):

Download and run standalone versions for Windows and Linux from [Releases](https://github.com/vtietz/usdxfixgapgui/releases).

> [`ffmpeg`](https://www.ffmpeg.org/) is required!

### Run with python

**Option 1: Using run scripts (Recommended - Automatic Setup)**

Simply use the provided run scripts that handle everything automatically:

```bash
# Windows
.\run.bat start

# Linux/macOS (same commands, just use ./run.sh instead)
./run.sh start
```

The scripts will automatically:
- Create the conda environment if it doesn't exist
- Install all dependencies
- Start the application

**Option 2: Manual Setup**

1. **Create a new conda environment (recommneded):**

    ```bash
    conda create -n usdxfixgapgui python=3.8
    ```

2. **Activate the conda environment:**

    ```bash
    conda activate usdxfixgapgui
    ```

3. **Upgrade pip and setuptools:**

    ```bash
    python -m pip install pip setuptools --upgrade
    ```

4. **Install the required dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

5. **Navigate to the `src` directory:**

    ```bash
    cd src
    ```

6. **Run the application:**

    ```bash
    python usdxfixgap.py
    ```

### Quick Start with Run Scripts (Recommended)

For convenience, you can use the provided run scripts that automatically handle conda environment setup:

```cmd
# Show available commands
.\run.bat          # Windows
./run.sh           # Linux/macOS

# Start the application
.\run.bat start

# Run tests
.\run.bat test

# Install/update requirements
.\run.bat install

# Clean cache files
.\run.bat clean

# Get environment info
.\run.bat info

# Run any Python command
.\run.bat python --version
.\run.bat pip list
```

> **Note:** Linux/macOS users can use `./run.sh` with the exact same commands as shown above.

These scripts will:
- Automatically check if the conda environment is active
- Create and activate the environment if it doesn't exist
- Install requirements automatically on first run
- Provide convenient shortcuts for common tasks

### Create executable Windows app

For creating an executable you need the PyInstaller.

```bash
pip install pyinstaller
```

Then run either `build.bat` or the following command:

```bash
pyinstaller --onefile --windowed --icon="%~dp0src\assets\usdxfixgap-icon.ico" --add-data "%~dp0src\assets;assets" "%~dp0src\usdxfixgap.py"
```

## Configuration

The configuration is managed through a `config.ini` file located in the `src` directory. This file allows you to customize various settings for the application.

### Configuration Options

#### [Paths]
- **tmp_root**: Directory where temporary files are stored (e.g., separated vocals, waveform images)
- **default_directory**: Default directory to scan for Ultrastar songs

#### [Detection]
- **default_detection_time**: Duration in seconds to analyze for gap detection
- **gap_tolerance**: Maximum allowed difference in milliseconds between detected and original gap values before flagging as a mismatch

#### [Colors]
- **detected_gap_color**: Color for highlighting the detected gap position in the waveform
- **playback_position_color**: Color for the playback position indicator
- **waveform_color**: Color for the main waveform visualization
- **silence_periods_color**: RGBA color values for highlighting silent periods (format: 105,105,105,128)

#### [Player]
- **adjust_player_position_step_audio**: Milliseconds to move when navigating audio with arrow keys
- **adjust_player_position_step_vocals**: Milliseconds to move when navigating vocals track with arrow keys

#### [Processing]
- **method**: Detection method to use (mdx, spleeter, hq_segment)
  - **mdx** (default): Fast Demucs-based chunked scanning with early-stop (GPU accelerated)
  - **spleeter**: Full stem separation (slower but highest accuracy)
  - **hq_segment**: Windowed Spleeter for balanced speed/quality
- **normalization_level**: Target level in dB for audio normalization
- **auto_normalize**: Whether to automatically normalize audio after gap detection (true/false)

#### [mdx] (for mdx method - optional, uses defaults if missing)
- **chunk_duration_ms**: Duration of each chunk in milliseconds (default: 12000)
- **chunk_overlap_ms**: Overlap between chunks for robustness (default: 6000)
- **frame_duration_ms**: Frame size for RMS computation (default: 25)
- **hop_duration_ms**: Hop size for RMS analysis (default: 10)
- **noise_floor_duration_ms**: Duration to estimate noise floor (default: 800)
- **onset_snr_threshold**: SNR threshold for onset detection (default: 2.5)
- **min_voiced_duration_ms**: Minimum sustained vocal duration (default: 180)
- **hysteresis_ms**: Hysteresis for stability (default: 80)
- **confidence_threshold**: Minimum confidence for detection (default: 0.55)
- **preview_pre_ms**: Preview window before onset (default: 3000)
- **preview_post_ms**: Preview window after onset (default: 9000)

#### [spleeter] (for spleeter method)
- **silence_detect_params**: FFmpeg parameters for silence detection

#### [hq_segment] (for hq_segment method)
- **hq_preview_pre_ms**: Preview window before gap (default: 3000)
- **hq_preview_post_ms**: Preview window after gap (default: 9000)
- **silence_detect_params**: FFmpeg parameters for silence detection (same as spleeter)

**Important**: The "extracted voices" you receive depends on the method:
- **mdx**: Returns a true **isolated vocal stem** for the entire track (Demucs separation)
- **spleeter**: Returns a true **isolated vocal stem** for the entire track (Spleeter separation)
- **hq_segment**: Returns a true **local vocal stem** for the preview window only (windowed Spleeter)

See [MDX Provider Documentation](docs/mdx-provider-implementation.md) for detailed information about the MDX method and its performance characteristics.

You can modify these settings by editing the `config.ini` file with a text editor.

## Development

This project follows a layered architecture with strict separation of concerns. For developers contributing to this project:

### **📋 Documentation**
- **[Architecture](docs/architecture.md)** - System design, layers, and component responsibilities
- **[Coding Standards](docs/coding-standards.md)** - DRY principle, SOLID principles, and clean code practices  
- **[Signal Usage](docs/signals.md)** - Signal flow patterns and communication guidelines
- **[Detection Providers](docs/detection-providers.md)** - Provider semantics, "extracted voices" behavior, and configuration guide
- **[GitHub Copilot Instructions](.github/copilot-instructions.md)** - AI assistance guidelines for consistent code generation

### **🧪 Testing**
Run tests with pytest:
```bash
# Using the run scripts (recommended)
.\run.bat test    # Windows (use ./run.sh test on Linux/macOS)

# Or directly with pytest
python -m pytest tests/ -v
```

### **🏗️ Architecture Layers**
- **Models**: Data structures and state management
- **Services**: Business logic and stateless operations  
- **Actions**: Orchestration between layers
- **UI**: User interface and presentation logic
- **Workers**: Background tasks and async operations

Before contributing, please review the documentation to understand the project's architecture and coding standards.

## Contributions

Contributions are welcome! Please fork the repository and submit a pull request with your changes.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Acknowledgements

- [USDB Syncer](https://github.com/bohning/usdb_syncer) for "downloading" USDX files from USDB
- [USDB](https://usdb.animux.de/) the awesome USD community creating and maintaining karaoke songs
- [Demucs](https://github.com/facebookresearch/demucs) by Meta Research for state-of-the-art audio separation (default method)
- [Spleeter](https://github.com/deezer/spleeter) by Deezer for audio separation (legacy method)
- [PyTorch](https://pytorch.org/) for deep learning framework
- [ffmpeg](https://github.com/FFmpeg) for audio processing and normalization
