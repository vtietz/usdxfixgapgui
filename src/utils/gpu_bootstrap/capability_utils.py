"""
GPU Capability Detection Utilities

Provides NVIDIA GPU detection and driver version probing without requiring PyTorch.
Works in both development and PyInstaller frozen executable contexts.
"""

import os
import subprocess
import logging
from typing import Optional, Tuple, List, Dict, Any

logger = logging.getLogger(__name__)


def probe_nvml() -> Optional[Tuple[List[str], str]]:
    """
    Use pynvml (if available) to query NVIDIA GPU information.

    Returns:
        Tuple of (gpu_names, driver_version) or None if unavailable
    """
    try:
        import pynvml
        pynvml.nvmlInit()

        driver_version = pynvml.nvmlSystemGetDriverVersion()
        device_count = pynvml.nvmlDeviceGetCount()

        gpu_names = []
        for i in range(device_count):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            name = pynvml.nvmlDeviceGetName(handle)
            # Handle bytes/string conversion
            if isinstance(name, bytes):
                name = name.decode('utf-8')
            gpu_names.append(name)

        pynvml.nvmlShutdown()

        # Handle bytes/string conversion for driver version
        if isinstance(driver_version, bytes):
            driver_version = driver_version.decode('utf-8')

        return (gpu_names, driver_version) if gpu_names and driver_version else None

    except (ImportError, Exception) as e:
        logger.debug(f"pynvml not available: {e}")
        return None


def probe_nvidia_smi() -> Optional[Tuple[List[str], str]]:
    """
    Use nvidia-smi command to query NVIDIA GPU information.

    Returns:
        Tuple of (gpu_names, driver_version) or None if unavailable
    """
    try:
        # Query driver version
        driver_result = subprocess.run(
            ['nvidia-smi', '--query-gpu=driver_version', '--format=csv,noheader'],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        driver_version = driver_result.stdout.strip().split('\n')[0].strip()

        # Query GPU names
        gpu_result = subprocess.run(
            ['nvidia-smi', '--query-gpu=name', '--format=csv,noheader'],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        gpu_names = [name.strip() for name in gpu_result.stdout.strip().split('\n') if name.strip()]

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
