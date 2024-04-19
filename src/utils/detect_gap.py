import logging
import os
import sys
from utils.cancellable_process import run_cancellable_process
import utils.files as files
import shutil
import utils.audio as audio
from utils.separate import separate_audio

logger = logging.getLogger(__name__)

def detect_nearest_gap(silence_periods, start_position_ms, check_cancellation=None):
    """Detect the nearest gap after the given start position in the audio file."""

    closest_silence_end_ms = None
    closest_gap_diff_ms = float('inf')

    for start_ms, end_ms in silence_periods:
        # Check if the start_position_ms is before the current silence period
        if start_position_ms < start_ms:
            gap_diff_ms = abs(start_ms - start_position_ms)
        else:
            gap_diff_ms = abs(end_ms - start_position_ms)

        if gap_diff_ms < closest_gap_diff_ms:
            closest_gap_diff_ms = gap_diff_ms
            closest_silence_end_ms = end_ms

    if closest_silence_end_ms is not None:
        return int(closest_silence_end_ms)
    else:
        return None

def get_vocals_file(
        audio_file, 
        temp_root, 
        destination_vocals_file, 
        duration: int = 60,
        overwrite = False, 
        check_cancellation = None
    ):

    logger.debug(f"Performing detection for {audio_file}...")
    
    if audio_file is None or os.path.exists(audio_file) is False:
        raise Exception(f"Audio file not found: {audio_file}")

    temp_path = files.get_tmp_path(temp_root, audio_file)
    vocals_file = files.get_vocals_path(temp_path)
    output_path = os.path.join(temp_root, "spleeter")

    if not overwrite and os.path.exists(vocals_file):
        logger.info(f"Vocals already exists: '{vocals_file}'")
        return vocals_file

    # Extract vocals from the audio file
    vocals_file, instrumental_file = separate_audio(
        audio_file, 
        destination_vocals_file,
        None,
        duration,
        overwrite=False, 
        check_cancellation=None
    )
    
    if vocals_file is None:
        raise Exception(f"Failed to extract vocals from '{audio_file}'")
    
    if os.path.exists(destination_vocals_file):
        os.remove(destination_vocals_file)
    os.makedirs(os.path.dirname(destination_vocals_file), exist_ok=True)
    os.rename(vocals_file, destination_vocals_file)

    # Remove the temporary directory
    shutil.rmtree(output_path)

    logger.debug(f"Vocals extracted to {destination_vocals_file}")

    vocals_file = audio.normalize_audio(destination_vocals_file, -6, check_cancellation)
    vocals_file = audio.convert_to_mp3(destination_vocals_file, check_cancellation)

    return vocals_file

def perform(
        audio_file,
        tmp_root,
        gap, 
        audio_length=None,
        default_detection_time=60, 
        overwrite=False, 
        check_cancellation=None):

    logger.info(f"Detecting gap for {audio_file}")
    if not audio_file or not os.path.exists(audio_file):
        raise FileNotFoundError(f"Audio file not found: {audio_file}")

    tmp_path = files.get_tmp_path(tmp_root, audio_file)

    if(not audio_length):
        audio_length = audio.get_audio_duration(audio_file, check_cancellation)

    # Calculate the maximum detection time (s), increasing it if necessary
    detection_time = default_detection_time
    while detection_time <= gap / 1000:
        detection_time += default_detection_time

    detection_time = detection_time + int(detection_time / 2)

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

        silence_periods = audio.detect_silence_periods(
            vocals_file, 
            check_cancellation=check_cancellation
        )
        
        detected_gap = detect_nearest_gap(silence_periods, gap, check_cancellation)
        if detected_gap is None:
            raise Exception(f"Failed to detect gap in {audio_file}")
        
        if detected_gap < detection_time * 1000 or detection_time * 1000 >= audio_length:
            break

        logger.info(f"Detected GAP seems not to be correct. Increasing detection time to {detection_time + detection_time}s.")
        detection_time += detection_time
 
        if detection_time >= audio_length and detected_gap > audio_length:
            raise Exception(f"Error: Unable to detect gap within the length of the audio: {audio_file}")

    logger.info(f"Detected GAP: {detected_gap}m in {audio_file}")

    return detected_gap, silence_periods

