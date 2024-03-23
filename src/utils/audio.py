import logging
import os
import sys
from utils.cancellable_process import run_cancellable_process
import utils.files as files
import tempfile
import shutil

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
        print(f"Error getting duration of {audio_file}: {stderr}", file=sys.stderr)
        return None

def normalize_audio(audio_file, check_cancellation=None):
    print(f"Normalizing {audio_file}...")

    if(not os.path.exists(audio_file)):
        raise Exception(f"Audio file not found: {audio_file}")

    temp_dir = os.path.dirname(audio_file)
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='_normalized.wav', dir=temp_dir).name
    
    print(f"Temp dir: {temp_dir}")
    print(f"Temp file: {temp_file}")

    command = ["ffmpeg-normalize", audio_file, "-o", temp_file, "-f", "-nt", "peak", "-t", "0"]
    returncode, stdout, stderr = run_cancellable_process(command, check_cancellation)

    print(f"R: {returncode}")

    if returncode == 0:
        if(os.path.exists(audio_file)):
            os.remove(audio_file)
        os.replace(temp_file, audio_file)
    else:
        os.remove(temp_file)  # Cleanup the temporary file if normalization failed
        raise Exception(f"Failed to normalize {audio_file}. Error: {stderr}")

    print(f"Normalization completed for {audio_file}")
    return audio_file


def convert_to_mp3(audio_file, check_cancellation=None):
    """Convert audio file to MP3 format."""
    mp3_file = audio_file.replace(".wav", ".mp3")
    command = ["ffmpeg", "-y", "-i", audio_file, "-q:a", "0", "-map", "a", mp3_file]
    run_cancellable_process(command, check_cancellation)
    return mp3_file

def detect_nearest_gap(audio_path, start_position_ms, check_cancellation=None):
    # Define the silencedetect filter parameters
    silence_detect_params = "silencedetect=noise=-20dB:d=0.3"
    
    if(not os.path.exists(audio_path)):
        raise Exception(f"Audio file not found: {audio_path}")

    # Run ffmpeg to detect silence
    command = [
        "ffmpeg", "-i", audio_path, "-af", silence_detect_params, "-f", "null", "-", 
    ]
    returncode, stdout, stderr = run_cancellable_process(command, check_cancellation)
    
    # Process ffmpeg stderr output to find silence ends
    closest_silence_end_ms = None
    closest_gap_diff_ms = float('inf')
    
    for line in stderr.splitlines():
        if "silence_end" in line:
            silence_end_ms = float(line.split("silence_end: ")[1].split(" ")[0]) * 1000
            gap_diff_ms = abs(silence_end_ms - start_position_ms)
            
            if gap_diff_ms < closest_gap_diff_ms:
                closest_gap_diff_ms = gap_diff_ms
                closest_silence_end_ms = silence_end_ms
    
    return int(closest_silence_end_ms)

def extract_vocals_with_spleeter(audio_file, output_path, max_detection_time=None, check_cancellation=None):
    """Extract vocals from the audio file using Spleeter."""

    if(not os.path.exists(audio_file)):
        raise Exception(f"Audio file not found: {audio_file}")

    filename_without_extension = os.path.splitext(os.path.basename(audio_file))[0]
    spleeter_vocals_file = os.path.join(output_path, filename_without_extension, "vocals.wav")

    print(f"Extracting vocals from {audio_file} to {output_path}...")

    if not os.path.exists(os.path.dirname(output_path)):
        os.makedirs(os.path.dirname(output_path))

    command = ["spleeter", "separate", "-o", output_path, "-p", "spleeter:2stems", "-d", str(max_detection_time), audio_file]
    print(check_cancellation)
    returncode, stdout, stderr = run_cancellable_process(command, check_cancellation)

    if not os.path.exists(spleeter_vocals_file):
        raise Exception(f"Failed to extract vocals. Error: {stderr}")
    
    accompaniment_path = os.path.join(output_path, "accompaniment.wav")
    if os.path.exists(accompaniment_path):
        os.remove(accompaniment_path)

    print(f"Vocals extracted to {spleeter_vocals_file}")
    return spleeter_vocals_file


def get_vocals_file(
        audio_file, 
        temp_root, 
        destination_vocals_file, 
        max_detection_time, 
        overwrite=False, 
        check_cancellation=None
    ):

    print(f"Performing detection for {audio_file}...")
    
    if audio_file is None or os.path.exists(audio_file) is False:
        raise Exception(f"Audio file not found: {audio_file}")

    temp_path = files.get_temp_path(temp_root, audio_file)
    vocals_file = files.get_vocals_path(temp_path, max_detection_time)
    output_path = os.path.join(temp_root, "spleeter")

    if not overwrite and os.path.exists(vocals_file):
        print(f"Vocals already exists: '{vocals_file}'")
        return vocals_file

    # Extract vocals from the audio file
    vocals_file = extract_vocals_with_spleeter(audio_file, output_path, max_detection_time, check_cancellation)
    if vocals_file is None:
        raise Exception(f"Failed to extract vocals from '{audio_file}'")
    
    if os.path.exists(destination_vocals_file):
        os.remove(destination_vocals_file)
    os.makedirs(os.path.dirname(destination_vocals_file), exist_ok=True)
    os.rename(vocals_file, destination_vocals_file)

    # Remove the temporary directory
    shutil.rmtree(output_path)

    print(f"Vocals extracted to {destination_vocals_file}")

    # Normalize the extracted vocals
    vocals_file = normalize_audio(destination_vocals_file, check_cancellation)

    # Convert the normalized vocals to MP3
    vocals_file = convert_to_mp3(destination_vocals_file, check_cancellation)


    return vocals_file

def detect_gap(
        audio_file,
        tmp_root,
        gap, 
        default_detection_time, 
        overwrite=False, 
        check_cancellation=None):

    logger.info(f"Detecting gap for {audio_file}")
    if not audio_file or not os.path.exists(audio_file):
        raise FileNotFoundError(f"Audio file not found: {audio_file}")

    audio_length = get_audio_duration(audio_file)
    tmp_path = files.get_temp_path(tmp_root, audio_file)

    # Calculate the maximum detection time (s), increasing it if necessary
    detection_time = default_detection_time
    while detection_time <= gap / 1000:
        detection_time += detection_time

    logger.debug(f"Audio length: {audio_length}ms, max detection time: {detection_time}s")
    
    destination_vocals_file = files.get_vocals_path(tmp_path)
    logger.debug(f"Destination vocals file: {destination_vocals_file}")

    # detect gap, increasing the detection time if necessary
    while True:
        if os.path.exists(destination_vocals_file) and not overwrite:
            vocals_file = destination_vocals_file
        else:
            vocals_file = get_vocals_file(
                audio_file, 
                tmp_root, 
                destination_vocals_file,
                detection_time,
                overwrite,
                check_cancellation
            )
        detected_gap = detect_nearest_gap(vocals_file, gap, check_cancellation)
        if detected_gap is None:
            raise Exception(f"Failed to detect gap in {audio_file}")
        
        if detected_gap < detection_time * 1000 or detection_time * 1000 >= audio_length:
            break

        logger.info(f"Detected GAP seems not to be correct. Increasing detection time to {detection_time + detection_time}s.")
        detection_time += detection_time

    if detection_time >= audio_length and detected_gap > audio_length:
        raise Exception(f"Error: Unable to detect gap within the length of the audio: {audio_file}")

    logger.info(f"Detected: {detected_gap}m in {audio_file}")

    return detected_gap
