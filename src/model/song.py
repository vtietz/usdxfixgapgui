
from enum import Enum
import os
from model.gap_info import GapInfo, GapInfoStatus
import utils.files as files
import utils.audio as audio
from utils.usdx_file import USDXFile


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
    
    _duration_str: str = ""
    _duration_ms: int = 0

    audio_waveform_file: str = ""
    vocals_file: str = ""
    vocals_waveform_file: str = ""

    gap_info: GapInfo = None
    
    status: SongStatus = SongStatus.NOT_PROCESSED

    notes: list = []

    file: USDXFile = None

    def __init__(self, txt_file: str, tmp_root: str):
        self.txt_file = txt_file
        self.tmp_root = tmp_root

    async def load(self):
        print(f"Loading song {self.txt_file}")
        txt_file = self.txt_file
        if not os.path.exists(txt_file):
           raise FileNotFoundError(f"File not found: {txt_file}")

        file = USDXFile(txt_file)
        await file.load()
        self.file = file
        
        self.notes = file.notes
        self.title = file.tags.TITLE
        self.artist = file.tags.ARTIST
        self.audio = file.tags.AUDIO
        self.gap = file.tags.GAP
        self.bpm = file.tags.BPM
        self.start = file.tags.START
        self.is_relative = file.tags.RELATIVE

        path = files.get_song_path(txt_file)
        self.path = path
        self.txt_file = txt_file
        self.audio_file = os.path.join(path, self.audio)
        
        tmp_path = files.get_temp_path(self.tmp_root, self.audio_file)
        self.tmp_path = tmp_path
        self.vocals_file = files.get_vocals_path(tmp_path)
        self.audio_waveform_file = files.get_waveform_path(tmp_path, "audio")
        self.vocals_waveform_file = files.get_waveform_path(tmp_path, "vocals")

        gap_info_file = files.get_info_file_path(self.path)
        gap_info = GapInfo(gap_info_file)
        await gap_info.load()
        if(not gap_info.original_gap):
            gap_info.original_gap = self.gap
        self.gap_info = gap_info
        self.update_status_from_gap_info()

        print(f"Song loaded: {self}")

    def _load_duration(self):
        self._duration_ms=audio.get_audio_duration(self.audio_file)
    
    def __str__(self):
        return f"Song {self.artist} - {self.title} - {self.file.tags}"
    
    def delete(self):
        files.delete_folder(self.path)

    @property
    def duration_str(self):
        if not self._duration_str:
            self._duration_str = audio.milliseconds_to_str(self.duration_ms)
        return self._duration_str
    
    @property
    def duration_ms(self):
        if not self._duration_ms:
            self._load_duration()
        return self._duration_ms
    
    def load_info(self):
        if not self._info:
            info_file = files.get_info_file_path(self.path)
            self._info = GapInfo(info_file)
            if not os.path.exists(info_file):
                self._info.status = SongStatus.NOT_PROCESSED.value,
                self._info.original_gap = self.gap
            else:
                self._info.load()
        return self._info


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
        else:
            self.status = SongStatus.NOT_PROCESSED
    