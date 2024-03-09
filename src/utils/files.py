import os
import json
from typing import Any, Dict

IGNORE_FILE="usdxfixgap.ignore"
INFO_FILE="usdxfixgap.info"
WAVEFORM_FILE="waveform.png"

TMP_DIR = os.path.join("..", ".tmp")

def get_song_path(txt_file):
    return os.path.dirname(txt_file)

def get_temp_path(txt_file):
    return os.path.join(TMP_DIR, os.path.splitext(os.path.basename(txt_file))[0])

def get_vocals_path(tmp_path, max_detection_time=60):
    return os.path.join(tmp_path, f"vocals_{max_detection_time}.wav")

def get_info_file_path(song_path):
    return os.path.join(song_path, INFO_FILE)

def get_txt_path(info_file):
    path = os.path.dirname(info_file)
    return os.path.join(path, f"{os.path.basename(info_file).replace(INFO_FILE, '.txt')}")

def get_waveform_path(tmp_path, audio_length=None):
    if audio_length:
        return os.path.join(tmp_path, f"waveform_{audio_length}.png")
    return os.path.join(tmp_path, WAVEFORM_FILE)

def list_txt_files(directory):
    """List all .txt files in the directory and its subdirectories."""
    txt_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".txt"):
                txt_files.append(os.path.join(root, file))
    return txt_files

def list_files(directory, endswith):
    """List all files in the directory and its subdirectories."""
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
    print(f"Deleting {folder}...")
    try:
        for root, dirs, files in os.walk(folder, topdown=False):
            for file in files:
                os.remove(os.path.join(root, file))
            for dir in dirs:
                os.rmdir(os.path.join(root, dir))
        os.rmdir(folder)
    except Exception as e:
        print(f"Error deleting {folder}: {e}")

def extract_tags(file_path):
    """Extract #GAP, #MP3, #BPM, and #RELATIVE values from the given file."""
    print(f"Extracting tags from {file_path}...")
    tags = {'TITLE': None, 'ARTIST' : None, 'GAP': None, 'MP3': None, 'BPM': None, 'RELATIVE': None}
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            for line in file:
                if line.startswith('#GAP:'):
                    value = line.split(':')[1].strip()
                    tags['GAP'] = int(value) if value else None
                elif line.startswith('#TITLE:'):
                    tags['TITLE'] = line.split(':')[1].strip()                
                elif line.startswith('#ARTIST:'):
                    tags['ARTIST'] = line.split(':')[1].strip()
                elif line.startswith('#MP3:'):
                    tags['AUDIO'] = line.split(':')[1].strip()
                elif line.startswith('#AUDIO:'):
                    tags['AUDIO'] = line.split(':')[1].strip()
                elif line.startswith('#BPM:'):
                    value = line.split(':')[1].strip()
                    tags['BPM'] = float(value) if value else None
                elif line.startswith('#RELATIVE:'):
                    value = line.split(':')[1].strip()
                    tags['RELATIVE'] = value.lower() == "yes" if value else None
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
    return tags

def update_gap(file_path, gap):
    """Update the GAP value in the given file."""
    with open(file_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()
    with open(file_path, 'w', encoding='utf-8') as file:
        for line in lines:
            if line.startswith('#GAP:'):
                file.write(f"#GAP: {gap}\n")
            else:
                file.write(line)
                

def parse_notes(file_path):
    """
    Parses notes from a given text file, starting after the first line that begins with '#'.

    :param file_path: Path to the text file containing the notes.
    :return: A list of dictionaries, each representing a note.
    """
    print(f"Parsing notes from {file_path}...")
    notes = []
    start_parsing = False  # Flag to indicate when to start parsing notes
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            for line in file:
                if line.startswith('#'):
                    start_parsing = True  # Start parsing notes after this line
                    continue
                if start_parsing and line.strip() and not line.startswith('#'):
                    parts = line.strip().split()
                    if len(parts) >= 5 and parts[0] in {':', '*', 'R', '-', 'F', 'G'}:
                        note = {
                            'NoteType': parts[0],
                            'StartBeat': int(parts[1]),
                            'Length': int(parts[2]),
                            'Pitch': int(parts[3]),
                            'Text': ' '.join(parts[4:])
                        }
                        notes.append(note)
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
    return notes


def write_info_data(file_path: str, data: Dict[str, Any]) -> None:
    """
    Writes the given data to a JSON file.

    :param file_path: Path to the JSON file where data will be written.
    :param data: A dictionary containing the data to write.
    """
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def read_info_data(file_path: str) -> Dict[str, Any]:
    """
    Reads data from a JSON file.

    :param file_path: Path to the JSON file to read.
    :return: A dictionary containing the data read from the file.
    """
    try:
        print(f"Reading info data from {file_path}...")
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"No such file or directory: '{file_path}'")
        return {}
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from '{file_path}': {e}")
        return {}
