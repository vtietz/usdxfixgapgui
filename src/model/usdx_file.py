import os
from typing import List, Optional

class ValidationError(Exception):
    """Exception raised when USDX file validation fails"""

class Tags:
    """Container for USDX file tags"""
    def __init__(self):
        # Optional annotations prevent Pylance from inferring attributes as literal None
        self.TITLE: Optional[str] = None
        self.ARTIST: Optional[str] = None
        self.GAP: Optional[int] = None
        self.AUDIO: Optional[str] = None
        self.BPM: Optional[float] = None
        self.RELATIVE: Optional[bool] = None
        self.START: Optional[float] = None

    def __str__(self):
        return f"Tags(TITLE={self.TITLE}, ARTIST={self.ARTIST}, GAP={self.GAP}, AUDIO={self.AUDIO}, BPM={self.BPM}, RELATIVE={self.RELATIVE}, START={self.START})"

class Note:
    """Container for USDX note data"""
    def __init__(self):
        self.NoteType: Optional[str] = None
        self.StartBeat: Optional[int] = None
        self.Length: Optional[int] = None
        self.Pitch: Optional[int] = None
        self.Text: Optional[str] = None
        self.start_ms: Optional[float] = None
        self.duration_ms: Optional[float] = None
        self.end_ms: Optional[float] = None

    def __str__(self):
        return f"Notes(NoteType={self.NoteType}, StartBeat={self.StartBeat}, Length={self.Length}, Pitch={self.Pitch}, Text={self.Text})"

class USDXFile:
    """Data class for USDX file content and metadata"""

    def __init__(self, filepath: str = ""):
        # File info
        self.filepath = filepath
        self.path = os.path.dirname(filepath) if filepath else ""
        self.encoding: Optional[str] = None

        # Content
        self.content: Optional[str] = None
        self.tags: Tags = Tags()
        self.notes: List[Note] = []

        # State
        self._loaded: bool = False

    def is_loaded(self) -> bool:
        return self._loaded

    def __str__(self):
        if self.tags.TITLE and self.tags.ARTIST:
            return f"USDXFile({self.tags.ARTIST} - {self.tags.TITLE})"
        return f"USDXFile({self.filepath})"