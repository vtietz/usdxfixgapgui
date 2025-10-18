"""
GPU Bootstrap Module - Clean Typed API

Provides:
- Staged facade: enable() returning BootstrapResult
- Legacy compatibility: enable_gpu_runtime, bootstrap_and_maybe_enable_gpu
- Modular components: LayoutDetector, PathCalculator, LibPathManager
- Typed results: PathConfig, InstallationResult, ValidationResult, BootstrapResult

No global mutable state; explicit imports only.
"""

# Refactored modular components
from .layout_detector import LayoutDetector, PackLayout
from .path_calculator import PathCalculator, PathConfig
from .path_installer import PathInstaller, InstallationResult as PathInstallerResult
from .runtime_validator import RuntimeValidator
from .orchestrator import enable_runtime

# New typed API
from .types import (
    PathConfig as TypedPathConfig,
    InstallationResult,
    ValidationResult,
    BootstrapResult
)
from .lib_path_manager import LibPathManager
from .facade import enable, enable_legacy, bootstrap_and_maybe_enable_gpu_legacy

# Legacy functions for backward compatibility
from .legacy import (
    bootstrap_and_maybe_enable_gpu,
    enable_gpu_runtime,
    validate_cuda_torch,
    validate_torch_cpu,
    child_process_min_bootstrap,
    ADDED_DLL_DIRS
)

# Import capability_probe from parent gpu_bootstrap.py module
# (This was not moved to legacy as it's a utility function)
from pathlib import Path as _Path
_parent_module = _Path(__file__).parent.parent / "gpu_bootstrap.py"
if _parent_module.exists():
    import importlib.util as _importlib_util
    _spec = _importlib_util.spec_from_file_location("_gpu_bootstrap_parent", _parent_module)
    if _spec and _spec.loader:
        _parent = _importlib_util.module_from_spec(_spec)
        _spec.loader.exec_module(_parent)
        capability_probe = _parent.capability_probe
        resolve_pack_dir = _parent.resolve_pack_dir
        probe_nvml = _parent.probe_nvml
        probe_nvidia_smi = _parent.probe_nvidia_smi
        find_installed_pack_dirs = _parent.find_installed_pack_dirs
        select_best_existing_pack = _parent.select_best_existing_pack
        auto_recover_gpu_pack_config = _parent.auto_recover_gpu_pack_config
    else:
        capability_probe = None
        resolve_pack_dir = None
        probe_nvml = None
        probe_nvidia_smi = None
        find_installed_pack_dirs = None
        select_best_existing_pack = None
        auto_recover_gpu_pack_config = None
else:
    capability_probe = None
    resolve_pack_dir = None
    probe_nvml = None
    probe_nvidia_smi = None
    find_installed_pack_dirs = None
    select_best_existing_pack = None
    auto_recover_gpu_pack_config = None

__all__ = [
    # Staged facade API (primary interface)
    'enable',
    'enable_legacy',
    'bootstrap_and_maybe_enable_gpu_legacy',
    # Typed results
    'BootstrapResult',
    'InstallationResult',
    'ValidationResult',
    'TypedPathConfig',
    # Modular components
    'LayoutDetector',
    'PackLayout',
    'PathCalculator',
    'PathConfig',
    'PathInstaller',
    'PathInstallerResult',
    'RuntimeValidator',
    'LibPathManager',
    'enable_runtime',
    # Legacy functions (backward compatibility)
    'bootstrap_and_maybe_enable_gpu',
    'enable_gpu_runtime',
    'validate_cuda_torch',
    'validate_torch_cpu',
    'child_process_min_bootstrap',
    'ADDED_DLL_DIRS',
    # Utility functions from parent module
    'capability_probe',
    'resolve_pack_dir',
    'probe_nvml',
    'probe_nvidia_smi',
    'find_installed_pack_dirs',
    'select_best_existing_pack',
    'auto_recover_gpu_pack_config',
]
