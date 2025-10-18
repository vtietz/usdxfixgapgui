"""
GPU Bootstrap Module for USDXFixGap

Handles GPU Pack runtime activation, CUDA validation, and environment setup.
Ensures PyTorch with CUDA is loaded correctly before any provider imports.
"""

import os
import sys
import subprocess
import logging
from typing import Dict, Optional, Tuple, List, Any
from pathlib import Path

logger = logging.getLogger(__name__)

# Module-level list to track DLL directories added for diagnostics
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


def resolve_pack_dir(app_version: str, flavor: str = "cu121") -> Path:
    """
    Resolve the GPU Pack installation directory.

    Args:
        app_version: Application version (e.g., "1.4.0")
        flavor: CUDA flavor (cu121 or cu124)

    Returns:
        Path to GPU Pack directory
    """
    local_app_data = os.getenv('LOCALAPPDATA')
    if not local_app_data:
        # Fallback for non-Windows or missing env var
        local_app_data = os.path.expanduser('~/.local/share')

    pack_dir = Path(local_app_data) / 'USDXFixGap' / 'gpu_runtime' / f'v{app_version}-{flavor}'
    return pack_dir


def probe_nvml() -> Optional[Tuple[List[str], str]]:
    """
    Probe GPU information using pynvml library.

    Returns:
        Tuple of (gpu_names, driver_version) or None if pynvml not available
    """
    try:
        import pynvml
        pynvml.nvmlInit()

        driver_version = pynvml.nvmlSystemGetDriverVersion()
        if isinstance(driver_version, bytes):
            driver_version = driver_version.decode('utf-8')

        device_count = pynvml.nvmlDeviceGetCount()
        gpu_names = []

        for i in range(device_count):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            name = pynvml.nvmlDeviceGetName(handle)
            if isinstance(name, bytes):
                name = name.decode('utf-8')
            gpu_names.append(name)

        pynvml.nvmlShutdown()
        return (gpu_names, driver_version)

    except (ImportError, Exception) as e:
        logger.debug(f"pynvml not available: {e}")
        return None


def probe_nvidia_smi() -> Optional[Tuple[List[str], str]]:
    """
    Fallback GPU probe using nvidia-smi command.

    Returns:
        Tuple of (gpu_names, driver_version) or None if nvidia-smi not available
    """
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=name,driver_version', '--format=csv,noheader'],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode != 0:
            return None

        lines = result.stdout.strip().split('\n')
        if not lines or not lines[0]:
            return None

        gpu_names = []
        driver_version = None

        for line in lines:
            parts = [p.strip() for p in line.split(',')]
            if len(parts) >= 2:
                gpu_names.append(parts[0])
                if driver_version is None:
                    driver_version = parts[1]

        return (gpu_names, driver_version) if gpu_names and driver_version else None

    except (FileNotFoundError, subprocess.TimeoutExpired, Exception) as e:
        logger.debug(f"nvidia-smi not available: {e}")
        return None


def capability_probe() -> Dict[str, Any]:
    """
    Probe NVIDIA GPU capability and driver information.

    Returns:
        Dictionary with keys: has_nvidia, driver_version, gpu_names
    """
    # Try pynvml first, fallback to nvidia-smi
    result = probe_nvml()
    if result is None:
        result = probe_nvidia_smi()

    if result is None:
        return {
            'has_nvidia': False,
            'driver_version': None,
            'gpu_names': []
        }

    gpu_names, driver_version = result
    return {
        'has_nvidia': True,
        'driver_version': driver_version,
        'gpu_names': gpu_names
    }


