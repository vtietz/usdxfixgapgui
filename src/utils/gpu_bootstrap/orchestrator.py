"""
GPU Bootstrap Orchestrator - Staged Runtime Activation

Coordinates layout detection, path calculation, and installation phases.
"""

import os
import logging
from pathlib import Path
from typing import List

from .layout_detector import LayoutDetector, PackLayout
from .path_calculator import PathCalculator
from .path_installer import PathInstaller
from .runtime_validator import RuntimeValidator

logger = logging.getLogger(__name__)


def enable_runtime(pack_dir: Path) -> tuple[bool, List[str]]:
    """
    Enable GPU Pack runtime using staged approach.

    Phases:
    1. Detect layout (wheel vs site-packages)
    2. Calculate required path additions
    3. Install paths into runtime
    4. Validate runtime dependencies

    Args:
        pack_dir: Path to GPU Pack installation

    Returns:
        Tuple of (success, list of DLL directories added)
    """
    # Phase 1: Detect layout
    layout = LayoutDetector.detect(pack_dir)
    if layout == PackLayout.UNKNOWN:
        logger.debug(f"Cannot enable GPU runtime: unknown layout in {pack_dir}")
        return False, []

    # Phase 2: Calculate paths
    path_config = PathCalculator.calculate(pack_dir, layout)

    # Phase 3: Install paths
    result = PathInstaller.install(path_config)
    if not result.success:
        logger.warning(f"Path installation failed: {result.error_message}")
        return False, []

    # Phase 4: Validate runtime
    RuntimeValidator.check_vcruntime()

    # Set environment variable for child processes
    os.environ['USDXFIXGAP_GPU_PACK_DIR'] = str(pack_dir)

    return True, result.added_dll_dirs
