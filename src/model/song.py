class Song:
    
    path: str = ""
    title: str = ""
    artist: str = ""
    audio: str = "" 
    gap: int = 0
    detected_gap: int = 0
    diff: int = 0
    status: str = "Not processed"
    txt_file: str = ""
    vocal_file: str = ""
    waveform_file: str = ""
    audio_file: str = ""

    _isExtractingVocals: bool = False

    def __init__(self, path: str):
        self.path = path
       
    def fromTags(self, tags: dict):
      self.title = tags.get("TITLE", "")
      self.artist = tags.get("ARTIST", "")
      self.audio = tags.get("AUDIO", "")
      self.gap = tags.get("GAP", 0)
    
    def fromInfo(self, info: dict):
      self.detected_gap = info.get("detected_gap", 0)
      self.status = info.get("status", "Not processed")
      self.diff = self.detected_gap - self.gap
