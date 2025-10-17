"""
GPU Utilities for USDXFixGap

Provides utility functions for checking GPU Pack installation status,
CUDA availability, and other GPU-related queries.
"""

from pathlib import Path
from typing import Optional, Tuple


def is_gpu_pack_installed(config) -> bool:
    """
    Check if GPU Pack is actually installed on disk.

    Verifies both that:
    1. Config has gpu_pack_path set
    2. The path actually exists on disk

    Args:
        config: Application config object

    Returns:
        True if GPU Pack is installed and path exists, False otherwise
    """
    if not config.gpu_pack_path:
        return False

    pack_path = Path(config.gpu_pack_path)
    return pack_path.exists() and pack_path.is_dir()


def get_gpu_pack_info(config) -> Optional[Tuple[str, str]]:
    """
    Get GPU Pack installation information.

    Args:
        config: Application config object

    Returns:
        Tuple of (version, path) if installed, None otherwise
    """
    if not is_gpu_pack_installed(config):
        return None

    version = config.gpu_pack_installed_version or "unknown"
    path = str(config.gpu_pack_path)

    return (version, path)


def is_gpu_enabled(config) -> bool:
    """
    Check if GPU acceleration is enabled in config.

    Args:
        config: Application config object

    Returns:
        True if GpuOptIn is enabled, False otherwise
    """
    return bool(config.gpu_opt_in)


def is_gpu_ready(config, gpu_enabled: bool) -> bool:
    """
    Check if GPU is ready for use (installed, enabled, and bootstrapped).

    Args:
        config: Application config object
        gpu_enabled: Boolean indicating if GPU bootstrap succeeded

    Returns:
        True if GPU is ready to use, False otherwise
    """
    return (
        is_gpu_pack_installed(config) and
        is_gpu_enabled(config) and
        gpu_enabled
    )


def get_gpu_status_summary(config, gpu_enabled: bool) -> dict:
    """
    Get comprehensive GPU status information.

    Args:
        config: Application config object
        gpu_enabled: Boolean indicating if GPU bootstrap succeeded

    Returns:
        Dictionary with status information:
        - installed: bool
        - enabled: bool
        - bootstrapped: bool
        - ready: bool
        - version: str or None
        - path: str or None
        - last_error: str or None
    """
    pack_info = get_gpu_pack_info(config)

    return {
        'installed': is_gpu_pack_installed(config),
        'enabled': is_gpu_enabled(config),
        'bootstrapped': gpu_enabled,
        'ready': is_gpu_ready(config, gpu_enabled),
        'version': pack_info[0] if pack_info else None,
        'path': pack_info[1] if pack_info else None,
        'last_error': config.gpu_last_error if hasattr(config, 'gpu_last_error') else None
    }
