"""
GPU Pack Downloader Module for USDXFixGap

Handles GPU Pack download with resume support, SHA-256 verification,
and atomic extraction.
"""

import json
import hashlib
import logging
import uuid
import shutil
import zipfile
from pathlib import Path
from typing import Optional, Callable
from datetime import datetime

logger = logging.getLogger(__name__)


class CancelToken:
    """Simple cancellation token for downloads."""

    def __init__(self):
        self.cancelled = False

    def cancel(self):
        self.cancelled = True

    def is_cancelled(self) -> bool:
        return self.cancelled


def download_with_resume(
    url: str,
    dest_zip: Path,
    expected_sha256: str,
    expected_size: int,
    progress_cb: Optional[Callable[[int, int], None]] = None,
    cancel_token: Optional[CancelToken] = None,
    config=None,
) -> bool:
    """
    Download file with resume support and SHA-256 verification.

    Args:
        url: Download URL
        dest_zip: Destination ZIP file path
        expected_sha256: Expected SHA-256 checksum
        expected_size: Expected file size in bytes
        progress_cb: Optional callback(bytes_downloaded, total_size)
        cancel_token: Optional cancellation token
        config: Optional configuration object (unused, kept for compatibility)

    Returns:
        True on success, False on failure
    """
    from utils.download import download_file

    logger.info("Using resilient downloader")
    return download_file(
        url=url,
        dest_zip=dest_zip,
        expected_sha256=expected_sha256,
        expected_size=expected_size,
        progress_cb=progress_cb,
        cancel_token=cancel_token,
    )


def verify_file_checksum(file_path: Path, expected_sha256: str, expected_size: int) -> bool:
    """
    Verify file checksum and size.

    Args:
        file_path: Path to file
        expected_sha256: Expected SHA-256 checksum (or "TBD" to skip verification)
        expected_size: Expected file size

    Returns:
        True if valid, False otherwise
    """
    try:
        # Skip verification if SHA256 not defined yet
        if expected_sha256 == "TBD":
            logger.info(f"Skipping checksum verification (not defined for this wheel yet)")
            actual_size = file_path.stat().st_size
            logger.info(f"Downloaded file size: {actual_size} bytes ({actual_size / 1024 / 1024:.1f} MB)")
            return True

        # Check size first (fast)
        actual_size = file_path.stat().st_size
        if actual_size != expected_size:
            logger.debug(f"Size mismatch: expected {expected_size}, got {actual_size}")
            return False

        # Check SHA-256
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(8192)
                if not chunk:
                    break
                hasher.update(chunk)

        actual_sha256 = hasher.hexdigest()
        if actual_sha256 != expected_sha256:
            logger.debug(f"SHA-256 mismatch: expected {expected_sha256}, got {actual_sha256}")
            return False

        return True

    except Exception as e:
        logger.warning(f"Failed to verify file: {e}")
        return False


def extract_zip(zip_path: Path, dest_dir: Path) -> bool:
    """
    Extract ZIP file to destination with atomic move.

    Args:
        zip_path: Path to ZIP file
        dest_dir: Destination directory (e.g., gpu_runtime/v1.4.0-cu121)

    Returns:
        True on success, False on failure
    """
    temp_dir = None
    try:
        # Create temporary extraction directory
        temp_dir = dest_dir.parent / f"tmp_{uuid.uuid4().hex}"
        temp_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Extracting {zip_path} to {temp_dir}")

        # Extract ZIP
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(temp_dir)

        # Atomic move to final location
        if dest_dir.exists():
            # Remove old installation
            logger.info(f"Removing old installation: {dest_dir}")
            shutil.rmtree(dest_dir)

        shutil.move(str(temp_dir), str(dest_dir))

        logger.info(f"Extraction complete: {dest_dir}")
        return True

    except Exception as e:
        logger.error(f"Extraction failed: {e}", exc_info=True)

        # Clean up temp dir
        if temp_dir and temp_dir.exists():
            try:
                shutil.rmtree(temp_dir)
            except Exception:
                pass

        return False


def write_install_record(dest_dir: Path, manifest) -> bool:
    """
    Write installation record to install.json.

    Args:
        dest_dir: GPU Pack installation directory
        manifest: GpuPackManifest object

    Returns:
        True on success, False on failure
    """
    try:
        install_record = {
            "app_version": manifest.app_version,
            "torch_version": manifest.torch_version,
            "cuda_version": manifest.cuda_version,
            "sha256": manifest.sha256,
            "install_time": datetime.utcnow().isoformat(),
            "flavor": manifest.flavor,
        }

        install_json = dest_dir / "install.json"
        with open(install_json, "w") as f:
            json.dump(install_record, f, indent=2)

        logger.info(f"Installation record written: {install_json}")
        return True

    except Exception as e:
        logger.error(f"Failed to write installation record: {e}")
        return False
