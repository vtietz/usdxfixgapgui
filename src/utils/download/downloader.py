"""
High-level download orchestrator with modular components.

Coordinates HTTP client, resume manager, chunk writer, and retry policy
for resilient downloads with checksum verification.
"""

import logging
import urllib.error
from pathlib import Path
from typing import Optional, Callable

from .http_client import HttpClient
from .resume_manager import ResumeManager
from .chunk_writer import ChunkWriter
from .retry_policy import RetryPolicy

logger = logging.getLogger(__name__)


def download_file(
    url: str,
    dest_zip: Path,
    expected_sha256: str,
    expected_size: int,
    progress_cb: Optional[Callable[[int, int], None]] = None,
    cancel_token=None
) -> bool:
    """
    Download file with resume support and SHA-256 verification.

    Uses separate components for HTTP, resume management,
    chunk writing, and retry logic.

    Args:
        url: Download URL
        dest_zip: Destination ZIP file path
        expected_sha256: Expected SHA-256 checksum
        expected_size: Expected file size in bytes
        progress_cb: Optional callback(bytes_downloaded, total_size)
        cancel_token: Optional cancellation token

    Returns:
        True on success, False on failure
    """
    # Create parent directory
    dest_zip.parent.mkdir(parents=True, exist_ok=True)

    # Check if already complete and valid
    if dest_zip.exists():
        if _verify_complete_file(dest_zip, expected_sha256, expected_size):
            logger.info(f"File already downloaded and verified: {dest_zip}")
            if progress_cb:
                progress_cb(expected_size, expected_size)
            return True
        else:
            logger.warning(f"Existing file is corrupt, re-downloading: {dest_zip}")
            dest_zip.unlink()

    # Initialize components
    client = HttpClient(timeout=30)
    resume_mgr = ResumeManager(dest_zip)
    retry_policy = RetryPolicy(max_retries=5, initial_delay=1.0)

    start_byte = resume_mgr.get_resume_position()
    if start_byte > 0:
        logger.info(f"Resuming download from byte {start_byte}")

    # Download with retry
    def download_operation():
        try:
            response = client.get(url, start_byte=start_byte, cancel_token=cancel_token)
        except InterruptedError:
            # Cancellation should not trigger retry
            logger.info("Download cancelled by user")
            return False

        # Verify content length if provided
        if response.content_length:
            total_size = response.content_length + start_byte
            if total_size != expected_size:
                raise ValueError(
                    f"Size mismatch: expected {expected_size}, got {total_size}"
                )

        # Write chunks with verification
        writer = ChunkWriter(resume_mgr.part_file, resume_from_byte=start_byte)
        downloaded = start_byte

        for chunk in response.stream:
            writer.write_chunk(chunk)
            downloaded += len(chunk)

            if progress_cb:
                progress_cb(downloaded, expected_size)

        # Verify size
        if writer.get_bytes_written() != expected_size:
            raise ValueError(
                f"Downloaded {writer.get_bytes_written()} bytes, "
                f"expected {expected_size}"
            )

        # Verify hash
        if not _is_placeholder_checksum(expected_sha256):
            if not writer.verify(expected_sha256):
                raise ValueError("Checksum verification failed")
        else:
            logger.warning(
                f"Checksum verification skipped (placeholder: {expected_sha256})"
            )

        # Move to final location
        resume_mgr.part_file.rename(dest_zip)
        resume_mgr.cleanup()

        logger.info(f"Download complete and verified: {dest_zip}")
        return True

    # Execute with retry and handle special cases
    try:
        result = retry_policy.execute(
            download_operation,
            on_retry=lambda attempt, exc: _handle_retry(attempt, exc, resume_mgr, start_byte)
        )
        return result
    except InterruptedError:
        # Cancellation is not an error
        logger.info("Download cancelled by user")
        return False
    except urllib.error.HTTPError as e:
        if e.code == 416:  # Range not satisfiable
            logger.warning("Server does not support resume, starting from beginning")
            resume_mgr.cleanup()
            # Could retry from beginning here, but for now just fail
        logger.error(f"Download failed: HTTP {e.code} - {e.reason}")
        return False
    except Exception as e:
        logger.error(f"Download failed after retries: {e}")
        return False


def _verify_complete_file(file_path: Path, expected_sha256: str, expected_size: int) -> bool:
    """
    Verify complete file checksum and size.

    Args:
        file_path: Path to file
        expected_sha256: Expected SHA-256 checksum
        expected_size: Expected file size

    Returns:
        True if valid, False otherwise
    """
    try:
        # Import here to avoid circular dependency with gpu_downloader
        from utils.gpu_downloader import verify_file_checksum
        return verify_file_checksum(file_path, expected_sha256, expected_size)
    except Exception as e:
        logger.warning(f"Failed to verify file: {e}")
        return False


def _is_placeholder_checksum(checksum: str) -> bool:
    """
    Check if checksum is a placeholder value.

    Args:
        checksum: Checksum string

    Returns:
        True if placeholder, False otherwise
    """
    return checksum.upper() in ['TBD', 'TODO', 'PLACEHOLDER', 'UNKNOWN']


def _handle_retry(attempt: int, exc: Exception, resume_mgr: ResumeManager, start_byte: int):
    """
    Handle retry attempt.

    Args:
        attempt: Attempt number (0-indexed)
        exc: Exception that caused retry
        resume_mgr: Resume manager for cleanup
        start_byte: Starting byte position
    """
    # On certain errors, clean up partial download
    if isinstance(exc, ValueError):
        # Checksum or size mismatch - clean up and start fresh
        logger.warning("Cleaning up partial download due to verification failure")
        resume_mgr.cleanup()
