from enum import Enum
import os
import re
from datetime import datetime
from typing import List, Optional

import logging
import _strptime  # noqa: F401  # Ensure datetime.strptime dependencies bundled/available
import utils.audio as audio

from model.gap_info import GapInfo, GapInfoStatus
from model.usdx_file import Note  # Add this import

logger = logging.getLogger(__name__)


class SongStatus(Enum):
    NOT_PROCESSED = "NOT_PROCESSED"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    SOLVED = "SOLVED"
    UPDATED = "UPDATED"
    MATCH = "MATCH"
    MISMATCH = "MISMATCH"
    MISSING_AUDIO = "MISSING_AUDIO"
    ERROR = "ERROR"


ARTICLE_PREFIXES = ("the ", "a ", "an ")
NUMBER_PADDING = 6


def _title_sort_substr(value: str) -> str:
    """Normalize title for sorting (drop articles, pad numbers, collapse whitespace)."""
    if not value:
        return ""

    normalized = value.casefold().strip()
    for prefix in ARTICLE_PREFIXES:
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix):]
            break

    normalized = re.sub(r"\s+", " ", normalized)
    normalized = re.sub(r"\d+", lambda match: match.group(0).zfill(NUMBER_PADDING), normalized)
    return normalized


TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"


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
        self._status: SongStatus = SongStatus.NOT_PROCESSED
        self._status_changed_at: Optional[datetime] = None
        self._status_changed_str: str = ""
        self.status = SongStatus.NOT_PROCESSED
        self.error_message: Optional[str] = ""
        self._title_sort_key: str = ""

    @property
    def status(self) -> SongStatus:
        return getattr(self, "_status", SongStatus.NOT_PROCESSED)

    @status.setter
    def status(self, value):
        normalized = self._normalize_status_value(value)
        if getattr(self, "_status", None) == normalized and self._status_changed_at is not None:
            return
        self._status = normalized
        self._touch_status_timestamp()

    def _normalize_status_value(self, value) -> SongStatus:
        if isinstance(value, SongStatus):
            return value
        if isinstance(value, str):
            try:
                return SongStatus[value]
            except KeyError:
                logger.warning("Invalid status string %s on Song", value)
                return SongStatus.ERROR
        return SongStatus.NOT_PROCESSED

    def _touch_status_timestamp(self, timestamp: Optional[datetime] = None):
        ts = timestamp or datetime.now()
        self._status_changed_at = ts
        try:
            self._status_changed_str = ts.strftime(TIMESTAMP_FORMAT)
        except Exception:
            self._status_changed_str = ts.isoformat(timespec="seconds")

    def set_status_timestamp_from_string(self, timestamp_str: str):
        if not timestamp_str:
            return
        try:
            parsed = datetime.strptime(timestamp_str, TIMESTAMP_FORMAT)
        except ValueError:
            self._status_changed_at = None
            self._status_changed_str = timestamp_str
            return
        self._touch_status_timestamp(parsed)

    @property
    def status_time_display(self) -> str:
        if self._gap_info and self._gap_info.processed_time:
            return self._gap_info.processed_time
        if self._status_changed_str:
            return self._status_changed_str
        return ""

    @property
    def status_time_sort_key(self) -> str:
        return self.status_time_display

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
    def title_sort_key(self) -> str:
        """Normalized title used for consistent UI sorting."""
        if not self._title_sort_key:
            self._title_sort_key = _title_sort_substr(self.title)
        return self._title_sort_key

    def update_title_sort_key(self):
        """Recompute the cached title sort key after metadata changes."""
        self._title_sort_key = _title_sort_substr(self.title)

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
        previous_gap_info = getattr(self, "_gap_info", None)
        previous_processed = previous_gap_info.processed_time if previous_gap_info else ""
        previous_timestamp = self._status_changed_at

        self._gap_info = value
        if value:
            value.owner = self  # Set the song as owner of gap_info

            if previous_processed:
                candidate = value.processed_time or ""
                keep_previous = False
                candidate_dt = self._parse_timestamp(candidate)
                if not candidate or candidate_dt is None:
                    keep_previous = True
                elif previous_timestamp and candidate_dt < previous_timestamp:
                    keep_previous = True
                else:
                    previous_dt = self._parse_timestamp(previous_processed)
                    if previous_dt and candidate_dt < previous_dt:
                        keep_previous = True

                if keep_previous:
                    value.processed_time = previous_processed

            self._gap_info_updated()
            if value.processed_time:
                self.set_status_timestamp_from_string(value.processed_time)
        else:
            self.status = SongStatus.NOT_PROCESSED

    @staticmethod
    def _parse_timestamp(timestamp_str: str) -> Optional[datetime]:
        if not timestamp_str:
            return None
        try:
            return datetime.strptime(timestamp_str, TIMESTAMP_FORMAT)
        except ValueError:
            return None

    def _gap_info_updated(self):
        """Private method to update song status based on current state"""
        # Preserve MISSING_AUDIO status - don't overwrite it
        if self.status == SongStatus.MISSING_AUDIO:
            return

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
            # Copy error message from gap_info to song, with fallback for legacy data
            if info.error_message:
                self.error_message = info.error_message
            else:
                self.error_message = "Historical error (no details available)"
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
        legacy_status = state.pop("status", None)
        self.__dict__.update(state)
        self.notes = None
        if not getattr(self, "_title_sort_key", ""):
            self.update_title_sort_key()
        if not hasattr(self, "_status"):
            normalized = self._normalize_status_value(legacy_status) if legacy_status else SongStatus.NOT_PROCESSED
            self._status = normalized
        if not hasattr(self, "_status_changed_at"):
            self._status_changed_at = None
        if not hasattr(self, "_status_changed_str"):
            self._status_changed_str = ""
        if not self._status_changed_str and getattr(self, "_gap_info", None):
            processed = getattr(self._gap_info, "processed_time", "")
            if processed:
                self.set_status_timestamp_from_string(processed)
