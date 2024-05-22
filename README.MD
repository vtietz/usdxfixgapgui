# USDX Fix Gap Gui

USDX Fix Gap Gui is a Python application designed to scan a directory for Ultrastar files and verify if the given gap matches the song or not. The app uses `spleeter` to separate vocals from music, detect silence parts, and suggest a correct GAP value if a mismatch is found. The suggested GAP value is marked on a waveform, allowing the user to decide which value should be chosen.

## Features

- Scans directories for Ultrastar files.
- Uses `spleeter` to separate vocals from music.
- Detects silence parts to verify the accuracy of the GAP value.
- Provides a graphical user interface (GUI) to visualize the waveform and suggested GAP values.
- Allows users to manually choose the correct GAP value if mismatched.

## Installation

### Recommended: Setup a Conda Environment

1. **Create a new conda environment:**

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
    pip install spleeter ffmpeg-normalize ffmpeg
    ```

## Usage

1. **Navigate to the `src` directory:**

    ```bash
    cd src
    ```

2. **Run the application:**

    ```bash
    python app.py
    ```

## How It Works

1. **Load Songs:** Load Ultrastar songs from the specified directory.
2. **Detect Gap:** The application uses `spleeter` to separate vocals from music and detect silence parts.
3. **Check Gap:** Verifies if the given GAP value matches the song.
4. **Display Results:** Displays the results in the GUI, showing the detected GAP, difference, and status (MATCH or MISMATCH).
5. **Manual Adjustment:** If a mismatch is detected, the user can view the suggested GAP on the waveform and manually choose the correct value.

## GUI Overview

![Screenshot](./screenshot.png)

- **Load Songs:** Button to load Ultrastar files.
- **Detect Gap:** Button to start the GAP detection process.
- **Results Table:** Displays the path, artist, title, length, BPM, original GAP, detected GAP, difference, notes, time, and status for each song.
- **Waveform Display:** Shows the waveform of the song with marked GAP values.
- **Control Buttons:** Options to keep the original GAP, save the play position, save the detected GAP, or revert to the original GAP.

## Contributions

Contributions are welcome! Please fork the repository and submit a pull request with your changes.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Acknowledgements

- [Spleeter](https://github.com/deezer/spleeter) by Deezer for audio separation.
- [ffmpeg-normalize](https://github.com/slhck/ffmpeg-normalize) for normalizing audio files.
