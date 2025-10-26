"""
Model Path Configuration Module

This module MUST be imported before any AI libraries (PyTorch, Demucs)
to override their default cache locations and use our centralized model storage.

Usage:
    from utils.model_paths import setup_model_paths

    # Call this BEFORE importing torch or demucs
    setup_model_paths(config)

    # Now safe to import AI libraries
    import torch
    from demucs.pretrained import get_model
"""

import os
import logging
from utils.files import get_demucs_models_dir

logger = logging.getLogger(__name__)


def setup_model_paths(config=None):
    """
    Configure environment variables to override default model cache locations.

    This function sets environment variables that AI libraries respect for model storage:
    - TORCH_HOME: PyTorch hub models (Demucs)
    - XDG_CACHE_HOME: Fallback for other libraries

    Must be called BEFORE importing PyTorch or Demucs.

    Args:
        config: Optional Config object with custom models_directory setting.
                If None, uses default LOCALAPPDATA/USDXFixGap/models/

    Returns:
        dict: Paths that were configured
            {
                'demucs_dir': str,
                'torch_home': str
            }

    Examples:
        >>> from utils.model_paths import setup_model_paths
        >>> paths = setup_model_paths()
        >>> print(paths['demucs_dir'])
        C:/Users/<username>/AppData/Local/USDXFixGap/models/demucs
    """
    # Get model directories (respects config.models_directory if set)
    demucs_dir = get_demucs_models_dir(config)

    # Create directories if they don't exist
    os.makedirs(demucs_dir, exist_ok=True)

    # Configure PyTorch Hub (used by Demucs)
    # This overrides the default ~/.cache/torch/hub/checkpoints/
    os.environ['TORCH_HOME'] = demucs_dir
    logger.info(f"Set TORCH_HOME={demucs_dir}")

    # Set XDG_CACHE_HOME as fallback for other libraries
    # This is a standard Unix/Linux environment variable
    if 'XDG_CACHE_HOME' not in os.environ:
        cache_home = os.path.dirname(demucs_dir)  # models parent directory
        os.environ['XDG_CACHE_HOME'] = cache_home
        logger.debug(f"Set XDG_CACHE_HOME={cache_home}")

    paths = {
        'demucs_dir': demucs_dir,
        'torch_home': os.environ['TORCH_HOME']
    }

    logger.info("Model paths configured successfully")
    logger.debug(f"Model paths: {paths}")

    return paths


def get_configured_model_paths():
    """
    Get currently configured model paths from environment variables.

    Returns:
        dict: Current model paths or None if not configured
            {
                'torch_home': str or None,
                'model_path': str or None,
                'xdg_cache_home': str or None
            }
    """
    return {
        'torch_home': os.environ.get('TORCH_HOME'),
        'model_path': os.environ.get('MODEL_PATH'),
        'xdg_cache_home': os.environ.get('XDG_CACHE_HOME')
    }


def is_model_paths_configured():
    """
    Check if model paths have been configured.

    Returns:
        bool: True if TORCH_HOME is set, False otherwise
    """
    return 'TORCH_HOME' in os.environ