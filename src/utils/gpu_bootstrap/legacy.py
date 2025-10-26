"""
Legacy GPU Bootstrap Functions

Backward-compatible functions moved from gpu_bootstrap.py module.
These preserve the original API for existing call sites.
New code should use the staged facade in __init__.py.
"""

import os
import sys
import logging
from typing import Optional, Tuple, List
from pathlib import Path

logger = logging.getLogger(__name__)

# Module-level list to track DLL directories added for diagnostics (legacy)
ADDED_DLL_DIRS: List[str] = []


def _check_vcruntime() -> None:
    """
    Check for Microsoft Visual C++ Redistributable DLLs on Windows.
    Logs a warning with download URL if they're missing.
    """
    if sys.platform != 'win32':
        return

    try:
        import ctypes

        # Try to load critical VC++ runtime DLLs
        required_dlls = ['vcruntime140_1.dll', 'msvcp140.dll']
        missing_dlls = []

        for dll_name in required_dlls:
            try:
                ctypes.WinDLL(dll_name)
            except (OSError, FileNotFoundError):
                missing_dlls.append(dll_name)

        if missing_dlls:
            logger.warning(
                f"Microsoft Visual C++ Redistributable DLLs missing: {', '.join(missing_dlls)}. "
                "Install Visual Studio 2015-2022 (x64) runtime from: "
                "https://aka.ms/vs/17/release/vc_redist.x64.exe"
            )
    except Exception as e:
        logger.debug(f"Could not check VC++ runtime: {e}")


def enable_gpu_runtime(pack_dir: Path, config=None) -> bool:
    """
    Enable GPU Pack runtime by modifying sys.path and DLL search paths.
    Legacy function for backward compatibility.

    Args:
        pack_dir: Path to GPU Pack installation
        config: Optional config object for feature flag access

    Returns:
        True if successful, False otherwise
    """
    global ADDED_DLL_DIRS

    # Use staged GPU bootstrap
    from utils.gpu_bootstrap.orchestrator import enable_runtime
    logger.debug("Using GPU bootstrap")
    success, added_dirs = enable_runtime(pack_dir)
    if success:
        ADDED_DLL_DIRS = added_dirs
    return success


def validate_cuda_torch(expected_cuda: str = "12.1") -> Tuple[bool, str]:
    """
    Validate that PyTorch with CUDA is properly loaded and functional.

    Args:
        expected_cuda: Expected CUDA version (e.g., "12.1" for exact, "12" for any 12.x)

    Returns:
        Tuple of (success, error_message)
    """
    try:
        import torch

        # Check if CUDA is available
        if not torch.cuda.is_available():
            return (False, "torch.cuda.is_available() returned False")

        # Check CUDA version match
        torch_cuda_version = torch.version.cuda
        if torch_cuda_version is None:
            return (False, "torch.version.cuda is None")

        # Compare versions
        expected_parts = expected_cuda.split('.')
        actual_parts = torch_cuda_version.split('.')

        # If only major version specified (e.g., "12"), accept any minor version
        compare_parts = len(expected_parts)
        if expected_parts[:compare_parts] != actual_parts[:compare_parts]:
            return (False, f"CUDA version mismatch: expected {expected_cuda}.x, got {torch_cuda_version}")

        # Smoke test: create tensor on GPU and perform operation
        try:
            device = torch.device('cuda:0')
            x = torch.randn(100, 100, device=device)
            y = torch.randn(100, 100, device=device)
            z = torch.matmul(x, y)

            # Ensure computation completed
            torch.cuda.synchronize()

            if z.device.type != 'cuda':
                return (False, "Smoke test failed: result not on GPU")

        except Exception as e:
            return (False, f"Smoke test failed: {str(e)}")

        logger.info(f"CUDA validation successful: PyTorch {torch.__version__}, CUDA {torch_cuda_version}")
        return (True, "")

    except ImportError as e:
        return (False, f"Failed to import torch: {str(e)}")
    except Exception as e:
        return (False, f"Unexpected error during validation: {str(e)}")


def validate_torch_cpu() -> Tuple[bool, str]:
    """
    Validate that PyTorch is available for CPU-only operation.
    Does not check CUDA availability - only verifies torch can be imported.

    Returns:
        Tuple of (success, error_message)
    """
    try:
        import torch

        # Basic smoke test on CPU
        try:
            x = torch.randn(10, 10)
            y = torch.randn(10, 10)
            z = torch.matmul(x, y)

            if z.shape != (10, 10):
                return (False, "CPU smoke test failed: unexpected result shape")
        except Exception as e:
            return (False, f"CPU smoke test failed: {str(e)}")

        logger.info(f"CPU-only torch validation successful: PyTorch {torch.__version__}")
        return (True, "")

    except ImportError as e:
        return (False, f"Failed to import torch: {str(e)}")
    except Exception as e:
        return (False, f"Unexpected error during CPU validation: {str(e)}")


