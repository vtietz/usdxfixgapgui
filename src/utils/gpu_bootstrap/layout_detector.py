"""
Layout Detection - Identify GPU Pack Structure

Determines whether GPU Pack uses wheel extraction or traditional install layout.
"""

import logging
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class PackLayout(Enum):
    """GPU Pack installation layout types."""
    WHEEL_EXTRACTION = "wheel"  # torch/ at root
    SITE_PACKAGES = "site_packages"  # site-packages/ subdirectory
    UNKNOWN = "unknown"


class LayoutDetector:
    """Detect GPU Pack directory structure."""

    @staticmethod
    def detect(pack_dir: Path) -> PackLayout:
        """
        Detect GPU Pack layout type.

        Args:
            pack_dir: Root directory of GPU Pack installation

        Returns:
            PackLayout enum indicating structure type
        """
        if not pack_dir.exists():
            logger.debug(f"Pack directory does not exist: {pack_dir}")
            return PackLayout.UNKNOWN

        torch_dir = pack_dir / 'torch'
        site_packages = pack_dir / 'site-packages'

        if torch_dir.exists():
            logger.debug("Detected wheel extraction layout (torch/ at root)")
            return PackLayout.WHEEL_EXTRACTION

        if site_packages.exists():
            logger.debug("Detected site-packages layout")
            return PackLayout.SITE_PACKAGES

        logger.warning(f"Unknown layout: neither torch/ nor site-packages/ found in {pack_dir}")
        return PackLayout.UNKNOWN
