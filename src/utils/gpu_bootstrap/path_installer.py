"""
Path Installation - Apply Path Changes to Runtime

Applies sys.path modifications and library path setup.
"""

import os
import sys
import logging
from dataclasses import dataclass
from typing import List

from .path_calculator import PathConfig

logger = logging.getLogger(__name__)


@dataclass
class InstallationResult:
    """Result of path installation."""

    success: bool
    added_dll_dirs: List[str]
    error_message: str = ""


class PathInstaller:
    """Install calculated paths into Python runtime."""

    @staticmethod
    def install(config: PathConfig) -> InstallationResult:
        """
        Apply path configuration to Python runtime.

        Args:
            config: PathConfig with entries to add

        Returns:
            InstallationResult with success status and tracking info
        """
        added_dll_dirs = []

        # NOTE: In PyInstaller frozen executables, we use a runtime hook to manipulate
        # sys.path BEFORE torch is imported. See hook-rthook-gpu-pack.py
        # Clearing sys.modules after the fact causes DLL conflicts and hangs.
        is_frozen = hasattr(sys, "_MEIPASS")
        if is_frozen:
            logger.debug(f"PyInstaller frozen mode: sys.path will be managed by runtime hook")

        # Add sys.path entries
        for entry in config.sys_path_entries:
            entry_str = str(entry)
            if entry_str not in sys.path:
                sys.path.insert(0, entry_str)
                logger.info(f"Added to sys.path: {entry_str}")

        # Windows: Add DLL directories
        if sys.platform == "win32":
            for dll_dir in config.dll_directories:
                if dll_dir.exists():
                    if hasattr(os, "add_dll_directory"):
                        try:
                            os.add_dll_directory(str(dll_dir))
                            added_dll_dirs.append(str(dll_dir))
                            logger.info(f"Added DLL directory: {dll_dir}")
                        except Exception as e:
                            logger.warning(f"Failed to add DLL directory {dll_dir}: {e}")
                    else:
                        logger.warning("os.add_dll_directory not available (Python <3.8)")

        # Linux: Update LD_LIBRARY_PATH
        else:
            for lib_path in config.ld_library_paths:
                if lib_path.exists():
                    ld_path = os.environ.get("LD_LIBRARY_PATH", "")
                    new_ld_path = f"{lib_path}:{ld_path}" if ld_path else str(lib_path)
                    os.environ["LD_LIBRARY_PATH"] = new_ld_path
                    logger.info(f"Added to LD_LIBRARY_PATH: {lib_path}")

        return InstallationResult(success=True, added_dll_dirs=added_dll_dirs)
