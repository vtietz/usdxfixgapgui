from datetime import datetime
from enum import Enum
from utils import files
from enum import Enum
import json
import os
import aiofiles
import logging
from typing import List, Tuple 

logger = logging.getLogger(__name__)

class GapInfoStatus(Enum):
    NOT_PROCESSED = 'NOT_PROCESSED'
    MATCH = 'MATCH'
    MISMATCH = 'MISMATCH'
    SOLVED = 'SOLVED'
    UPDATED = 'UPDATED'
    ERROR = 'ERROR'

class GapInfo:

    file_path: str = ""
    
    # the status of the song
    status: str = "NOT_PROCESSED"

    # the automatically detected gao
    detected_gap: int = 0

    # the original gap from the .txt file
    original_gap: int = 0

    # the updated gap by the user
    updated_gap: int = 0

    # the difference between the original and detected gap
    diff: int = 0

    # the duration of the song
    duration: int = 0
    
    # the percentage of notes not in silence
    notes_overlap: float = 0

    # the time when the song was processed
    processed_time: str = ""

    # the silence periods in the vocals file
    silence_periods: List[Tuple[float, float]]

    def __init__(self, song_path: str):
        self.file_path = files.get_info_file_path(song_path)

    async def load(self):
        logger.debug(f"Try to load {self.file_path}")
        self.status = GapInfoStatus.NOT_PROCESSED
        self.original_gap = 0
        self.detected_gap = 0
        self.updated_gap = 0
        self.diff = 0
        self.duration = 0
        self.notes_overlap = 0
        self.processed_time = ""
        self.silence_periods = []
        if os.path.exists(self.file_path):
            try:
                async with aiofiles.open(self.file_path, "r", encoding="utf-8") as file:
                    content = await file.read()  # Read the content asynchronously
                    data = json.loads(content)  # Parse the JSON from the string
                self.status = GapInfo.map_string_to_status(data.get("status", "NOT_PROCESSED"))
                self.original_gap = data.get("original_gap", 0)
                self.detected_gap = data.get("detected_gap", 0)
                self.updated_gap = data.get("updated_gap", 0)
                self.diff = data.get("diff", 0)
                self.duration = data.get("duration", 0)
                self.notes_overlap = data.get("notes_overlap", 0)
                self.processed_time = data.get("processed_time", "")
                self.silence_periods = data.get("silence_periods", [])
            except Exception as e:
                logger.error(f"Error loading gap info: {e}")

    async def save(self):
        logger.debug(f"Saving{self.file_path}")
        self.processed_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        data = {
            "status": self.status.value,
            "original_gap": self.original_gap,
            "detected_gap": self.detected_gap,
            "updated_gap": self.updated_gap,
            "diff": self.diff,
            "duration": self.duration,
            "notes_overlap": self.notes_overlap,
            "processed_time": self.processed_time,
            "silence_periods": self.silence_periods
        }
        async with aiofiles.open(self.file_path, "w", encoding="utf-8") as file:
            await file.write(json.dumps(data, indent=4))  # Convert data to JSON string and write asynchronously


    def map_string_to_status(status_string) -> GapInfoStatus:
        status_map = {
            'NOT_PROCESSED': GapInfoStatus.NOT_PROCESSED,
            'MATCH': GapInfoStatus.MATCH,
            'MISMATCH': GapInfoStatus.MISMATCH,
            'ERROR': GapInfoStatus.ERROR,
            'UPDATED': GapInfoStatus.UPDATED,
            'SOLVED': GapInfoStatus.SOLVED,
        }
        return status_map.get(status_string, None)
    
