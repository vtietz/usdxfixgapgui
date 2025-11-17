"""
GPU Bootstrap Main Logic

Orchestrates GPU Pack activation, system PyTorch detection, and validation.
"""

import sys
import logging
from pathlib import Path
from typing import List

from .orchestrator import enable_runtime
from .system_pytorch_detector import detect_system_pytorch_cuda
from .pack_utils import auto_recover_gpu_pack_config
from .types import GPUStatus
from .validation import validate_cuda_torch, validate_torchaudio

logger = logging.getLogger(__name__)

# Module-level list to track DLL directories for diagnostics
ADDED_DLL_DIRS: List[str] = []


# ---- Small helpers to keep control-flow flat and readable ----


def _is_gpu_disabled(config) -> bool:
    """Return True if user explicitly disabled GPU in config."""
    return getattr(config, "gpu_opt_in", None) is False


def _expected_cuda_from_flavor(gpu_flavor: str) -> str:
    """Derive expected CUDA version from flavor name.

    Supports patterns like cu121, cu124, future cuXYZ where XYZ = major minor digits.
    Returns major.minor (e.g. cu121 -> 12.1, cu124 -> 12.4).
    Falls back to '12' (broad match) if parsing fails.
    """
    if not gpu_flavor or not gpu_flavor.startswith("cu"):
        return "12"  # broad match
    digits = gpu_flavor[2:]
    if len(digits) < 3 or not digits.isdigit():
        return "12"  # fallback broad match
    # first two digits = major, last digit = minor (cu121 -> 12.1)
    major = digits[0:2]
    minor = digits[2]
    return f"{major}.{minor}"


def _torch_from_dir(module_name: str, base_dir: Path) -> bool:
    """Check if an already-imported module originates from a given directory."""
    try:
        import sys as _sys

        m = _sys.modules.get(module_name)
        src = getattr(m, "__file__", None) if m else None
        return bool(src and str(base_dir) in src)
    except Exception:
        return False


def _add_pack_and_swap_torch_if_needed(pack_dir: Path) -> None:
    """Ensure GPU Pack is on sys.path so that subsequent torch imports resolve there.

    Safety change: If torch is already imported (likely CPU build), we DO NOT purge and re-import
    to avoid duplicate native registration errors (e.g., 'Key already registered: C10').
    Instead we log a diagnostic and allow CPU fallback; user can restart with clean state if needed.
    """
    try:
        enable_gpu_runtime(pack_dir, None)

        import sys as _sys

        if "torch" in _sys.modules:
            if _torch_from_dir("torch", pack_dir):
                logger.debug("torch already imported from GPU Pack path; no action needed")
            else:
                logger.info(
                    "torch pre-imported from non-GPU location; "
                    "skipping destructive swap to avoid native registration conflicts; "
                    "CPU fallback may occur"
                )
        # If torch not yet imported, normal import later will pick GPU Pack.
    except Exception as swap_err:
        logger.debug(f"GPU Pack path addition encountered error (continuing with CPU fallback if needed): {swap_err}")


def _try_system_pytorch_if_enabled(config, gpu_opt_in) -> bool:
    """Optionally try system PyTorch with CUDA; return True if validated and used."""
    prefer_system = getattr(config, "prefer_system_pytorch", False)
    is_frozen = getattr(sys, "frozen", False)
    logger.debug(f"GPU bootstrap: prefer_system={prefer_system}, is_frozen={is_frozen}, gpu_opt_in={gpu_opt_in}")

    if not (prefer_system and gpu_opt_in is not False and not is_frozen):
        if is_frozen:
            logger.debug("Running in frozen exe - skipping system PyTorch check to allow GPU Pack activation")
        return False

    logger.debug("Checking for system PyTorch with CUDA...")
    system_pytorch = detect_system_pytorch_cuda()
    if not system_pytorch:
        logger.debug("System PyTorch with CUDA not found, trying GPU Pack...")
        return False

    logger.info(
        f"Found system PyTorch {system_pytorch['torch_version']} "
        f"with CUDA {system_pytorch['cuda_version']} "
        f"({system_pytorch['device_name']})"
    )
    try:
        success, error_msg = validate_cuda_torch(expected_cuda="12")  # Accept CUDA 12.x
        if success:
            logger.info("✓ System PyTorch validated successfully - using it instead of GPU Pack")
            config.gpu_last_health = "healthy (system)"
            config.gpu_last_error = ""
            config.save_config()
            return True
        logger.warning(f"System PyTorch validation failed: {error_msg}")
        logger.info("Falling back to GPU Pack...")
        return False
    except Exception as e:
        logger.warning(f"System PyTorch validation error: {e}")
        logger.info("Falling back to GPU Pack...")
        return False


