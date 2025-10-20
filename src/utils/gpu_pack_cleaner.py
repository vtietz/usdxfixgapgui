"""
GPU Pack Cleaner Utility

Detects and removes GPU Packs that don't match the current Python version.
"""

import sys
import logging
import re
from pathlib import Path
from typing import List, Tuple

logger = logging.getLogger(__name__)


def get_current_python_tag() -> str:
    """Get current Python version tag (e.g., 'cp312')."""
    return f"cp{sys.version_info.major}{sys.version_info.minor}"


def detect_python_version_from_wheel(wheel_filename: str) -> str:
    """
    Extract Python version tag from wheel filename.
    
    Args:
        wheel_filename: Wheel filename (e.g., 'torch-2.4.1+cu121-cp38-cp38-win_amd64.whl')
    
    Returns:
        Python version tag (e.g., 'cp38') or empty string if not found
    """
    match = re.search(r'-cp(\d+)-', wheel_filename)
    return f"cp{match.group(1)}" if match else ""


def find_mismatched_packs(runtime_root: Path) -> List[Tuple[Path, str, str]]:
    """
    Find GPU Packs that don't match current Python version.
    
    Args:
        runtime_root: Path to gpu_runtime directory
    
    Returns:
        List of (pack_path, pack_python_version, current_python_version) tuples
    """
    if not runtime_root.exists():
        return []
    
    current_py_tag = get_current_python_tag()
    mismatched = []
    
    for pack_dir in runtime_root.iterdir():
        if not pack_dir.is_dir():
            continue
        
        # Check for wheel filename in install.json
        install_json = pack_dir / "install.json"
        if install_json.exists():
            try:
                import json
                with open(install_json, 'r') as f:
                    data = json.load(f)
                    # install.json doesn't store wheel filename, so we check dist-info folder
            except Exception as e:
                logger.debug(f"Failed to read install.json: {e}")
        
        # Check for torch dist-info folder (contains wheel metadata)
        dist_info_pattern = pack_dir / "torch-*.dist-info"
        dist_info_dirs = list(pack_dir.glob("torch-*.dist-info"))
        
        if dist_info_dirs:
            # Extract Python version from dist-info folder name
            # Format: torch-2.4.1+cu121-cp38-cp38-win_amd64
            dist_info_name = dist_info_dirs[0].name.replace(".dist-info", "")
            pack_py_tag = detect_python_version_from_wheel(dist_info_name)
            
            if pack_py_tag and pack_py_tag != current_py_tag:
                mismatched.append((pack_dir, pack_py_tag, current_py_tag))
                logger.info(
                    f"Found mismatched GPU Pack: {pack_dir.name} "
                    f"(pack: {pack_py_tag}, current: {current_py_tag})"
                )
    
    return mismatched


def clean_mismatched_packs(runtime_root: Path, dry_run: bool = True) -> int:
    """
    Remove GPU Packs that don't match current Python version.
    
    Args:
        runtime_root: Path to gpu_runtime directory
        dry_run: If True, only report what would be deleted
    
    Returns:
        Number of packs removed (or would be removed in dry_run mode)
    """
    mismatched = find_mismatched_packs(runtime_root)
    
    if not mismatched:
        logger.info("No mismatched GPU Packs found")
        return 0
    
    for pack_dir, pack_py, current_py in mismatched:
        if dry_run:
            logger.info(
                f"[DRY RUN] Would delete: {pack_dir} "
                f"(Python {pack_py} → {current_py})"
            )
        else:
            try:
                import shutil
                shutil.rmtree(pack_dir)
                logger.info(
                    f"Deleted mismatched GPU Pack: {pack_dir} "
                    f"(Python {pack_py} → {current_py})"
                )
            except Exception as e:
                logger.error(f"Failed to delete {pack_dir}: {e}")
    
    return len(mismatched)


def should_clean_on_startup(runtime_root: Path) -> bool:
    """
    Check if we should clean mismatched packs on startup.
    
    Returns:
        True if mismatched packs found and cleanup recommended
    """
    mismatched = find_mismatched_packs(runtime_root)
    return len(mismatched) > 0
