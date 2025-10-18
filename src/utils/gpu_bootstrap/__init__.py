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

# Import legacy bootstrap function from the .py file (not this package)
import importlib.util
from pathlib import Path

_legacy_module_path = Path(__file__).parent.parent / "gpu_bootstrap.py"
_spec = importlib.util.spec_from_file_location("_gpu_bootstrap_legacy", _legacy_module_path)
if _spec and _spec.loader:
    _legacy_module = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_legacy_module)

    # Re-export legacy functions (all public functions from gpu_bootstrap.py)
    bootstrap_and_maybe_enable_gpu = _legacy_module.bootstrap_and_maybe_enable_gpu
    enable_gpu_runtime = _legacy_module.enable_gpu_runtime
    ADDED_DLL_DIRS = _legacy_module.ADDED_DLL_DIRS
    capability_probe = _legacy_module.capability_probe
    validate_cuda_torch = _legacy_module.validate_cuda_torch
    validate_torch_cpu = _legacy_module.validate_torch_cpu
    child_process_min_bootstrap = _legacy_module.child_process_min_bootstrap
else:
    raise ImportError(f"Could not load legacy gpu_bootstrap module from {_legacy_module_path}")

__all__ = [
    # Refactored modular components (Phase 4)
    'LayoutDetector',
    'PackLayout',
    'PathCalculator',
    'PathConfig',
    'PathInstaller',
    'InstallationResult',
    'RuntimeValidator',
    'enable_gpu_runtime_refactored',
    # Legacy functions (backward compatibility)
    'bootstrap_and_maybe_enable_gpu',
    'enable_gpu_runtime',
    'capability_probe',
    'validate_cuda_torch',
    'validate_torch_cpu',
    'child_process_min_bootstrap',
    'ADDED_DLL_DIRS',
]
