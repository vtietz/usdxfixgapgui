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
    GAP_DETECTED = 'GAP_DETECTED'
    SOLVED = 'SOLVED'
    UPDATED = 'UPDATED'
    MATCH = 'MATCH'
    MISMATCH = 'MISMATCH'
    ERROR = 'ERROR'

class Song:

    def __init__(self, txt_file: str = ""):
        # File paths
        self.txt_file: str = txt_file
        self.audio_file: str = ""

        # Song metadata
        self.title: str = ""
        self.artist: str = ""
        self.audio: str = ""
        self.gap: int = 0
        # BPM can be fractional; use float to match tests and parsers
        self.bpm: float = 0.0
        self.start: int = 0
        self.is_relative: bool = False
        self.usdb_id: Optional[int] = None

        # Audio analysis data
        self.duration_ms: int = 0

        # Notes data
        self.notes: Optional[List[Note]] = None

        # Status information
        self._gap_info: Optional[GapInfo] = None
        self.status: SongStatus = SongStatus.NOT_PROCESSED
        self.error_message: Optional[str] = ""

    @property
    def path(self):
        """Get the directory path of the song"""
        return os.path.dirname(self.txt_file) if self.txt_file else ""

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

    @property
    def status_text(self):
        """Human-readable status text - returns error message if status is ERROR"""
        if self.status == SongStatus.ERROR and self.error_message:
            return self.error_message
        return self.status.value

    @property
    def gap_info(self):
        return self._gap_info

    @gap_info.setter
    def gap_info(self, value):
        self._gap_info = value
        if value:
            value.owner = self  # Set the song as owner of gap_info
            self._gap_info_updated()
        else:
            self.status = SongStatus.NOT_PROCESSED

    def _gap_info_updated(self):
        """Private method to update song status based on current state"""
        if not self._gap_info:
            self.status = SongStatus.NOT_PROCESSED
            return

        info: GapInfo = self._gap_info
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

        if info.duration and info.duration > 0:
            self.duration_ms = info.duration

    def set_error(self, error_message: str):
        """Set error status and message.

        Args:
            error_message: Description of the error that occurred
        """
        self.status = SongStatus.ERROR
        self.error_message = error_message

    def clear_error(self):
        """Clear error status and message, resetting song to neutral ready state.

        Sets status to NOT_PROCESSED and clears error_message.
        Use this after successful operations to reset error state.
        Note: GapInfo-driven status transitions via _gap_info_updated() remain unchanged.
        """
        self.status = SongStatus.NOT_PROCESSED
        self.error_message = None

    def __str__(self):
        return f"Song [{self.artist} - {self.title}]"

    def __repr__(self):
        return f"<Song: {self.artist} - {self.title}>"

    def __getstate__(self):
        # Define which attributes to serialize
        state = self.__dict__.copy()
        state.pop("notes", None)  # Exclude notes
        return state

    def __setstate__(self, state):
        # Restore the state during deserialization
        self.__dict__.update(state)
        self.notes = None