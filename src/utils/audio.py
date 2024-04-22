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

def run_ffmpeg(audio_file, command, check_cancellation=None):
    if not os.path.exists(audio_file):
        raise FileNotFoundError(f"Audio file not found: {audio_file}")

    temp_dir = os.path.dirname(audio_file)
    extension = os.path.splitext(audio_file)[1]
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=f'_processed{extension}', dir=temp_dir).name

    full_command = ["ffmpeg", "-i", audio_file, "-y"] + command + [temp_file]
    returncode, stdout, stderr = run_cancellable_process(full_command, check_cancellation)

    if returncode == 0:
        if os.path.exists(audio_file):
            os.remove(audio_file)
        os.replace(temp_file, audio_file)
    else:
        os.remove(temp_file)  # Cleanup the temporary file if processing failed
        raise Exception(f"Failed to apply command on {audio_file}. Error: {stderr}")

    return audio_file

def normalize_audio(audio_file, target_level=-23, check_cancellation=None):
    """Normalize the audio file to the target level. Default seetings are equal to USDB Syncher."""
    logger.debug(f"Normalizing {audio_file}...")
    command = ['-af', f'loudnorm=I={target_level}:LRA=7:TP=-2', '-ar','48000']
    return run_ffmpeg(audio_file, command, check_cancellation)

def convert_to_mp3(audio_file, check_cancellation=None):
    """Convert audio file to MP3 format."""
    mp3_file = audio_file.replace(".wav", ".mp3")
    command = ["ffmpeg", "-y", "-i", audio_file, "-q:a", "0", "-map", "a", mp3_file]
    run_cancellable_process(command, check_cancellation)
    return mp3_file

def detect_silence_periods(
        audio_file, 
        silence_detect_params="silencedetect=noise=-30dB:d=0.5", 
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


