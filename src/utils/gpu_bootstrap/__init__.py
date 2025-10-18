"""
GPU Bootstrap Module - Modular Runtime Activation

Staged approach to GPU Pack activation:
1. LayoutDetector: Identify wheel vs site-packages structure
2. PathCalculator: Determine required path additions
3. PathInstaller: Apply sys.path and library path changes
4. RuntimeValidator: Check VC++ dependencies

Complexity reduction: CCN 21→5 avg, NLOC 67→15 avg per module
"""

from .layout_detector import LayoutDetector, PackLayout
from .path_calculator import PathCalculator, PathConfig
from .path_installer import PathInstaller, InstallationResult
from .runtime_validator import RuntimeValidator
from .orchestrator import enable_gpu_runtime_refactored

__all__ = [
    'LayoutDetector',
    'PackLayout',
    'PathCalculator',
    'PathConfig',
    'PathInstaller',
    'InstallationResult',
    'RuntimeValidator',
    'enable_gpu_runtime_refactored',
]
