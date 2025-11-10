"""
GPU Bootstrap Module - Clean API

Main exports:
- bootstrap_and_maybe_enable_gpu(): Main entry point
- enable_gpu_runtime(): Enable GPU Pack paths
- validate_cuda_torch(), validate_torchaudio(): Validation functions
- capability_probe(): Hardware detection
- ADDED_DLL_DIRS: Diagnostic tracking

Typed facade:
- enable(): Returns BootstrapResult
"""

# Main API from bootstrap module
from .bootstrap import (
    bootstrap_and_maybe_enable_gpu,
    enable_gpu_runtime,
    ADDED_DLL_DIRS,
)
from .validation import validate_cuda_torch, validate_torchaudio

# Staged facade API
from .facade import enable

# Typed results
from .types import (
    PathConfig as TypedPathConfig,
    InstallationResult,
    ValidationResult,
    BootstrapResult,
)

# Modular components
from .layout_detector import LayoutDetector, PackLayout
from .path_calculator import PathCalculator, PathConfig
from .path_installer import PathInstaller, InstallationResult as PathInstallerResult
from .runtime_validator import RuntimeValidator
from .lib_path_manager import LibPathManager
from .orchestrator import enable_runtime

# Utility functions
from .capability_utils import capability_probe, probe_nvml, probe_nvidia_smi
from .system_pytorch_detector import detect_system_pytorch_cuda
from .pack_utils import (
    resolve_pack_dir,
    find_installed_pack_dirs,
    select_best_existing_pack,
    auto_recover_gpu_pack_config,
    detect_existing_gpu_pack,
    activate_existing_gpu_pack,
)

__all__ = [
    # Main API
    "bootstrap_and_maybe_enable_gpu",
    "enable_gpu_runtime",
    "validate_cuda_torch",
    "validate_torchaudio",
    "ADDED_DLL_DIRS",
    # Staged facade API
    "enable",
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
    # Utility functions
    "capability_probe",
    "resolve_pack_dir",
    "probe_nvml",
    "probe_nvidia_smi",
    "find_installed_pack_dirs",
    "select_best_existing_pack",
    "auto_recover_gpu_pack_config",
    "detect_existing_gpu_pack",
    "activate_existing_gpu_pack",
    "detect_system_pytorch_cuda",
]