def _validate_pack_and_update_config(config, pack_dir: Path, gpu_flavor: str, expected_cuda: str) -> bool:
    """Validate CUDA and torchaudio from GPU Pack; update config accordingly."""
    cuda_success, cuda_error = validate_cuda_torch(expected_cuda)
    if cuda_success:
        audio_success, audio_error = validate_torchaudio()
        if audio_success:
            config.gpu_last_health = "healthy"
            config.gpu_last_error = ""
            config.save_config()
            logger.info("GPU Pack activated successfully (PyTorch + torchaudio validated)")
            return True
        logger.error(f"GPU Pack torchaudio validation failed: {audio_error}")
        diagnostic_info = (
            f"GPU Pack is broken (torchaudio DLL error).\n\n"
            f"Location: {pack_dir}\n"
            f"Error: {audio_error}\n\n"
            f"SOLUTION: Delete the GPU Pack folder and restart to download a fresh copy."
        )
        config.gpu_last_error = diagnostic_info
        config.gpu_last_health = "failed"
        config.gpu_opt_in = False  # Disable to prevent boot loop
        config.save_config()
        logger.warning("GPU Pack disabled due to validation failure - user can re-activate from startup dialog")
        return False

    # CUDA validation failed - add torch import source diagnostics
    logger.warning(f"GPU Pack validation failed: {cuda_error}")
    torch_source = "unknown"
    torch_cuda_version = "unknown"
    torch_from_venv = False
    try:
        import torch

        torch_source = getattr(torch, "__file__", "unknown")
        torch_cuda_version = getattr(torch.version, "cuda", "None")
        # Check if torch was imported from venv (not GPU Pack)
        torch_from_venv = ".venv" in torch_source or "site-packages" in torch_source
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

    # Only disable GPU opt-in if this is actual corruption, not just pre-imported CPU torch
    # If torch was pre-imported from venv, keep gpu_opt_in=true so it works on next clean start
    if not torch_from_venv:
        config.gpu_opt_in = False  # Disable to prevent boot loop
        logger.warning("GPU Pack disabled due to validation failure - user can re-activate from startup dialog")
    else:
        logger.info("GPU Pack validation failed because CPU torch was pre-imported - keeping gpu_opt_in=true for next restart")

    config.save_config()
    return False


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


# moved to validation.py


def _to_gpu_status_from_context(source: str, pack_dir: Path | None, error: str | None = None) -> GPUStatus:
    """Build a GPUStatus snapshot from current torch context."""
    torch_version = None
    cuda_version = None
    cuda_available = False
    try:
        import torch

        torch_version = getattr(torch, "__version__", None)
        cuda_version = getattr(torch.version, "cuda", None)
        cuda_available = bool(getattr(torch.cuda, "is_available", lambda: False)())
    except Exception:
        pass

    enabled = bool(cuda_available)
    return GPUStatus(
        enabled=enabled,
        source=source,
        cuda_available=cuda_available,
        torch_version=torch_version,
        cuda_version=cuda_version,
        error=error,
        pack_dir=pack_dir,
    )


def bootstrap_gpu(config) -> GPUStatus:
    """
    Centralized GPU bootstrap returning a GPUStatus.

    Preserves existing behavior: GPU if available; CPU fallback if not.
    """
    try:
        # Auto-recover GPU Pack config if pack exists on disk but config is empty
        auto_recover_gpu_pack_config(config)

        # Check if user has explicitly disabled GPU
        gpu_opt_in = getattr(config, "gpu_opt_in", None)
        if _is_gpu_disabled(config):
            logger.debug("GPU acceleration explicitly disabled (gpu_opt_in=false)")
            status = _to_gpu_status_from_context("cpu", None)
            logger.info(status.as_structured_log())
            return status

        # CRITICAL: Add GPU Pack to sys.path IMMEDIATELY if configured
        # This must happen BEFORE any torch imports (including system check)
        # to ensure GPU Pack's torch loads instead of venv's torch
        pack_path = getattr(config, "gpu_pack_path", "")
        pack_dir = None
        gpu_flavor = getattr(config, "gpu_flavor", "cu121")
        expected_cuda = _expected_cuda_from_flavor(gpu_flavor)

        if pack_path:
            pack_dir = Path(pack_path)
            if pack_dir.exists():
                logger.debug(
                    "GPU Pack found at %s - adding to sys.path BEFORE any torch imports " "(if not yet imported)",
                    pack_dir,
                )
                _add_pack_and_swap_torch_if_needed(pack_dir)
            else:
                logger.debug(f"GPU Pack path configured but directory not found: {pack_dir}")

        # STEP 1: Try system PyTorch+CUDA (ONLY if explicitly enabled AND not frozen)
        # Note: GPU Pack paths are already in sys.path, so if GPU Pack exists,
        # its torch will be imported here instead of venv's torch
        if _try_system_pytorch_if_enabled(config, gpu_opt_in):
            status = _to_gpu_status_from_context("system", pack_dir)
            logger.info(status.as_structured_log())
            return status

        # STEP 2: Validate GPU Pack (paths already added above)
        if not pack_dir or not pack_dir.exists():
            logger.debug("No GPU Pack configured or pack directory not found")
            status = _to_gpu_status_from_context("cpu", None)
            logger.info(status.as_structured_log())
            return status

        success = _validate_pack_and_update_config(config, pack_dir, gpu_flavor, expected_cuda)
        if success:
            status = _to_gpu_status_from_context("pack", pack_dir)
        else:
            status = _to_gpu_status_from_context("cpu", pack_dir, error=getattr(config, "gpu_last_error", None))
        logger.info(status.as_structured_log())
        return status

    except Exception as e:
        logger.error(f"GPU bootstrap error: {e}", exc_info=True)
        status = _to_gpu_status_from_context("cpu", None, error=str(e))
        logger.info(status.as_structured_log())
        return status


def bootstrap_and_maybe_enable_gpu(config) -> bool:
    """Backward-compatible wrapper returning bool for existing callers."""
    status = bootstrap_gpu(config)
    return status.enabled
