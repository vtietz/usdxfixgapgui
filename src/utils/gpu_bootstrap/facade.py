"""
Staged GPU Bootstrap Facade

Single entry point for GPU Pack activation using typed results.
Eliminates global mutable state and provides clear phase separation.
"""

import os
import logging
from pathlib import Path
from typing import Tuple
from .types import BootstrapResult, ValidationResult
from .layout_detector import LayoutDetector
from .path_calculator import PathCalculator
from .lib_path_manager import LibPathManager

logger = logging.getLogger(__name__)


def validate_cuda_torch(expected_cuda: str = "12") -> Tuple[bool, str]:
    """Validate torch.cuda availability and version."""
    try:
        import torch

        if not torch.cuda.is_available():
            return False, "torch.cuda.is_available() returned False"
        cuda_version = torch.version.cuda
        if not cuda_version:
            return False, "CUDA version is None"
        if not cuda_version.startswith(expected_cuda.split(".")[0]):
            return False, f"CUDA version mismatch: expected {expected_cuda}, got {cuda_version}"
        # Smoke test
        device = torch.device("cuda:0")
        test_tensor = torch.zeros(10, 10, device=device)
        if test_tensor.sum().item() != 0.0:
            return False, "CUDA smoke test failed"
        return True, ""
    except Exception as e:
        return False, f"Failed to validate CUDA: {e}"


def validate_torch_cpu() -> Tuple[bool, str]:
    """Validate torch CPU-only mode."""
    try:
        import torch

        # CPU smoke test
        test_tensor = torch.zeros(10, 10)
        if test_tensor.sum().item() != 0.0:
            return False, "CPU smoke test failed"
        return True, ""
    except Exception as e:
        return False, f"Failed to validate torch CPU: {e}"


def _check_vcruntime() -> None:
    """Check for VC++ runtime DLLs on Windows."""
    import sys

    if sys.platform != "win32":
        return
    try:
        import ctypes

        required_dlls = ["vcruntime140_1.dll", "msvcp140.dll"]
        missing_dlls = []
        for dll_name in required_dlls:
            try:
                ctypes.WinDLL(dll_name)
            except (OSError, FileNotFoundError):
                missing_dlls.append(dll_name)
        if missing_dlls:
            logger.warning(
                f"Microsoft Visual C++ Redistributable DLLs missing: {', '.join(missing_dlls)}. "
                "Install from: https://aka.ms/vs/17/release/vc_redist.x64.exe"
            )
    except Exception as e:
        logger.debug(f"Could not check VC++ runtime: {e}")


def enable(pack_dir: Path, expected_cuda: str = "12.1") -> BootstrapResult:
    """
    Enable GPU Pack with staged activation and typed results.

    Phases:
    1. Detect layout (wheel extraction vs site-packages)
    2. Calculate required path changes
    3. Apply platform-specific library and sys.path changes
    4. Validate CUDA, fallback to CPU if needed
    5. Set USDXFIXGAP_GPU_PACK_DIR on success

    Args:
        pack_dir: Path to GPU Pack installation
        expected_cuda: Expected CUDA version (e.g., "12.1" or "12" for any 12.x)

    Returns:
        BootstrapResult with success status and detailed phase info
    """
    diagnostics = []

    # Phase 1: Detect layout
    detector = LayoutDetector()
    layout = detector.detect(pack_dir)

    if layout == "unknown":
        diagnostics.append(f"Unknown pack layout at {pack_dir}")
        return BootstrapResult(success=False, mode="none", diagnostics=diagnostics, pack_dir=pack_dir)

    diagnostics.append(f"Detected layout: {layout}")

    # Phase 2: Calculate paths
    calculator = PathCalculator()
    path_config = calculator.calculate(pack_dir, layout)

    if not path_config.sys_path_entries and not path_config.dll_directories and not path_config.ld_library_paths:
        diagnostics.append("No paths to install")
        return BootstrapResult(success=False, mode="none", diagnostics=diagnostics, pack_dir=pack_dir)

    # Phase 3: Install paths
    manager = LibPathManager()
    installation = manager.install_paths(
        dll_dirs=path_config.dll_directories,
        sys_paths=path_config.sys_path_entries,
        ld_paths=path_config.ld_library_paths,
    )

    if not installation.success:
        diagnostics.append(f"Path installation failed: {installation.error_message}")
        return BootstrapResult(
            success=False, mode="none", installation=installation, diagnostics=diagnostics, pack_dir=pack_dir
        )

    diagnostics.extend(installation.messages)

    # Check VC++ runtime on Windows
    import sys

    if sys.platform == "win32":
        _check_vcruntime()

    # Phase 4: Validate CUDA
    cuda_success, cuda_error = validate_cuda_torch(expected_cuda)

    if cuda_success:
        # CUDA validation successful
        try:
            import torch

            torch_version = torch.__version__
            cuda_version = torch.version.cuda
        except ImportError:
            torch_version = None
            cuda_version = None

        validation = ValidationResult(success=True, mode="cuda", torch_version=torch_version, cuda_version=cuda_version)

        # Set environment variable for child processes
        os.environ["USDXFIXGAP_GPU_PACK_DIR"] = str(pack_dir)

        return BootstrapResult(
            success=True,
            mode="cuda",
            installation=installation,
            validation=validation,
            diagnostics=diagnostics,
            pack_dir=pack_dir,
        )

    # CUDA failed - try CPU fallback
    diagnostics.append(f"CUDA validation failed: {cuda_error}")
    cpu_success, cpu_error = validate_torch_cpu()

    if cpu_success:
        # CPU validation successful
        try:
            import torch

            torch_version = torch.__version__
        except ImportError:
            torch_version = None

        validation = ValidationResult(
            success=True, mode="cpu", torch_version=torch_version, error_message=f"CUDA unavailable: {cuda_error}"
        )

        # Set environment variable for child processes
        os.environ["USDXFIXGAP_GPU_PACK_DIR"] = str(pack_dir)

        return BootstrapResult(
            success=True,
            mode="cpu",
            installation=installation,
            validation=validation,
            diagnostics=diagnostics,
            pack_dir=pack_dir,
        )

    # Both CUDA and CPU failed
    diagnostics.append(f"CPU validation also failed: {cpu_error}")

    validation = ValidationResult(
        success=False,
        mode="none",
        error_message=f"CUDA: {cuda_error} | CPU: {cpu_error}",
        diagnostics=[cuda_error, cpu_error],
    )

    return BootstrapResult(
        success=False,
        mode="none",
        installation=installation,
        validation=validation,
        diagnostics=diagnostics,
        pack_dir=pack_dir,
    )