def _build_diagnostic_message(pack_dir: Optional[Path], flavor: str,
                              expected_cuda: str, error_msg: str) -> str:
    """Build detailed diagnostic message for GPU bootstrap failure."""
    lines = [f"GPU Pack validation failed: {error_msg}"]

    if pack_dir:
        lines.append(f"Pack path: {pack_dir}")
    lines.append(f"Pack flavor: {flavor}")
    lines.append(f"Expected CUDA: {expected_cuda}")

    if ADDED_DLL_DIRS:
        lines.append(f"DLL directories added: {', '.join(ADDED_DLL_DIRS)}")
    else:
        lines.append("No DLL directories were added")

    env_pack_dir = os.environ.get('USDXFIXGAP_GPU_PACK_DIR', 'Not set')
    lines.append(f"USDXFIXGAP_GPU_PACK_DIR: {env_pack_dir}")

    lines.append("Run --gpu-diagnostics for detailed information")

    return " | ".join(lines)


def bootstrap_and_maybe_enable_gpu(config) -> bool:
    """
    Orchestrate GPU Pack activation and validation.
    Legacy function for backward compatibility.

    Tries multiple approaches in order:
    1. Use GPU Pack if installed and enabled
    2. Auto-detect system-wide CUDA/PyTorch if available
    3. Fall back to CPU-only torch (if torch already importable)
    4. Fall back to no torch (FFmpeg only)

    Args:
        config: Application config object

    Returns:
        True if GPU is enabled and validated, False otherwise
    """
    try:
        # Check if user has explicitly disabled GPU
        gpu_opt_in = getattr(config, 'gpu_opt_in', None)
        if gpu_opt_in is False:
            logger.debug("GPU acceleration explicitly disabled (gpu_opt_in=false)")
            return False

        # Try GPU Pack first if configured
        pack_path = getattr(config, 'gpu_pack_path', '')
        pack_dir = None
        gpu_flavor = getattr(config, 'gpu_flavor', 'cu121')
        expected_cuda = "12.1" if gpu_flavor == "cu121" else "12.4"

        if pack_path:
            pack_dir = Path(pack_path)

            # Check if GPU Pack directory exists before trying to enable it
            if not pack_dir.exists():
                logger.debug(f"GPU Pack path configured but directory not found: {pack_dir}")
                logger.debug("Will attempt to detect system-wide CUDA installation...")
            else:
                # Enable GPU runtime
                if enable_gpu_runtime(pack_dir, config):
                    # Validate CUDA
                    success, error_msg = validate_cuda_torch(expected_cuda)

                    if success:
                        config.gpu_last_health = "healthy"
                        config.gpu_last_error = ""
                        config.save_config()
                        logger.info("GPU Pack activated successfully")
                        return True
                    else:
                        logger.warning(f"GPU Pack validation failed: {error_msg}")
                        # Compose detailed diagnostic message
                        diagnostic_info = _build_diagnostic_message(
                            pack_dir, gpu_flavor, expected_cuda, error_msg
                        )
                        config.gpu_last_error = diagnostic_info
                        config.gpu_last_health = "failed"
                        config.save_config()
                        # GPU Pack failed - don't try CPU fallback with broken GPU Pack in sys.path
                        return False
                else:
                    logger.debug(f"Could not enable GPU runtime from {pack_dir}, trying system CUDA...")

        # If GPU Pack not available or failed, try system-wide CUDA/PyTorch
        if gpu_opt_in is not False:  # None or True means try auto-detection
            logger.debug("Attempting to detect system-wide CUDA/PyTorch...")
            success, error_msg = validate_cuda_torch(expected_cuda="12")  # Accept CUDA 12.x

            if success:
                logger.info("System-wide CUDA/PyTorch detected and validated successfully")
                config.gpu_last_health = "healthy (system)"
                config.gpu_last_error = ""
                config.save_config()
                return True
            else:
                logger.debug(f"System CUDA not available or validation failed: {error_msg}")

        # No GPU available - final state
        logger.info("GPU not available. Application will use CPU-only providers or FFmpeg fallback.")
        config.gpu_last_health = "unavailable"
        config.gpu_last_error = ""
        config.save_config()
        return False

    except Exception as e:
        error_msg = f"Unexpected error during GPU bootstrap: {str(e)}"
        logger.error(error_msg, exc_info=True)
        try:
            config.gpu_last_health = "failed"
            config.gpu_last_error = error_msg
            config.save_config()
        except Exception:  # nosec - intentional catch-all for config save
            pass
        return False


def child_process_min_bootstrap():
    """
    Minimal bootstrap for child processes.
    Replicates GPU Pack activation using environment variable.
    """
    pack_dir_str = os.environ.get('USDXFIXGAP_GPU_PACK_DIR')
    if pack_dir_str:
        pack_dir = Path(pack_dir_str)
        if pack_dir.exists():
            enable_gpu_runtime(pack_dir)
            logger.debug(f"Child process: GPU Pack activated from {pack_dir}")