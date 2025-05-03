from enum import Enum
import os
from model.gap_info import GapInfo, GapInfoStatus
import utils.audio as audio
import logging
from typing import List, Optional
from model.usdx_file import Note  # Add this import

logger = logging.getLogger(__name__)

class SongStatus(Enum):
    NOT_PROCESSED = 'NOT_PROCESSED'
    QUEUED = 'QUEUED'
    PROCESSING = 'PROCESSING'
    SOLVED = 'SOLVED'
    UPDATED = 'UPDATED'
    MATCH = 'MATCH'
    MISMATCH = 'MISMATCH'
    ERROR = 'ERROR'

class Song:
    
    def __init__(self, txt_file: str = "", songs_root: str = "", tmp_root: str = ""):
        # File paths
        self.txt_file = txt_file
        self.path = os.path.dirname(txt_file) if txt_file else ""
        self.relative_path = os.path.relpath(self.path, songs_root) if txt_file and songs_root else ""
        self.tmp_path = ""
        self.audio_file = ""
        self.tmp_root = tmp_root
        
        # Song metadata
        self.title = ""
        self.artist = ""
        self.audio = ""
        self.gap = 0
        self.bpm = 0
        self.start = 0
        self.is_relative = False
        self.usdb_id = None
        
        # Audio analysis data
        self.duration_ms = 0
        self.audio_waveform_file = ""
        self.vocals_file = ""
        self.vocals_waveform_file = ""
        self.vocals_duration_ms = 0
        
        # Notes data
        self.notes: Optional[List[Note]] = None
        
        # Status information
        self.gap_info = None  # Will be initialized by SongService using GapInfoService
        self.status = SongStatus.NOT_PROCESSED
        self.error_message = ""

    @property
    def duration_str(self):
        """Human-readable duration string"""
        if self.duration_ms:
            return audio.milliseconds_to_str(self.duration_ms)
        return "N/A"
    
    @property
    def normalized_str(self):
        """Return a string representation of the normalization status with level"""
        if self.gap_info and self.gap_info.is_normalized:
            if self.gap_info.normalization_level is not None:
                return f"{self.gap_info.normalization_level:.1f} dB"
            return "YES"
        return "NO"
    
    def update_status_from_gap_info(self):
        """Update song status based on gap info status"""
        if not self.gap_info:
            return
            
        info = self.gap_info
        if info.status == GapInfoStatus.MATCH:
            self.status = SongStatus.MATCH
        elif info.status == GapInfoStatus.MISMATCH:
            self.status = SongStatus.MISMATCH
        elif info.status == GapInfoStatus.ERROR:
            self.status = SongStatus.ERROR
        elif info.status == GapInfoStatus.UPDATED:
            self.status = SongStatus.UPDATED
        elif info.status == GapInfoStatus.SOLVED:
            self.status = SongStatus.SOLVED            
        else:
            self.status = SongStatus.NOT_PROCESSED
    
    def __str__(self):
        return f"Song {self.artist} - {self.title}"

    def __repr__(self):
        return f"<Song: {self.artist} - {self.title}>"