def enable_gpu_runtime(pack_dir: Path) -> bool:
    """
    Enable GPU Pack runtime by modifying sys.path and DLL search paths.

    Args:
        pack_dir: Path to GPU Pack installation

    Returns:
        True if successful, False otherwise
    """
    global ADDED_DLL_DIRS
    ADDED_DLL_DIRS = []  # Reset tracking list
    
    if not pack_dir.exists():
        logger.debug(f"GPU Pack directory does not exist: {pack_dir}")
        return False

    # Check if this is a wheel extraction (torch/, functorch/ at root)
    # or a traditional install (site-packages/)
    torch_dir = pack_dir / 'torch'
    site_packages = pack_dir / 'site-packages'

    if torch_dir.exists():
        # Wheel extraction - add pack_dir itself to sys.path
        pack_dir_str = str(pack_dir)
        if pack_dir_str not in sys.path:
            sys.path.insert(0, pack_dir_str)
            logger.info(f"Added GPU Pack directory to sys.path: {pack_dir_str}")

        # Platform-specific library path setup
        if sys.platform == 'win32':
            # Windows: Add multiple DLL directories for CUDA/cuDNN/NVRTC dependencies
            dll_dirs = [
                torch_dir / 'lib',           # Main torch DLLs (torch_python.dll, etc.)
                pack_dir / 'bin',            # CUDA/cuDNN/NVRTC DLLs (cublas64_12.dll, etc.)
                pack_dir / 'torchaudio' / 'lib'  # Torchaudio backend DLLs if present
            ]
            
            for dll_dir in dll_dirs:
                if dll_dir.exists() and hasattr(os, 'add_dll_directory'):
                    try:
                        os.add_dll_directory(str(dll_dir))
                        ADDED_DLL_DIRS.append(str(dll_dir))
                        logger.info(f"Added DLL directory: {dll_dir}")
                    except Exception as e:
                        logger.warning(f"Failed to add DLL directory {dll_dir}: {e}")
        else:
            # Linux: Add torch/lib directory to LD_LIBRARY_PATH
            torch_lib_dir = torch_dir / 'lib'
            if torch_lib_dir.exists():
                ld_path = os.environ.get('LD_LIBRARY_PATH', '')
                new_ld_path = f"{torch_lib_dir}:{ld_path}" if ld_path else str(torch_lib_dir)
                os.environ['LD_LIBRARY_PATH'] = new_ld_path
                logger.info(f"Added torch/lib to LD_LIBRARY_PATH: {torch_lib_dir}")

    elif site_packages.exists():
        # Traditional install with site-packages
        bin_dir = pack_dir / 'bin'

        # Prepend site-packages to sys.path (highest priority)
        site_packages_str = str(site_packages)
        if site_packages_str not in sys.path:
            sys.path.insert(0, site_packages_str)
            logger.info(f"Added GPU Pack site-packages to sys.path: {site_packages_str}")

        # Platform-specific library path setup
        if sys.platform == 'win32':
            # Windows: Add bin directory and torchaudio/lib to DLL search path
            dll_dirs = [
                bin_dir,
                site_packages / 'torchaudio' / 'lib'
            ]
            
            for dll_dir in dll_dirs:
                if dll_dir.exists() and hasattr(os, 'add_dll_directory'):
                    try:
                        os.add_dll_directory(str(dll_dir))
                        ADDED_DLL_DIRS.append(str(dll_dir))
                        logger.info(f"Added DLL directory: {dll_dir}")
                    except Exception as e:
                        logger.warning(f"Failed to add DLL directory {dll_dir}: {e}")
        else:
            # Linux: Add lib directory to LD_LIBRARY_PATH
            lib_dir = pack_dir / 'lib'
            if lib_dir.exists():
                ld_path = os.environ.get('LD_LIBRARY_PATH', '')
                new_ld_path = f"{lib_dir}:{ld_path}" if ld_path else str(lib_dir)
                os.environ['LD_LIBRARY_PATH'] = new_ld_path
                logger.info(f"Added GPU Pack lib to LD_LIBRARY_PATH: {lib_dir}")
    else:
        logger.warning(f"GPU Pack has neither torch/ nor site-packages/: {pack_dir}")
        return False

    # Check for VC++ runtime DLLs on Windows
    if sys.platform == 'win32':
        _check_vcruntime()

    # Set environment variable for child processes
    os.environ['USDXFIXGAP_GPU_PACK_DIR'] = str(pack_dir)

    return True


def validate_cuda_torch(expected_cuda: str = "12.1") -> Tuple[bool, str]:
    """
    Validate that PyTorch with CUDA is properly loaded and functional.

    Args:
        expected_cuda: Expected CUDA version (e.g., "12.1" for exact match, "12" for any 12.x)

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


def bootstrap_and_maybe_enable_gpu(config) -> bool:
    """
    Orchestrate GPU Pack activation and validation.
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
    global ADDED_DLL_DIRS
    
    try:
        # Check if user has explicitly disabled GPU
        gpu_opt_in = getattr(config, 'gpu_opt_in', None)
        if gpu_opt_in is False:
            logger.debug("GPU acceleration explicitly disabled (GpuOptIn=false)")
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
                if enable_gpu_runtime(pack_dir):
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
                        diagnostic_info = _build_diagnostic_message(pack_dir, gpu_flavor, expected_cuda, error_msg)
                        config.gpu_last_error = diagnostic_info
                        config.gpu_last_health = "failed"
                        config.save_config()
                        # GPU Pack failed - don't try CPU fallback with broken GPU Pack in sys.path
                        # User needs to fix or remove GPU Pack
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
        except:
            pass
        return False


def _build_diagnostic_message(pack_dir: Optional[Path], flavor: str, expected_cuda: str, error_msg: str) -> str:
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
