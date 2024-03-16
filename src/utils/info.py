
import json
import os
from typing import Dict, Any

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
