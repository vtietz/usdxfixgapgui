import os
import logging
import sys  # Use current interpreter to invoke spleeter

from utils.cancellable_process import run_cancellable_process

logger = logging.getLogger(__name__)

def separate_audio(
        audio_file, 
        duration,
        output_path,
        overvrite=False,
        check_cancellation=None
    ):

    if audio_file is None or os.path.exists(audio_file) is False:
        raise Exception(f"Audio file not found: {audio_file}")
    
    # spleeter puts the audio files in a subdirectory according to the audio file name
    path_segment = os.path.splitext(os.path.basename(audio_file))[0]
    vocals_filepath = os.path.join(output_path, path_segment, "vocals.wav")    
    accompaniment_filepath = os.path.join(output_path, path_segment, "accompaniment.wav")

    logger.debug(f"Extracting vocals and instrumentals from {audio_file} to {output_path}...")

    if os.path.exists(vocals_filepath) and os.path.exists(accompaniment_filepath) and not overvrite:
        logger.debug(f"Vocals and instrumentals already extracted. Skipping.")
        return vocals_filepath, accompaniment_filepath

    if not os.path.exists(os.path.dirname(output_path)):
        os.makedirs(os.path.dirname(output_path))

    command = [
        sys.executable,
        "-m", "spleeter",
        "separate",
        "-o", output_path,
        "-p", "spleeter:2stems",
        "-d", str(duration),
        audio_file,
    ]
    logger.debug("Spleeter command: %s", ' '.join(command))
    returncode, stdout, stderr = run_cancellable_process(command, check_cancellation)

    if not os.path.exists(vocals_filepath) or not os.path.exists(accompaniment_filepath):
        raise Exception(f"Failed to separate audio. Error: {stderr}")

    logger.debug(f"Vocals extracted to {vocals_filepath}")
    logger.debug(f"Instrumental extracted to {accompaniment_filepath}")
    return vocals_filepath, accompaniment_filepath