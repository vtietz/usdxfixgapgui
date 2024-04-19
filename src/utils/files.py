import hashlib
import os
from typing import Any, Dict
import logging

IGNORE_FILE="usdxfixgap.ignore"
INFO_FILE="usdxfixgap.info"
WAVEFORM_FILE="waveform.png"


logger = logging.getLogger(__name__)

def get_song_path(txt_file):
    return os.path.dirname(txt_file)

def get_tmp_path(tmp_dir, audio_file):
    return os.path.join(tmp_dir, os.path.splitext(os.path.basename(audio_file))[0])

def get_vocals_path(tmp_path, max_detection_time=None):
    if max_detection_time is None:
        return os.path.join(tmp_path, "vocals.mp3")
    return os.path.join(tmp_path, f"vocals_{max_detection_time}.mp3")

def get_info_file_path(song_path):
    return os.path.join(song_path, INFO_FILE)

def get_txt_path(info_file):
    path = os.path.dirname(info_file)
    return os.path.join(path, f"{os.path.basename(info_file).replace(INFO_FILE, '.txt')}")

def get_waveform_path(tmp_path, type=None, length=None, extension="png"):
    file_name = "waveform"
    if type in ["audio", "vocals"]:
        file_name += f"_{type}"
    if length:
        file_name += f"_{length}"
    file_name += f".{extension}"
    return os.path.join(tmp_path, file_name)

def list_files(directory, endswith=".txt"):
    """List all .txt files in the directory and its subdirectories."""
    txt_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(endswith):
                txt_files.append(os.path.join(root, file))
    return txt_files

def ignore_file_exists(txt_file):
    ignre_file = os.path.join( os.path.dirname(txt_file), IGNORE_FILE)
    return os.path.exists(ignre_file)

def delete_folder(folder):
    """Delete the given folder and its contents."""
    if not os.path.exists(folder):
        return
    logger.debug(f"Deleting {folder}...")
    try:
        for root, dirs, files in os.walk(folder, topdown=False):
            for file in files:
                os.remove(os.path.join(root, file))
            for dir in dirs:
                os.rmdir(os.path.join(root, dir))
        os.rmdir(folder)
    except Exception as e:
        logger.error(f"Error deleting {folder}: {e}")

def generate_directory_hash(directory_path):
    """
    Generates a hash value from a directory path using SHA-256. This method provides a consistent hash value
    across different runs of the application.

    :param directory_path: The path of the directory to hash.
    :return: A hexadecimal hash value as a string.
    """
    # Encode the directory path to a byte representation required by hashlib
    directory_bytes = directory_path.encode('utf-8')
    # Use SHA-256 from hashlib and compute the hash
    hash_object = hashlib.sha256(directory_bytes)
    # Get the hexadecimal representation of the hash
    hex_hash = hash_object.hexdigest()
    short_hash = hex_hash[:8]  # take the first 8 characters for brevity
    return short_hash

def move_file(source, destination, overwrite=False):
    """
    Moves a file from source to destination.
    If overwrite is True and the destination file exists, it will be removed before moving.
    """
    # Check if the destination file exists and if overwrite is enabled
    if os.path.exists(destination) and overwrite:
        os.remove(destination)

    # Ensure the destination directory exists
    os.makedirs(os.path.dirname(destination), exist_ok=True)

    # Move the file
    os.rename(source, destination)

def rmtree(directory):
    """Recursively remove the directory and its contents."""
    if not os.path.exists(directory):
        return
    logger.debug(f"Removing directory {directory}")
    try:
        for root, dirs, files in os.walk(directory, topdown=False):
            for file in files:
                os.remove(os.path.join(root, file))
            for dir in dirs:
                os.rmdir(os.path.join(root, dir))
        os.rmdir(directory)
    except Exception as e:
        logger.error(f"Error removing directory {directory}: {e}")