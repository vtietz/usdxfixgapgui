"""
Download Cleanup Utilities

Helper functions for cleaning up GPU Pack download artifacts (.zip, .part, .meta files).
Extracted from startup_dialog.py to reduce complexity and improve reusability.
"""

import logging
import time
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)


def cleanup_download_files_safe(config) -> None:
    """
    Clean up download files safely (best effort, no errors on failure).

    Removes all .zip, .part, and .meta files from GPU runtime directory.
    Used for flavor switching and general cleanup without failing on errors.

    Args:
        config: Application config object with data_dir attribute
    """
    try:
        from utils.files import get_localappdata_dir

        if config and hasattr(config, "data_dir") and config.data_dir:
            pack_dir = Path(config.data_dir) / "gpu_runtime"
        else:
            localappdata = get_localappdata_dir()
            pack_dir = Path(localappdata) / "gpu_runtime"

        if pack_dir.exists():
            for pattern in ["*.zip", "*.part", "*.meta"]:
                for file_path in pack_dir.glob(pattern):
                    try:
                        file_path.unlink()
                        logger.info(f"Deleted: {file_path}")
                    except Exception as e:
                        logger.debug(f"Could not delete {file_path}: {e}")
    except Exception as e:
        logger.debug(f"Cleanup failed (non-critical): {e}")


def cleanup_download_files(dest_zip: Path, log_cb: Optional[Callable[[str], None]] = None) -> int:
    """
    Clean up ALL download files to force fresh download.

    This is intentionally aggressive to prevent resume-related issues:
    - Corrupt partial downloads
    - SSL/network errors during resume
    - "Bad magic number" from incomplete ZIPs

    Removes:
    - .zip file (final download, might be corrupt)
    - .part file (partial download)
    - .meta file (download metadata)

    Args:
        dest_zip: Path to the destination ZIP file
        log_cb: Optional callback for user-facing log messages

    Returns:
        Number of files successfully cleaned up
    """
    files_to_clean = [
        dest_zip.with_suffix(".part"),  # Partial download - MUST be deleted first
        dest_zip.with_suffix(".meta"),  # Download metadata
        dest_zip,  # Final ZIP file (might be corrupt)
    ]

    cleaned_count = 0
    for file_path in files_to_clean:
        if file_path.exists():
            # Try multiple times with delay (file might be locked by previous worker thread)
            for attempt in range(3):
                try:
                    file_path.unlink()
                    logger.info(f"Deleted download file to force fresh start: {file_path}")
                    cleaned_count += 1
                    break  # Success, move to next file
                except PermissionError as e:
                    if attempt < 2:  # Not the last attempt
                        logger.warning(f"File locked, retrying in 1 second: {file_path}")
                        time.sleep(1)  # Wait for previous worker to release file
                    else:
                        logger.error(f"Failed to delete {file_path} after 3 attempts: {e}")
                        if log_cb:
                            log_cb(f"⚠️ Could not clean up {file_path.name} (file in use)")
                            log_cb(f"   Please close any programs using this file and try again")
                except Exception as e:
                    logger.warning(f"Failed to delete {file_path}: {e}")
                    break  # Don't retry for other exceptions

    if cleaned_count > 0:
        logger.info(f"Cleaned up {cleaned_count} download file(s) for fresh start")
        if log_cb:
            log_cb(f"Cleaned up {cleaned_count} old download file(s)")

    return cleaned_count
