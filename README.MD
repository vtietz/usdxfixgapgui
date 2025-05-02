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

The app uses `spleeter` to separate vocals from music with help of AI, detect silence parts, and suggest a correct GAP value if a mismatch is found. The suggested GAP value is marked on a waveform, allowing the user to decide which value should be chosen.

## Features

- Scans directories for Ultrastar files.
- Uses `spleeter` to separate vocals from music.
- Detects silence parts to verify the accuracy of the GAP value.
- Provides a graphical user interface (GUI) to visualize the waveform and suggested GAP values.
- Allows users to manually choose the correct GAP value if mismatched.
- Normalizes audio to ensure consistent playback levels.

## GUI Overview

- **Load Songs:** Button to load Ultrastar files.
- **Detect Gap:** Button to start the GAP detection process.
- **Results Table:** Displays the path, artist, title, length, BPM, original GAP, detected GAP, difference, notes, time, and status for each song.
- **Waveform Display:** Shows the waveform of the song with marked GAP values.
- **Control Buttons:** Options to keep the original GAP, save the play position, save the detected GAP, or revert to the original GAP.

## How It Works

1. **Load Songs:** Load Ultrastar songs from the specified directory.
2. **Detect Gap:** The application uses `spleeter` to separate vocals from music and detect silence parts.
3. **Check Gap:** Verifies if the given GAP value matches the song.
4. **Display Results:** Displays the results in the GUI, showing the detected GAP, difference, and status (MATCH or MISMATCH).
5. **Manual Adjustment:** If a mismatch is detected, the user can view the suggested GAP on the waveform and manually choose the correct value.

## Installation

### Run with executables (recommended):

Download and run standalone versions for Windows and Linux from [Releases](https://github.com/vtietz/usdxfixgapgui/releases).

> [`ffmpeg`](https://www.ffmpeg.org/) is required!

### Run with python

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
- **spleeter**: Enable/disable vocal isolation using Spleeter (true/false)
- **silence_detect_params**: FFmpeg parameters for silence detection
- **normalization_level**: Target level in dB for audio normalization
- **auto_normalize**: Whether to automatically normalize audio after gap detection (true/false)

You can modify these settings by editing the `config.ini` file with a text editor.

## Contributions

Contributions are welcome! Please fork the repository and submit a pull request with your changes.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Acknowledgements

- [USDB Syncer](https://github.com/bohning/usdb_syncer) for "downloading" USDX files from USDB
- [USDB](https://usdb.animux.de/) the awesome USD community creating and maintaining karaoke songs
- [Spleeter](https://github.com/deezer/spleeter) by Deezer for audio separation.
- [ffmpeg](https://github.com/FFmpeg) for detecting silence parts and normalization.
