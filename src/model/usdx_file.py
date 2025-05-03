import os
from typing import List, Optional

class ValidationError(Exception):
    """Exception raised when USDX file validation fails"""
    pass

class Tags:
    """Container for USDX file tags"""
    def __init__(self):
        self.TITLE = None
        self.ARTIST = None
        self.GAP = None
        self.AUDIO = None
        self.BPM = None
        self.RELATIVE = None
        self.START = None

    def __str__(self):
        return f"Tags(TITLE={self.TITLE}, ARTIST={self.ARTIST}, GAP={self.GAP}, AUDIO={self.AUDIO}, BPM={self.BPM}, RELATIVE={self.RELATIVE}, START={self.START})"
    
class Note:
    """Container for USDX note data"""
    def __init__(self):
        self.NoteType = None
        self.StartBeat = None
        self.Length = None
        self.Pitch = None
        self.Text = None
        self.start_ms = None
        self.duration_ms = None
        self.end_ms = None

    def __str__(self):
        return f"Notes(NoteType={self.NoteType}, StartBeat={self.StartBeat}, Length={self.Length}, Pitch={self.Pitch}, Text={self.Text})"

class USDXFile:
    """Data class for USDX file content and metadata"""
    
    def __init__(self, filepath: str = ""):
        # File info
        self.filepath = filepath
        self.path = os.path.dirname(filepath) if filepath else ""
        self.encoding = None
        
        # Content
        self.content = None
        self.tags = Tags()
        self.notes: List[Note] = []
        
        # State
        self._loaded = False
    
    def is_loaded(self) -> bool:
        return self._loaded
    
    def __str__(self):
        if self.tags.TITLE and self.tags.ARTIST:
            return f"USDXFile({self.tags.ARTIST} - {self.tags.TITLE})"
        return f"USDXFile({self.filepath})"
