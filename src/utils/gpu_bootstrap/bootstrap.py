"""
GPU Bootstrap Main Logic

Orchestrates GPU Pack activation, system PyTorch detection, and validation.
"""

import sys
import logging
from pathlib import Path
from typing import Tuple, List

from .orchestrator import enable_runtime
from .system_pytorch_detector import detect_system_pytorch_cuda
from .pack_utils import auto_recover_gpu_pack_config

logger = logging.getLogger(__name__)

# Module-level list to track DLL directories for diagnostics
ADDED_DLL_DIRS: List[str] = []


def enable_gpu_runtime(pack_dir: Path, config=None) -> bool:
    """
    Enable GPU Pack runtime by modifying sys.path and DLL search paths.

    Args:
        pack_dir: Path to GPU Pack installation
        config: Optional config object (unused, kept for compatibility)

    Returns:
        True if successful, False otherwise
    """
    global ADDED_DLL_DIRS

    logger.debug("Enabling GPU runtime")
    success, added_dirs = enable_runtime(pack_dir)
    if success:
        ADDED_DLL_DIRS = added_dirs
    return success


def validate_cuda_torch(expected_cuda: str = "12") -> Tuple[bool, str]:
    """
    Validate that torch.cuda is available and matches expected CUDA version.

    Args:
        expected_cuda: Expected CUDA version (e.g., "12.1" or "12" for any 12.x)

    Returns:
        Tuple of (success, error_message)
    """
    try:
        import torch

        if not torch.cuda.is_available():
            return False, "torch.cuda.is_available() returned False"

        cuda_version = torch.version.cuda
        if not cuda_version:
            return False, "CUDA version is None"

        # Check version match (allow "12" to match "12.1", "12.4", etc.)
        if not cuda_version.startswith(expected_cuda.split(".")[0]):
            return False, f"CUDA version mismatch: expected {expected_cuda}, got {cuda_version}"

        # Run smoke test
        try:
            device = torch.device("cuda:0")
            test_tensor = torch.zeros(10, 10, device=device)
            result = test_tensor.sum().item()
            if result != 0.0:
                return False, f"CUDA smoke test failed: expected 0.0, got {result}"
        except Exception as e:
            return False, f"CUDA smoke test error: {e}"

        return True, ""

    except Exception as e:
        return False, f"Failed to validate CUDA: {e}"


def validate_torchaudio() -> Tuple[bool, str]:
    """
    Validate that torchaudio can be imported and its DLLs load correctly.

    This is critical for MDX gap detection which uses torchaudio spectrogram.

    Returns:
        Tuple of (success, error_message)
    """
    try:
        import torchaudio

        # Try to access a function that requires DLL loading
        _ = torchaudio.transforms.Spectrogram

        return True, ""

    except Exception as e:
        return False, f"torchaudio import/DLL error: {e}"


