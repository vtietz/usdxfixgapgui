
from enum import Enum
import os
from model.gap_info import GapInfo, GapInfoStatus
import utils.files as files
import utils.audio as audio
from utils.usdx_file import USDXFile
import logging

logger = logging.getLogger(__name__)

class SongStatus(Enum):
    NOT_PROCESSED = 'NOT_PROCESSED'
    QUEUED = 'QUEUED'
    PROCESSING = 'PROCESSING'
    ERROR = 'ERROR'
    SOLVED = 'SOLVED'
    UPDATED = 'UPDATED'
    MATCH = 'MATCH'
    MISMATCH = 'MISMATCH'

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

    usdb_id: int = None
    
    audio_waveform_file: str = ""
    vocals_file: str = ""
    vocals_waveform_file: str = ""
    vocals_duration_ms: int = 0

    gap_info: GapInfo = None
    
    status: SongStatus = SongStatus.NOT_PROCESSED

    notes: list = []

    def __init__(self, usdx_file: USDXFile, gap_info: GapInfo, tmp_root: str):
        self.usdx_file = usdx_file
        self.gap_info = gap_info
        self.tmp_root = tmp_root
        self.init()

    def init(self):

        txt_file = self.usdx_file.filepath

        if not os.path.exists(txt_file):
           raise FileNotFoundError(f"File not found: {txt_file}")

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
        return audio.milliseconds_to_str(self.duration_ms)
    
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
    