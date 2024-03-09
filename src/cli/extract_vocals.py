import argparse
import os
import subprocess

class VocalExtractionError(Exception):
    pass

def extract_vocals_with_spleeter(audio_path, destination_path, max_detection_time=60, overwrite=False, check_cancellation=None):
    """Extract vocals from the audio file using Spleeter."""

    if(not os.path.exists(audio_path)):
        raise VocalExtractionError(f"Audio file not found: {audio_path}")

    filename_without_extension = os.path.splitext(os.path.basename(audio_path))[0]

    final_vocals_path = os.path.join(destination_path, filename_without_extension, f"vocals_{max_detection_time}.wav")
    spleeter_vocals_path = os.path.join(destination_path, filename_without_extension, "vocals.wav")

    print(f"Extracting vocals from {audio_path} to {final_vocals_path}...")

    if not overwrite and os.path.exists(final_vocals_path):
        print(f"Vocals already extracted to {final_vocals_path}. Use --overwrite to force extraction.")
        return final_vocals_path

    if not os.path.exists(os.path.dirname(final_vocals_path)):
        os.makedirs(os.path.dirname(final_vocals_path))

    command = ["spleeter", "separate", "-o", destination_path, "-p", "spleeter:2stems", "-d", str(max_detection_time), audio_path]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    stdout, stderr = process.communicate()
    
    # Poll process for new output until finished
    while True:
        if check_cancellation and check_cancellation():
            process.kill()
            raise VocalExtractionError("Vocal extraction cancelled.")
        if process.poll() is not None:
            break

    if not os.path.exists(spleeter_vocals_path):
        print(f"Failed to extract vocals.")
        print(f"Command: {' '.join(command)}")
        print(f"Output: {stdout}")
        print(f"Error: {stderr}")
        raise VocalExtractionError("Failed to extract vocals.")
    
    if os.path.exists(final_vocals_path):
        os.remove(final_vocals_path)
    os.rename(spleeter_vocals_path, final_vocals_path)

    accompaniment_path = os.path.join(destination_path, "accompaniment.wav")
    if os.path.exists(accompaniment_path):
        os.remove(accompaniment_path)

    print(f"Vocals extracted to {final_vocals_path}")
    return final_vocals_path

def parse_arguments():
    parser = argparse.ArgumentParser(description="Extract vocals from an audio file using Spleeter.")
    parser.add_argument("audio_path", help="Path to the audio file.")
    parser.add_argument("destination_path", help="Path to the destination folder.")
    parser.add_argument("-t", "--max_detection_time", type=int, default=60, help="Maximum detection time in seconds.")
    parser.add_argument("-o", "--overwrite", action="store_true", default=False, help="Overwrite existing vocals.")
    return parser.parse_args()

def main():
    args = parse_arguments()
    audio_path = args.audio_path
    destination_path = args.destination_path
    max_detection_time = args.max_detection_time
    overwrite = args.overwrite
    extract_vocals_with_spleeter(audio_path, destination_path, max_detection_time, overwrite)

if __name__ == "__main__":
    main()
