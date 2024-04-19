import os
import logging

from utils.cancellable_process import run_cancellable_process
from utils import files


logger = logging.getLogger(__name__)

def extract_vocals_with_spleeter(
        audio_file, 
        output_path, 
        duration, 
        check_cancellation=None
    ):

    if(not os.path.exists(audio_file)):
        raise Exception(f"Audio file not found: {audio_file}")

    logger.debug(f"Extracting vocals from {audio_file} to {output_path}...")

    if not os.path.exists(os.path.dirname(output_path)):
        os.makedirs(os.path.dirname(output_path))

    command = [
        "spleeter", 
        "separate", 
        "-o", output_path, 
        "-p", "spleeter:2stems", 
        "-d", str(duration), 
        audio_file
      ]
    returncode, stdout, stderr = run_cancellable_process(command, check_cancellation)

    spleeter_vocals_file = os.path.join(output_path, "vocals.wav")
    spleeter_accompaniment_file = os.path.join(output_path, "accompaniment.wav")

    if not os.path.exists(spleeter_vocals_file) or not os.path.exists(spleeter_accompaniment_file):
        raise Exception(f"Failed to separeate audio. Error: {stderr}")

    logger.debug(f"Vocals extracted to {spleeter_vocals_file}")
    return spleeter_vocals_file, spleeter_accompaniment_file

def separate_audio(
        audio_file, 
        final_vocals_path,
        final_instrumental_path,
        duration,
        overwrite=False, 
        check_cancellation=None
    ):

    if audio_file is None or os.path.exists(audio_file) is False:
        raise Exception(f"Audio file not found: {audio_file}")
    
    perform_separation = False

    if final_vocals_path:
        if overwrite and os.path.exists(final_vocals_path):
            perform_separation = True
        if not os.path.exists(final_vocals_path):
            perform_separation = True

    if final_instrumental_path:
        if overwrite and os.path.exists(final_instrumental_path):
            perform_separation = True
        if not os.path.exists(final_instrumental_path):
            perform_separation = True

    if not perform_separation:
        return final_vocals_path, final_instrumental_path

    tmp_path = os.path.join(".spleeter", os.path.basename(audio_file))

    # Extract vocals from the audio file
    vocals_file, instrumental_file = extract_vocals_with_spleeter(
        audio_file, 
        tmp_path, 
        duration, 
        check_cancellation
    )

    if vocals_file is None or instrumental_file is None:
        raise Exception(f"Failed to extract vocals and/or instruementals from '{audio_file}'")
    
    if(final_vocals_path and final_instrumental_path):
        files.move_file(vocals_file, final_vocals_path)
    
    if(instrumental_file and final_instrumental_path):
        files.move_file(instrumental_file, final_instrumental_path)
        
    files.rmtree(tmp_path)

    logger.debug(f"Audio file {audio_file} separated to {final_instrumental_path} and {final_instrumental_path}")

    return final_vocals_path, final_instrumental_path
