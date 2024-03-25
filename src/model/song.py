
import os
from model.info import Info, SongStatus
import utils.files as files
import utils.usdx as usdx
import utils.audio as audio
from utils.usdx_file import USDXFile

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

    _info: Info = None
    notes: list = []

    file: USDXFile = None

    def __init__(self, txt_file: str, tmp_root: str):
        self.txt_file = txt_file
        self.tmp_root = tmp_root

    def load(self):
        
        txt_file = self.txt_file
        if not os.path.exists(txt_file):
           raise FileNotFoundError(f"File not found: {txt_file}")

        file = USDXFile(txt_file)
        file.load()
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

    def _load_duration(self):
        self._duration_ms=audio.get_audio_duration(self.audio_file)
    
    def __str__(self):
        return f"Song {self.artist} - {self.title} - {self.file.tags}"
    
    def reload(self):
        self._info = None
        self._notes = []
        self._duration_ms = 0
        self.load()

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
    
    @property
    def info(self):
        if not self._info:
            info_file = files.get_info_file_path(self.path)
            self._info = Info(info_file)
            if not os.path.exists(info_file):
                self._info.status = SongStatus.NOT_PROCESSED
                self._info.original_gap = self.gap
            else:
                self._info.load()
        return self._info

    