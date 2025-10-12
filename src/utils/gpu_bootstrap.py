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
    if not pack_dir.exists():
        logger.warning(f"GPU Pack directory does not exist: {pack_dir}")
        return False
    
    site_packages = pack_dir / 'site-packages'
    bin_dir = pack_dir / 'bin'
    
    if not site_packages.exists():
        logger.warning(f"GPU Pack site-packages not found: {site_packages}")
        return False
    
    # Prepend site-packages to sys.path (highest priority)
    site_packages_str = str(site_packages)
    if site_packages_str not in sys.path:
        sys.path.insert(0, site_packages_str)
        logger.info(f"Added GPU Pack site-packages to sys.path: {site_packages_str}")
    
    # Add bin directory to DLL search path (Windows)
    if bin_dir.exists() and hasattr(os, 'add_dll_directory'):
        try:
            os.add_dll_directory(str(bin_dir))
            logger.info(f"Added GPU Pack bin to DLL search path: {bin_dir}")
        except Exception as e:
            logger.warning(f"Failed to add DLL directory: {e}")
    
    # Set environment variable for child processes
    os.environ['USDXFIXGAP_GPU_PACK_DIR'] = str(pack_dir)
    
    return True


def validate_cuda_torch(expected_cuda: str = "12.1") -> Tuple[bool, str]:
    """
    Validate that PyTorch with CUDA is properly loaded and functional.
    
    Args:
        expected_cuda: Expected CUDA version (e.g., "12.1")
        
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
        
        # Compare major.minor versions
        expected_parts = expected_cuda.split('.')[:2]
        actual_parts = torch_cuda_version.split('.')[:2]
        
        if expected_parts != actual_parts:
            return (False, f"CUDA version mismatch: expected {expected_cuda}, got {torch_cuda_version}")
        
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


def bootstrap_and_maybe_enable_gpu(config) -> bool:
    """
    Orchestrate GPU Pack activation and validation.
    
    Args:
        config: Application config object
        
    Returns:
        True if GPU is enabled and validated, False otherwise
    """
    try:
        # Check if user has opted in
        gpu_opt_in = getattr(config, 'gpu_opt_in', False)
        if not gpu_opt_in:
            logger.debug("GPU acceleration not enabled (GpuOptIn=false)")
            return False
        
        # Get pack configuration
        pack_path = getattr(config, 'gpu_pack_path', '')
        if not pack_path:
            logger.debug("GPU Pack path not configured")
            return False
        
        pack_dir = Path(pack_path)
        
        # Enable GPU runtime
        if not enable_gpu_runtime(pack_dir):
            error_msg = f"Failed to enable GPU runtime from {pack_dir}"
            logger.warning(error_msg)
            config.gpu_last_health = "failed"
            config.gpu_last_error = error_msg
            config.save_config()
            return False
        
        # Validate CUDA
        gpu_flavor = getattr(config, 'gpu_flavor', 'cu121')
        expected_cuda = "12.1" if gpu_flavor == "cu121" else "12.4"
        
        success, error_msg = validate_cuda_torch(expected_cuda)
        
        if success:
            config.gpu_last_health = "healthy"
            config.gpu_last_error = ""
            config.save_config()
            logger.info("GPU Pack activated successfully")
            return True
        else:
            logger.warning(f"CUDA validation failed: {error_msg}")
            config.gpu_last_health = "failed"
            config.gpu_last_error = error_msg
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
