
import os
from model.info import Info, SongStatus
import utils.files as files
import utils.usdx as usdx

class Song:

    txt_file: str = ""

    path: str = ""
    tmp_path: str = ""
    audio_file: str = ""
    
    title: str = ""
    artist: str = ""
    audio: str = "" 
    gap: int = 0
    bpm: int = 0
    is_relative: bool = False

    audio_waveform_file: str = ""
    vocals_file: str = ""
    vocals_waveform_file: str = ""

    info: Info = None

    def __init__(self, txt_file: str):
        self.txt_file = txt_file

    def load(self):
        
        txt_file = self.txt_file

        if not os.path.exists(txt_file):
           raise FileNotFoundError(f"File not found: {txt_file}")

        path = files.get_song_path(txt_file)
        info_file = files.get_info_file_path(path)
        self.info = Info(info_file)

        if os.path.exists(info_file):
            self.info.load()

        self.load_tags()
        self.path = path
        self.info_file= info_file
        self.audio_file = os.path.join(path, self.audio)
        tmp_path = files.get_temp_path(self.audio_file)
        self.txt_file = txt_file
        self.vocals_file = files.get_vocals_path(tmp_path)
        self.audio_waveform_file = files.get_waveform_path(tmp_path, "audio")
        self.vocals_waveform_file = files.get_waveform_path(tmp_path, "vocals")
        self.notes = usdx.parse_notes(txt_file)
        self.tmp_path = tmp_path
       
    def load_tags(self):
        tags = usdx.extract_tags(self.txt_file)
        if not tags:
            raise Exception(f"Failed to extract tags from {self.txt_file}")
        self.title = tags.get("TITLE", "")
        self.artist = tags.get("ARTIST", "")
        self.audio = tags.get("AUDIO", "")
        self.gap = tags.get("GAP", 0)
        self.bpm = tags.get("BPM", 0)
        self.is_relative = tags.get("RELATIVE", False)
    
    def __str__(self):
        return f"Song: {self.artist} - {self.title}"


