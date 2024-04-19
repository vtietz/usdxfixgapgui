import logging
import os
from utils.cancellable_process import run_cancellable_process
import tempfile

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

def normalize_audio(audio_file, target_level=0, check_cancellation=None):
    """Normalize the audio file to the target level. Default seetings are equal to USDB Syncher."""
    logger.debug(f"Normalizing {audio_file}...")

    if(not os.path.exists(audio_file)):
        raise Exception(f"Audio file not found: {audio_file}")

    temp_dir = os.path.dirname(audio_file)
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='_normalized.wav', dir=temp_dir).name
    
    logger.debug(f"Temp dir: {temp_dir}")
    logger.debug(f"Temp file: {temp_file}")

    command = [
        "ffmpeg-normalize", 
        audio_file, 
        "-o", temp_file, 
        "-f", 
        "-nt", "ebu", 
        "-t", str(target_level),
        "-lrt", "7",
        "-tp", "-2"]
    returncode, stdout, stderr = run_cancellable_process(command, check_cancellation)

    if returncode == 0:
        if(os.path.exists(audio_file)):
            os.remove(audio_file)
        os.replace(temp_file, audio_file)
    else:
        os.remove(temp_file)  # Cleanup the temporary file if normalization failed
        raise Exception(f"Failed to normalize {audio_file}. Error: {stderr}")

    logger.debug(f"Normalization completed for {audio_file}")
    return audio_file


def convert_to_mp3(audio_file, check_cancellation=None):
    """Convert audio file to MP3 format."""
    mp3_file = audio_file.replace(".wav", ".mp3")
    command = ["ffmpeg", "-y", "-i", audio_file, "-q:a", "0", "-map", "a", mp3_file]
    run_cancellable_process(command, check_cancellation)
    return mp3_file

def detect_silence_periods(
        audio_file, 
        silence_detect_params="silencedetect=noise=-20dB:d=0.2", 
        check_cancellation=None
    ) -> list[tuple[float, float]]:
    """Detect silence periods in the audio file."""
    if not os.path.exists(audio_file):
        raise Exception(f"Audio file not found: {audio_file}")

    command = [
        "ffmpeg", "-i", audio_file, "-af", silence_detect_params, "-f", "null", "-",
    ]
    returncode, stdout, stderr = run_cancellable_process(command, check_cancellation)

    silence_periods = []
    for line in stderr.splitlines():
        if "silence_start" in line:
            silence_start_ms = float(line.split("silence_start: ")[1]) * 1000
        if "silence_end" in line:
            silence_end_ms = float(line.split("silence_end: ")[1].split(" ")[0]) * 1000
            # Since ffmpeg reports end after start, we pair the last start with this end
            silence_periods.append((silence_start_ms, silence_end_ms))

    return silence_periods


