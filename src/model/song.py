from enum import Enum
import os
from model.gap_info import GapInfo, GapInfoStatus
import utils.files as files
import utils.audio as audio
from utils.usdx_file_cached import USDXFileCached
import logging

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

    txt_file: str = ""

    path: str = ""
    relative_path: str = ""
    tmp_path: str = ""
    audio_file: str = ""
    
    title: str = ""
    artist: str = ""
    audio: str = "" 
    gap: int = 0
    bpm: int = 0
    start: int = 0
    is_relative: bool = False

    usdb_id: str = None
    
    duration_ms: int = 0

    audio_waveform_file: str = ""
    vocals_file: str = ""
    vocals_waveform_file: str = ""
    vocals_duration_ms: int = 0

    gap_info: GapInfo = None
    
    status: SongStatus = SongStatus.NOT_PROCESSED

    notes: list = []

    error_message: str = ""

    def __init__(self, txt_file: str, songs_root:str, tmp_root: str):
        self.txt_file = txt_file
        self.tmp_root = tmp_root
        self.path = os.path.dirname(txt_file)
        self.relative_path = os.path.relpath(self.path, songs_root)
        self.usdx_file = USDXFileCached(txt_file)
        self.gap_info = GapInfo(self.path)

    async def load(self):
        await self.usdx_file.load()
        await self.gap_info.load()
        self.init()

    def init(self):

        if not os.path.exists(self.txt_file):
           raise FileNotFoundError(f"File not found: {self.txt_file}")

        self.notes = self.usdx_file.notes
        self.title = self.usdx_file.tags.TITLE
        self.artist = self.usdx_file.tags.ARTIST
        self.audio = self.usdx_file.tags.AUDIO
        self.gap = self.usdx_file.tags.GAP
        self.bpm = self.usdx_file.tags.BPM
        self.start = self.usdx_file.tags.START
        self.is_relative = self.usdx_file.tags.RELATIVE

        self.path = self.usdx_file.path
        self.audio_file = os.path.join(self.path, self.audio)
        
        tmp_path = files.get_tmp_path(self.tmp_root, self.audio_file)
        self.tmp_path = tmp_path
        self.vocals_file = files.get_vocals_path(tmp_path)
        self.audio_waveform_file = files.get_waveform_path(tmp_path, "audio")
        self.vocals_waveform_file = files.get_waveform_path(tmp_path, "vocals")

        self.duration_ms = self.gap_info.duration

        self.update_status_from_gap_info()

    def __str__(self):
        return f"Song {self.artist} - {self.title}"

    def __repr__(self):
        # This will be used when printing a list of Song objects
        return f"<Song: {self.artist} - {self.title}>"
    
    def delete(self):
        files.delete_folder(self.path)

    @property
    def duration_str(self):
        if(self.duration_ms):
            return audio.milliseconds_to_str(self.duration_ms)
        else:
            "N/A"
    
    @property
    def normalized_str(self):
        """Return a string representation of the normalization status with level"""
        if self.gap_info and self.gap_info.is_normalized:
            if self.gap_info.normalization_level is not None:
                return f"{self.gap_info.normalization_level:.1f} dB"
            return "YES"  # Fallback if level not available
        return "NO"
    
    def update_status_from_gap_info(self):
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
