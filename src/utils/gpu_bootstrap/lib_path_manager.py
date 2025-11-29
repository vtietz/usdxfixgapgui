"""
Library Path Manager for GPU Bootstrap

Platform-specific path management extracted from monolithic enable_gpu_runtime.
Handles Windows DLL directories, Linux LD_LIBRARY_PATH, and sys.path manipulation.
"""

import os
import sys
import logging
from pathlib import Path
from typing import List
from .types import InstallationResult

logger = logging.getLogger(__name__)


class LibPathManager:
    """Manages platform-specific library path configuration."""

    def __init__(self):
        self.added_dll_dirs: List[str] = []
        self.added_sys_paths: List[str] = []
        self.added_ld_paths: List[str] = []
        self.messages: List[str] = []

    def add_dll_dir(self, path: Path) -> bool:
        """
        Add directory to Windows DLL search path.

        Args:
            path: Directory containing DLLs

        Returns:
            True if successful or not Windows, False on failure
        """
        if sys.platform != "win32":
            return True  # Not applicable on non-Windows

        if not path.exists():
            self.messages.append(f"DLL directory does not exist: {path}")
            return False

        if not hasattr(os, "add_dll_directory"):
            self.messages.append("os.add_dll_directory not available")
            return False

        try:
            os.add_dll_directory(str(path))
            self.added_dll_dirs.append(str(path))
            logger.debug(f"Added DLL directory: {path}")
            return True
        except Exception as e:
            self.messages.append(f"Failed to add DLL directory {path}: {e}")
            logger.warning(f"Failed to add DLL directory {path}: {e}")
            return False

    def prepend_sys_path(self, path: Path) -> None:
        """
        Prepend directory to sys.path (highest priority).

        Args:
            path: Directory to add to sys.path
        """
        path_str = str(path)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)
            self.added_sys_paths.append(path_str)
            logger.debug(f"Added to sys.path: {path_str}")

    def update_ld_library_path(self, path: Path) -> None:
        """
        Prepend directory to LD_LIBRARY_PATH (Linux).

        Args:
            path: Directory containing shared libraries
        """
        if sys.platform == "win32":
            return  # Not applicable on Windows

        if not path.exists():
            self.messages.append(f"LD_LIBRARY_PATH directory does not exist: {path}")
            return

        path_str = str(path)
        ld_path = os.environ.get("LD_LIBRARY_PATH", "")

        if ld_path:
            new_ld_path = f"{path_str}:{ld_path}"
        else:
            new_ld_path = path_str

        os.environ["LD_LIBRARY_PATH"] = new_ld_path
        self.added_ld_paths.append(path_str)
        logger.info(f"Added to LD_LIBRARY_PATH: {path_str}")

    def install_paths(self, dll_dirs: List[Path], sys_paths: List[Path], ld_paths: List[Path]) -> InstallationResult:
        """
        Install all configured paths.

        Args:
            dll_dirs: Windows DLL directories to add
            sys_paths: Python sys.path entries to prepend
            ld_paths: Linux LD_LIBRARY_PATH entries to prepend

        Returns:
            InstallationResult with success status and tracking info
        """
        # Add sys.path entries first (highest priority)
        for path in sys_paths:
            self.prepend_sys_path(path)

        # Platform-specific library paths
        if sys.platform == "win32":
            for dll_dir in dll_dirs:
                self.add_dll_dir(dll_dir)
        else:
            for ld_path in ld_paths:
                self.update_ld_library_path(ld_path)

        # Consider success if at least one critical path was added
        success = bool(self.added_sys_paths or self.added_dll_dirs or self.added_ld_paths)

        return InstallationResult(
            success=success,
            added_dll_dirs=self.added_dll_dirs.copy(),
            added_sys_paths=self.added_sys_paths.copy(),
            added_ld_paths=self.added_ld_paths.copy(),
            messages=self.messages.copy(),
            error_message=None if success else "Failed to add any paths",
        )

    def get_installation_result(self) -> InstallationResult:
        """Get current installation result."""
        success = bool(self.added_sys_paths or self.added_dll_dirs or self.added_ld_paths)

        return InstallationResult(
            success=success,
            added_dll_dirs=self.added_dll_dirs.copy(),
            added_sys_paths=self.added_sys_paths.copy(),
            added_ld_paths=self.added_ld_paths.copy(),
            messages=self.messages.copy(),
            error_message=None if success else "No paths were added",
        )
