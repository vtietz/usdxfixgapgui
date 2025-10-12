"""
GPU Pack Downloader Module for USDXFixGap

Handles GPU Pack download with resume support, SHA-256 verification,
and atomic extraction.
"""

import os
import json
import hashlib
import logging
import time
import uuid
import shutil
import zipfile
from pathlib import Path
from typing import Optional, Callable
from datetime import datetime
import urllib.request
import urllib.error

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
    cancel_token: Optional[CancelToken] = None
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
        
    Returns:
        True on success, False on failure
    """
    part_file = dest_zip.with_suffix('.part')
    meta_file = dest_zip.with_suffix('.meta')
    
    # Create parent directory
    dest_zip.parent.mkdir(parents=True, exist_ok=True)
    
    # Check if already downloaded and valid
    if dest_zip.exists():
        if verify_file_checksum(dest_zip, expected_sha256, expected_size):
            logger.info(f"File already downloaded and verified: {dest_zip}")
            if progress_cb:
                progress_cb(expected_size, expected_size)
            return True
        else:
            logger.warning(f"Existing file is corrupt, re-downloading: {dest_zip}")
            dest_zip.unlink()
    
    # Resume from partial download if available
    start_byte = 0
    if part_file.exists():
        start_byte = part_file.stat().st_size
        logger.info(f"Resuming download from byte {start_byte}")
    
    # Download with resume and exponential backoff
    max_retries = 5
    retry_delay = 1.0
    
    for attempt in range(max_retries):
        try:
            headers = {}
            if start_byte > 0:
                headers['Range'] = f'bytes={start_byte}-'
            
            req = urllib.request.Request(url, headers=headers)
            req.add_header('User-Agent', 'USDXFixGap/1.0')
            
            with urllib.request.urlopen(req, timeout=30) as response:
                # Check content length
                content_length = response.getheader('Content-Length')
                if content_length:
                    total_size = int(content_length) + start_byte
                    if total_size != expected_size:
                        logger.warning(
                            f"Size mismatch: expected {expected_size}, "
                            f"got {total_size}"
                        )
                else:
                    total_size = expected_size
                
                # Download with progress
                hasher = hashlib.sha256()
                downloaded = start_byte
                
                # Read existing partial file for hash if resuming
                if start_byte > 0 and part_file.exists():
                    with open(part_file, 'rb') as f:
                        while True:
                            chunk = f.read(8192)
                            if not chunk:
                                break
                            hasher.update(chunk)
                
                with open(part_file, 'ab') as f:
                    while True:
                        # Check cancellation
                        if cancel_token and cancel_token.is_cancelled():
                            logger.info("Download cancelled by user")
                            return False
                        
                        chunk = response.read(8192)
                        if not chunk:
                            break
                        
                        f.write(chunk)
                        hasher.update(chunk)
                        downloaded += len(chunk)
                        
                        # Progress callback
                        if progress_cb:
                            progress_cb(downloaded, total_size)
                
                # Verify checksum
                actual_sha256 = hasher.hexdigest()
                if actual_sha256 != expected_sha256:
                    logger.error(
                        f"Checksum mismatch: expected {expected_sha256}, "
                        f"got {actual_sha256}"
                    )
                    return False
                
                # Verify size
                if downloaded != expected_size:
                    logger.error(
                        f"Size mismatch: expected {expected_size}, "
                        f"got {downloaded}"
                    )
                    return False
                
                # Move to final location
                shutil.move(str(part_file), str(dest_zip))
                
                # Clean up meta file
                if meta_file.exists():
                    meta_file.unlink()
                
                logger.info(f"Download complete and verified: {dest_zip}")
                return True
                
        except urllib.error.HTTPError as e:
            if e.code == 416:  # Range not satisfiable
                logger.warning("Server does not support resume, starting from beginning")
                if part_file.exists():
                    part_file.unlink()
                start_byte = 0
            else:
                logger.warning(f"HTTP error {e.code}: {e.reason}")
        
        except Exception as e:
            logger.warning(f"Download attempt {attempt + 1} failed: {e}")
        
        # Retry with exponential backoff
        if attempt < max_retries - 1:
            time.sleep(retry_delay)
            retry_delay *= 2
    
    logger.error(f"Download failed after {max_retries} attempts")
    return False


def verify_file_checksum(file_path: Path, expected_sha256: str, expected_size: int) -> bool:
    """
    Verify file checksum and size.
    
    Args:
        file_path: Path to file
        expected_sha256: Expected SHA-256 checksum
        expected_size: Expected file size
        
    Returns:
        True if valid, False otherwise
    """
    try:
        # Check size first (fast)
        actual_size = file_path.stat().st_size
        if actual_size != expected_size:
            logger.debug(f"Size mismatch: expected {expected_size}, got {actual_size}")
            return False
        
        # Check SHA-256
        hasher = hashlib.sha256()
        with open(file_path, 'rb') as f:
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
        temp_dir = dest_dir.parent / f'tmp_{uuid.uuid4().hex}'
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Extracting {zip_path} to {temp_dir}")
        
        # Extract ZIP
        with zipfile.ZipFile(zip_path, 'r') as zf:
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
            except:
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
            'app_version': manifest.app_version,
            'torch_version': manifest.torch_version,
            'cuda_version': manifest.cuda_version,
            'sha256': manifest.sha256,
            'install_time': datetime.utcnow().isoformat(),
            'flavor': manifest.flavor
        }
        
        install_json = dest_dir / 'install.json'
        with open(install_json, 'w') as f:
            json.dump(install_record, f, indent=2)
        
        logger.info(f"Installation record written: {install_json}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to write installation record: {e}")
        return False
