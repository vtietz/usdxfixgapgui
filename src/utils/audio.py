import logging
import os
import stat
import time
from utils.cancellable_process import run_cancellable_process
import tempfile
from typing import List, Tuple

logger = logging.getLogger(__name__)

def milliseconds_to_str(time = 0, with_milliseconds=False):
        if time is None:
            return ""
        time = int(time)
        minutes = time // 60000
        seconds = (time % 60000) // 1000
        milliseconds = time % 1000
        if with_milliseconds:
            return f'{minutes:02d}:{seconds:02d}:{milliseconds:03d}'
        else:
            return f'{minutes:02d}:{seconds:02d}'

def get_audio_duration(audio_file, check_cancellation=None):
    """Get the duration of the audio file using ffprobe."""
    command = [
        'ffprobe', '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        audio_file
    ]

    returncode, stdout, stderr = run_cancellable_process(command, check_cancellation)
    if returncode == 0 and stdout:
        duration = stdout.strip()
        return float(duration) * 1000  # Convert to milliseconds
    else:
        logger.error(f"Error getting duration of {audio_file}: {stderr}")
        return None

def run_ffmpeg(audio_file, command, check_cancellation=None):
    if not os.path.exists(audio_file):
        raise FileNotFoundError(f"Audio file not found: {audio_file}")

    temp_dir = os.path.dirname(audio_file)
    extension = os.path.splitext(audio_file)[1]

    # Create a temp output path without keeping a handle open (Windows-friendly)
    fd, temp_file = tempfile.mkstemp(suffix=f'_processed{extension}', dir=temp_dir)
    try:
        os.close(fd)
    except Exception:
        pass

    full_command = ["ffmpeg", "-i", audio_file, "-y"] + command + [temp_file]
    returncode, stdout, stderr = run_cancellable_process(full_command, check_cancellation)

    if returncode == 0:
        # Avoid explicit delete; use atomic replace. Requires destination not open on Windows.
        # Add robust retry to handle transient sharing violations or AV scanners on Windows/network drives.
        # Media player file locks require longer retry window
        max_retries = 15
        last_exc = None
        for attempt in range(max_retries):
            try:
                # Ensure destination and temp are writable (clear read-only attribute on Windows)
                try:
                    os.chmod(audio_file, stat.S_IWRITE)
                except Exception:
                    pass
                try:
                    os.chmod(temp_file, stat.S_IWRITE)
                except Exception:
                    pass
                os.replace(temp_file, audio_file)
                last_exc = None
                break
            except PermissionError as e:
                last_exc = e
                if attempt < max_retries - 1:
                    logger.debug(f"File locked (PermissionError), retry {attempt + 1}/{max_retries}")
            except OSError as e:
                # On Windows, check specific sharing/permission errors and retry briefly
                winerr = getattr(e, "winerror", None)
                if winerr in (5, 32):  # Access denied / Sharing violation
                    last_exc = e
                    if attempt < max_retries - 1:
                        logger.debug(f"File locked (WinError {winerr}), retry {attempt + 1}/{max_retries}")
                else:
                    # Non-retryable
                    last_exc = e
                    break
            # Longer backoff for media player to release file handles (up to ~3 seconds total)
            time.sleep(0.1 * (attempt + 1))
        if last_exc is not None:
            # Best-effort cleanup of temp file before re-raising
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except Exception:
                    pass
            raise last_exc
    else:
        # Cleanup the temporary file if processing failed
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except Exception:
                pass
        raise Exception(f"Failed to apply command on {audio_file}. Error: {stderr}")

    return audio_file

def normalize_audio(audio_file, target_level=-20, check_cancellation=None):
    """Normalize the audio file to the target level. Default seetings are equal to USDB Syncher."""
    logger.debug(f"Normalizing {audio_file}...")
    command = ['-af', f'loudnorm=I={target_level}:LRA=11:TP=-2', '-ar','48000']
    return run_ffmpeg(audio_file, command, check_cancellation)

def convert_to_mp3(audio_file, check_cancellation=None):
    """Convert audio file to MP3 format."""
    mp3_file = audio_file.replace(".wav", ".mp3")
    command = ["ffmpeg", "-y", "-i", audio_file, "-q:a", "0", "-map", "a", mp3_file]
    run_cancellable_process(command, check_cancellation)
    return mp3_file

def detect_silence_periods(
        audio_file,
        silence_detect_params="silencedetect=noise=-10dB:d=0.2",
        check_cancellation=None
    ) -> List[Tuple[float, float]]:
    """Detect silence periods in the audio file."""
    if not os.path.exists(audio_file):
        raise Exception(f"Audio file not found: {audio_file}")

    command = [
        "ffmpeg", "-i", audio_file, "-af", silence_detect_params, "-f", "null", "-",
    ]
    returncode, stdout, stderr = run_cancellable_process(command, check_cancellation)

    silence_periods = []
    silence_start_ms = None
    for line in stderr.splitlines():
        if "silence_start" in line:
            try:
                silence_start_ms = float(line.split("silence_start: ")[1]) * 1000
            except Exception:
                silence_start_ms = None
        elif "silence_end" in line and silence_start_ms is not None:
            try:
                silence_end_ms = float(line.split("silence_end: ")[1].split(" ")[0]) * 1000
                # Since ffmpeg reports end after start, we pair the last start with this end
                silence_periods.append((silence_start_ms, silence_end_ms))
            except Exception:
                pass
            finally:
                # Reset start for the next segment
                silence_start_ms = None

    return silence_periods

def make_clearer_voice(audio_file, check_cancellation=None):
    filters = [
        "highpass=f=80",
        "lowpass=f=8000",
        "loudnorm=I=-6:LRA=7:TP=-2",
        "acompressor=threshold=-20dB:ratio=3:attack=5:release=50"
    ]
    command = [
        "-af",
        ",".join(filters),]
    return run_ffmpeg(audio_file, command, check_cancellation)


