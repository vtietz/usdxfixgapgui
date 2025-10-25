"""
System PyTorch Detection for GPU Bootstrap

Detects if system/environment has usable PyTorch with CUDA support
(separate from GPU Pack).

This module is frozen-safe and works in both dev and bundled contexts.
"""

import logging
from typing import Optional, Dict

logger = logging.getLogger(__name__)


def detect_system_pytorch_cuda() -> Optional[Dict[str, str]]:
    """
    Detect if system has usable PyTorch with CUDA support.

    Checks if PyTorch is already available in the system/environment
    (not from GPU Pack) and has CUDA support enabled.

    Returns:
        Dict with torch_version, cuda_version, device_name if usable
        None if PyTorch not available or CUDA not supported
    """
    try:
        import torch

        # Check if CUDA is available
        if not torch.cuda.is_available():
            logger.debug("System PyTorch found but CUDA not available")
            return None

        # Check minimum PyTorch version (2.0+)
        version = torch.__version__
        try:
            major = int(version.split('.')[0].replace('+', ''))  # Handle version like "2.7.1+cpu"
            if major < 2:
                logger.debug(f"System PyTorch version too old: {version} (need 2.0+)")
                return None
        except (ValueError, IndexError):
            logger.debug(f"Could not parse PyTorch version: {version}")
            return None

        # Get CUDA version
        cuda_version = torch.version.cuda
        if cuda_version is None:
            logger.debug("System PyTorch has no CUDA version")
            return None

        # Get device name
        try:
            device_name = torch.cuda.get_device_name(0)
        except Exception as e:
            logger.debug(f"Could not get CUDA device name: {e}")
            device_name = "Unknown GPU"

        return {
            'torch_version': version,
            'cuda_version': cuda_version,
            'device_name': device_name
        }

    except ImportError:
        logger.debug("System PyTorch not available (ImportError)")
        return None
    except Exception as e:
        logger.debug(f"Error detecting system PyTorch: {e}")
        return None
