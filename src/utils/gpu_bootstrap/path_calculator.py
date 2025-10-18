"""
Path Calculation - Determine Required Path Additions

Calculates sys.path entries and library paths based on detected layout.
"""

import sys
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import List

from .layout_detector import PackLayout

logger = logging.getLogger(__name__)


@dataclass
class PathConfig:
    """Configuration for path additions."""
    sys_path_entries: List[Path]  # Entries to add to sys.path
    dll_directories: List[Path]  # Windows DLL directories
    ld_library_paths: List[Path]  # Linux LD_LIBRARY_PATH entries


class PathCalculator:
    """Calculate required path additions based on layout."""

    @staticmethod
    def calculate(pack_dir: Path, layout: PackLayout) -> PathConfig:
        """
        Calculate paths to add for given layout.

        Args:
            pack_dir: Root directory of GPU Pack
            layout: Detected layout type

        Returns:
            PathConfig with sys.path and library paths
        """
        if layout == PackLayout.WHEEL_EXTRACTION:
            return PathCalculator._calculate_wheel_paths(pack_dir)
        elif layout == PackLayout.SITE_PACKAGES:
            return PathCalculator._calculate_site_packages_paths(pack_dir)
        else:
            logger.warning("Cannot calculate paths for unknown layout")
            return PathConfig([], [], [])

    @staticmethod
    def _calculate_wheel_paths(pack_dir: Path) -> PathConfig:
        """Calculate paths for wheel extraction layout."""
        torch_dir = pack_dir / 'torch'

        sys_path_entries = [pack_dir]

        if sys.platform == 'win32':
            dll_directories = [
                torch_dir / 'lib',
                pack_dir / 'bin',
                pack_dir / 'torchaudio' / 'lib'
            ]
            ld_library_paths = []
        else:
            dll_directories = []
            ld_library_paths = [torch_dir / 'lib']

        return PathConfig(sys_path_entries, dll_directories, ld_library_paths)

    @staticmethod
    def _calculate_site_packages_paths(pack_dir: Path) -> PathConfig:
        """Calculate paths for site-packages layout."""
        site_packages = pack_dir / 'site-packages'

        sys_path_entries = [site_packages]

        if sys.platform == 'win32':
            dll_directories = [
                pack_dir / 'bin',
                site_packages / 'torchaudio' / 'lib'
            ]
            ld_library_paths = []
        else:
            dll_directories = []
            ld_library_paths = [pack_dir / 'lib']

        return PathConfig(sys_path_entries, dll_directories, ld_library_paths)