def bootstrap_and_maybe_enable_gpu(config) -> bool:
    """
    Main GPU bootstrap entry point - orchestrates GPU Pack activation and validation.

    Workflow:
    1. Skip if GPU explicitly disabled
    2. **Add GPU Pack to sys.path FIRST** if configured (before any torch imports)
    3. Try system PyTorch+CUDA (only if prefer_system_pytorch=true AND not frozen)
    4. Validate CUDA and torchaudio
    5. Fall back to CPU if GPU Pack fails

    Args:
        config: Application config object

    Returns:
        True if GPU is enabled and validated, False otherwise
    """
    global ADDED_DLL_DIRS

    try:
        # Auto-recover GPU Pack config if pack exists on disk but config is empty
        auto_recover_gpu_pack_config(config)

        # Check if user has explicitly disabled GPU
        gpu_opt_in = getattr(config, "gpu_opt_in", None)
        if gpu_opt_in is False:
            logger.debug("GPU acceleration explicitly disabled (gpu_opt_in=false)")
            return False

        # CRITICAL: Add GPU Pack to sys.path IMMEDIATELY if configured
        # This must happen BEFORE any torch imports (including system check)
        # to ensure GPU Pack's torch loads instead of venv's torch
        pack_path = getattr(config, "gpu_pack_path", "")
        pack_dir = None
        gpu_flavor = getattr(config, "gpu_flavor", "cu121")
        expected_cuda = "12.1" if gpu_flavor == "cu121" else "12.4"

        if pack_path:
            pack_dir = Path(pack_path)
            if pack_dir.exists():
                logger.debug(f"GPU Pack found at {pack_dir} - adding to sys.path BEFORE any imports")
                enable_gpu_runtime(pack_dir, config)
            else:
                logger.debug(f"GPU Pack path configured but directory not found: {pack_dir}")

        # STEP 1: Try system PyTorch+CUDA (ONLY if explicitly enabled AND not frozen)
        # Note: GPU Pack paths are already in sys.path, so if GPU Pack exists,
        # its torch will be imported here instead of venv's torch
        prefer_system = getattr(config, "prefer_system_pytorch", False)
        is_frozen = getattr(sys, "frozen", False)

        logger.debug(f"GPU bootstrap: prefer_system={prefer_system}, is_frozen={is_frozen}, gpu_opt_in={gpu_opt_in}")

        if prefer_system and gpu_opt_in is not False and not is_frozen:
            logger.debug("Checking for system PyTorch with CUDA...")
            system_pytorch = detect_system_pytorch_cuda()

            if system_pytorch:
                logger.info(
                    f"Found system PyTorch {system_pytorch['torch_version']} "
                    f"with CUDA {system_pytorch['cuda_version']} "
                    f"({system_pytorch['device_name']})"
                )

                # Validate it works properly
                try:
                    success, error_msg = validate_cuda_torch(expected_cuda="12")  # Accept CUDA 12.x
                    if success:
                        logger.info("✓ System PyTorch validated successfully - using it instead of GPU Pack")
                        config.gpu_last_health = "healthy (system)"
                        config.gpu_last_error = ""
                        config.save_config()
                        return True
                    else:
                        logger.warning(f"System PyTorch validation failed: {error_msg}")
                        logger.info("Falling back to GPU Pack...")
                except Exception as e:
                    logger.warning(f"System PyTorch validation error: {e}")
                    logger.info("Falling back to GPU Pack...")
            else:
                logger.debug("System PyTorch with CUDA not found, trying GPU Pack...")
        elif is_frozen:
            logger.debug("Running in frozen exe - skipping system PyTorch check to allow GPU Pack activation")

        # STEP 2: Validate GPU Pack (paths already added above)
        if not pack_dir or not pack_dir.exists():
            logger.debug("No GPU Pack configured or pack directory not found")
            return False

        # Validate CUDA first
        cuda_success, cuda_error = validate_cuda_torch(expected_cuda)

        if cuda_success:
            # CUDA works - now validate torchaudio (critical for MDX gap detection)
            audio_success, audio_error = validate_torchaudio()

            if audio_success:
                config.gpu_last_health = "healthy"
                config.gpu_last_error = ""
                config.save_config()
                logger.info("GPU Pack activated successfully (PyTorch + torchaudio validated)")
                return True
            else:
                # torchaudio broken - this breaks gap detection!
                logger.error(f"GPU Pack torchaudio validation failed: {audio_error}")
                diagnostic_info = (
                    f"GPU Pack is broken (torchaudio DLL error).\n\n"
                    f"Location: {pack_dir}\n"
                    f"Error: {audio_error}\n\n"
                    f"SOLUTION: Delete the GPU Pack folder and restart to download a fresh copy."
                )
                config.gpu_last_error = diagnostic_info
                config.gpu_last_health = "failed"
                config.save_config()
                return False
        else:
            # CUDA validation failed - add torch import source diagnostics
            logger.warning(f"GPU Pack validation failed: {cuda_error}")
            
            # Diagnostic: where did torch come from?
            torch_source = "unknown"
            torch_cuda_version = "unknown"
            try:
                import torch
                torch_source = getattr(torch, "__file__", "unknown")
                torch_cuda_version = getattr(torch.version, "cuda", "None")
            except Exception as import_err:
                torch_source = f"import failed: {import_err}"
            
            diagnostic_info = (
                f"GPU Pack validation failed: {cuda_error} | "
                f"Pack path: {pack_dir} | "
                f"Pack flavor: {gpu_flavor} | "
                f"Expected CUDA: {expected_cuda} | "
                f"DLL directories added: {', '.join(ADDED_DLL_DIRS)} | "
                f"USDXFIXGAP_GPU_PACK_DIR: {pack_dir} | "
                f"torch.__file__: {torch_source} | "
                f"torch.version.cuda: {torch_cuda_version}"
            )
            config.gpu_last_error = diagnostic_info
            config.gpu_last_health = "failed"
            config.save_config()
            return False

        return False

    except Exception as e:
        logger.error(f"GPU bootstrap error: {e}", exc_info=True)
        return False
