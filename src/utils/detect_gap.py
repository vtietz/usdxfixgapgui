import logging
import os
import utils.files as files
import shutil
import utils.audio as audio
from utils.separate import separate_audio

logger = logging.getLogger(__name__)

def detect_nearest_gap(silence_periods: list[tuple[float, float]], start_position_ms: float) -> int:
    """Detect the nearest gap before or after the given start position in the audio file."""
    logger.debug(f"Detecting nearest gap relative to {start_position_ms}ms")
    logger.debug(f"Silence periods: {silence_periods}")

    closest_gap_ms = None
    closest_gap_diff_ms = float('inf')  # Initialize with infinity

    # Evaluate both the start and end of each silence period
    for start_ms, end_ms in silence_periods:
        # Calculate the difference from start_position_ms to the start and end of the silence period
        start_diff = abs(start_ms - start_position_ms)
        end_diff = abs(end_ms - start_position_ms)

        # Determine which is closer: the start or the end of the silence period
        if start_diff < closest_gap_diff_ms:
            closest_gap_diff_ms = start_diff
            closest_gap_ms = start_ms

        if end_diff < closest_gap_diff_ms:
            closest_gap_diff_ms = end_diff
            closest_gap_ms = end_ms

    # If a closest gap was found, return its position rounded to the nearest integer
    if closest_gap_ms is not None:
        return int(closest_gap_ms)
    else:
        return None

def get_vocals_file(
        audio_file, 
        temp_root, 
        destination_vocals_filepath, 
        duration: int = 60,
        overwrite = False, 
        check_cancellation = None
    ):

    logger.debug(f"Performing detection for {audio_file}...")
    
    if audio_file is None or os.path.exists(audio_file) is False:
        raise Exception(f"Audio file not found: {audio_file}")

    if not overwrite and os.path.exists(destination_vocals_filepath):
        logger.debug(f"Vocals file already exists: {destination_vocals_filepath}")
        return destination_vocals_filepath

    output_path = os.path.join(temp_root, "spleeter")
    vocals_file, instrumental_file = separate_audio(
        audio_file, 
        duration,
        output_path,
        overwrite, 
        check_cancellation=None
    )
    
    if vocals_file is None:
        raise Exception(f"Failed to extract vocals from '{audio_file}'")

    #vocals_file = audio.normalize_audio(vocals_file, -6, check_cancellation)
    vocals_file = audio.make_clearer_voice(vocals_file, check_cancellation)
    vocals_file = audio.convert_to_mp3(vocals_file, check_cancellation)

    if(vocals_file and destination_vocals_filepath):
        files.move_file(vocals_file, destination_vocals_filepath)
    
    files.rmtree(output_path)

    return destination_vocals_filepath

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
        
        detected_gap = detect_nearest_gap(silence_periods, gap)
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

