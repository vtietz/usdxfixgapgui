from datetime import datetime
from enum import Enum
import json
import os
from enum import Enum

class SongStatus(Enum):
  NOT_PROCESSED = 'NOT_PROCESSED'
  QUEUED = 'QUEUED'
  PROCESSING = 'PROCESSING'
  SOLVED = 'SOLVED'
  UPDATED = 'UPDATED'
  MATCH = 'MATCH'
  MISMATCH = 'MISMATCH'
  ERROR = 'ERROR'

class Info:

    file_path: str = ""
    
    # the status of the song
    status: SongStatus = SongStatus.NOT_PROCESSED

    # the automatically detected gao
    detected_gap: int = 0

    # the original gap from the .txt file
    original_gap: int = 0

    # the updated gap by the user
    updated_gap: int = 0

    # the difference between the original and detected gap
    diff: int = 0

    # the time when the song was processed
    processed_time: str = ""

    def __init__(self, file_path: str):
        self.file_path = file_path

    def load(self):
        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"File not found: {self.file_path}")

        with open(self.file_path, "r") as file:
            data = json.load(file)
        
        self.status = Info.map_string_to_status(data.get("status", SongStatus.NOT_PROCESSED.value))
        self.original_gap = data.get("original_gap", 0)
        self.detected_gap = data.get("detected_gap", 0)
        self.updated_gap = data.get("updated_gap", 0)
        self.diff = data.get("diff", 0)
        self.processed_time = data.get("processed_time", "")

    def save(self):
        self.processed_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        data = {
            "status": self.status.value,
            "original_gap": self.original_gap,
            "detected_gap": self.detected_gap,
            "updated_gap": self.updated_gap,
            "diff": self.diff,
            "processed_time": self.processed_time
        }
        with open(self.file_path, "w") as file:
            json.dump(data, file, indent=4)

    def map_string_to_status(status_string):
        status_map = {
            'NOT_PROCESSED': SongStatus.NOT_PROCESSED,
            'MATCH': SongStatus.MATCH,
            'MISMATCH': SongStatus.MISMATCH,
            'ERROR': SongStatus.ERROR,
            'UPDATED': SongStatus.UPDATED,
            'QUEUED': SongStatus.QUEUED,
            'PROCESSING': SongStatus.PROCESSING,
            'SOLVED': SongStatus.SOLVED,
        }
        return status_map.get(status_string, None)
    