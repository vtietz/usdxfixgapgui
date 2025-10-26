"""
Chunk Writer for file I/O with fsync and hash verification.

Provides safe file writing with immediate disk sync and streaming
SHA-256 calculation for verification.
"""

import hashlib
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class ChunkWriter:
    """Write chunks to file with fsync and verification."""

    def __init__(self, file_path: Path, resume_from_byte: int = 0):
        """
        Initialize chunk writer.

        Args:
            file_path: Path to write to
            resume_from_byte: Byte position to resume from (for hash calculation)
        """
        self.file_path = file_path
        self.hasher = hashlib.sha256()
        self.bytes_written = 0
        self._resume_from_byte = resume_from_byte

        # If resuming, read existing data to update hash
        if resume_from_byte > 0 and file_path.exists():
            self._update_hash_from_existing()

    def _update_hash_from_existing(self):
        """Update hash from existing partial file."""
        with open(self.file_path, 'rb') as f:
            bytes_read = 0
            while bytes_read < self._resume_from_byte:
                chunk_size = min(8192, self._resume_from_byte - bytes_read)
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                self.hasher.update(chunk)
                bytes_read += len(chunk)
        self.bytes_written = bytes_read

    def write_chunk(self, chunk: bytes):
        """
        Write chunk and update hash.

        Args:
            chunk: Bytes to write
        """
        with open(self.file_path, 'ab') as f:
            f.write(chunk)
            f.flush()
            os.fsync(f.fileno())  # Force write to disk

        self.hasher.update(chunk)
        self.bytes_written += len(chunk)

    def verify(self, expected_sha256: str) -> bool:
        """
        Verify final hash.

        Args:
            expected_sha256: Expected SHA-256 checksum (lowercase hex)

        Returns:
            True if hash matches, False otherwise
        """
        actual_hash = self.hasher.hexdigest()
        matches = actual_hash == expected_sha256

        if not matches:
            logger.warning(
                f"Hash mismatch: expected {expected_sha256}, got {actual_hash}"
            )

        return matches

    def get_bytes_written(self) -> int:
        """
        Get total bytes written.

        Returns:
            Total bytes written (including resumed portion)
        """
        return self.bytes_written