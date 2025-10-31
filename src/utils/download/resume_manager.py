"""
Resume Manager for partial download state and persistence.

Manages .part files, .meta files, and resume position calculation
for interrupted downloads.
"""

import json
import logging
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class DownloadState:
    """Persisted download state for resume."""

    url: str
    dest_path: str  # Store as string for JSON serialization
    expected_size: int
    expected_sha256: str
    bytes_downloaded: int

    def save(self, meta_file: Path):
        """
        Persist state to JSON.

        Args:
            meta_file: Path to .meta file
        """
        with open(meta_file, "w") as f:
            json.dump(asdict(self), f, indent=2)

    @classmethod
    def load(cls, meta_file: Path) -> Optional["DownloadState"]:
        """
        Load state from JSON.

        Args:
            meta_file: Path to .meta file

        Returns:
            DownloadState if file exists and is valid, None otherwise
        """
        if not meta_file.exists():
            return None
        try:
            with open(meta_file, "r") as f:
                data = json.load(f)
                return cls(**data)
        except Exception as e:
            logger.warning(f"Failed to load download state: {e}")
            return None


class ResumeManager:
    """Manage partial download state and resume."""

    def __init__(self, dest_file: Path):
        """
        Initialize resume manager.

        Args:
            dest_file: Final destination file path
        """
        self.dest_file = dest_file
        self.part_file = dest_file.with_suffix(".part")
        self.meta_file = dest_file.with_suffix(".meta")

    def get_resume_position(self) -> int:
        """
        Get byte position to resume from.

        Returns:
            Starting byte position (0 if no partial download exists)
        """
        if not self.part_file.exists():
            return 0

        # Try to load from metadata first
        state = DownloadState.load(self.meta_file)
        if state:
            return state.bytes_downloaded

        # Fallback: use file size
        return self.part_file.stat().st_size

    def save_state(self, url: str, expected_size: int, expected_sha256: str, bytes_downloaded: int):
        """
        Save current download state.

        Args:
            url: Download URL
            expected_size: Expected file size
            expected_sha256: Expected SHA-256 checksum
            bytes_downloaded: Bytes downloaded so far
        """
        state = DownloadState(
            url=url,
            dest_path=str(self.dest_file),
            expected_size=expected_size,
            expected_sha256=expected_sha256,
            bytes_downloaded=bytes_downloaded,
        )
        state.save(self.meta_file)

    def cleanup(self):
        """Remove partial files and metadata."""
        if self.part_file.exists():
            self.part_file.unlink()
        if self.meta_file.exists():
            self.meta_file.unlink()
