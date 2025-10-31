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
from .types import PathConfig as TypedPathConfig, InstallationResult, ValidationResult, BootstrapResult
from .lib_path_manager import LibPathManager
from .facade import enable, enable_legacy, bootstrap_and_maybe_enable_gpu_legacy

# Legacy functions for backward compatibility
from .legacy import (
    bootstrap_and_maybe_enable_gpu,
    enable_gpu_runtime,
    validate_cuda_torch,
    validate_torch_cpu,
    child_process_min_bootstrap,
    ADDED_DLL_DIRS,
)

# Import utility functions
# These are now in the submodule and work in both dev and frozen contexts
from .capability_utils import capability_probe, probe_nvml, probe_nvidia_smi
from .system_pytorch_detector import detect_system_pytorch_cuda
from .pack_utils import (
    resolve_pack_dir,
    find_installed_pack_dirs,
    select_best_existing_pack,
    auto_recover_gpu_pack_config,
)

__all__ = [
    # Staged facade API (primary interface)
    "enable",
    "enable_legacy",
    "bootstrap_and_maybe_enable_gpu_legacy",
    # Typed results
    "BootstrapResult",
    "InstallationResult",
    "ValidationResult",
    "TypedPathConfig",
    # Modular components
    "LayoutDetector",
    "PackLayout",
    "PathCalculator",
    "PathConfig",
    "PathInstaller",
    "PathInstallerResult",
    "RuntimeValidator",
    "LibPathManager",
    "enable_runtime",
    # Legacy functions (backward compatibility)
    "bootstrap_and_maybe_enable_gpu",
    "enable_gpu_runtime",
    "validate_cuda_torch",
    "validate_torch_cpu",
    "child_process_min_bootstrap",
    "ADDED_DLL_DIRS",
    # Utility functions from parent module
    "capability_probe",
    "resolve_pack_dir",
    "probe_nvml",
    "probe_nvidia_smi",
    "find_installed_pack_dirs",
    "select_best_existing_pack",
    "auto_recover_gpu_pack_config",
    "detect_system_pytorch_cuda",
]
