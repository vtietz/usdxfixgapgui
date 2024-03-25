
import os
from model.info import Info, SongStatus
import utils.files as files
import utils.usdx as usdx
import utils.audio as audio

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
    _duration_str: str = ""
    _duration_ms: int = 0
    is_relative: bool = False

    audio_waveform_file: str = ""
    vocals_file: str = ""
    vocals_waveform_file: str = ""

    _info: Info = None
    _notes: list = []
    usdb_id: int = None

    def __init__(self, txt_file: str, tmp_root: str):
        self.txt_file = txt_file
        self.tmp_root = tmp_root

    def load(self):
        
        txt_file = self.txt_file

        if not os.path.exists(txt_file):
           raise FileNotFoundError(f"File not found: {txt_file}")

        path = files.get_song_path(txt_file)

        self._load_tags()
        self.path = path
        self.audio_file = os.path.join(path, self.audio)
        tmp_path = files.get_temp_path(self.tmp_root, self.audio_file)
        self.txt_file = txt_file
        self.vocals_file = files.get_vocals_path(tmp_path)
        self.audio_waveform_file = files.get_waveform_path(tmp_path, "audio")
        self.vocals_waveform_file = files.get_waveform_path(tmp_path, "vocals")
        self.tmp_path = tmp_path
       
    def _load_tags(self):
        tags = usdx.extract_tags(self.txt_file)
        if not tags:
            raise Exception(f"Failed to extract tags from {self.txt_file}")
        self.title = tags.get("TITLE", "")
        self.artist = tags.get("ARTIST", "")
        self.audio = tags.get("AUDIO", "")
        self.gap = tags.get("GAP", 0)
        self.bpm = tags.get("BPM", 0)
        self.start = tags.get("START", 0)
        self.is_relative = tags.get("RELATIVE", False)

    def _load_notes(self):
        self._notes = usdx.parse_notes(self.txt_file)

    def _load_duration(self):
        self._duration_ms=audio.get_audio_duration(self.audio_file)
    
    def __str__(self):
        return f"Song: {self.artist} - {self.title}"
    
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
    def notes(self):
        if not self._notes:
            self._load_notes()
        return self._notes
    
    @property
    def info(self):
        if not self._info:
            info_file = files.get_info_file_path(self.path)
            self._info = Info(info_file)
            if not os.path.exists(info_file):
                self._info.status = SongStatus.NOT_PROCESSED
            else:
                self._info.load()
        return self._info

    