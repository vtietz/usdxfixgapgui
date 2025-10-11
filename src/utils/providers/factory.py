"""
Factory for detection provider selection.

This module provides a factory function that selects and instantiates the appropriate
detection provider based on configuration, with fallback handling for unknown methods.
"""

import logging
from typing import TYPE_CHECKING

from common.config import Config
from utils.providers.base import IDetectionProvider
from utils.providers.spleeter_provider import SpleeterProvider
from utils.providers.vad_preview_provider import VadPreviewProvider
from utils.providers.hq_segment_provider import HqSegmentProvider
from utils.providers.exceptions import ProviderInitializationError

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def get_detection_provider(config: Config) -> IDetectionProvider:
    """
    Factory function to get the appropriate detection provider based on configuration.
    
    Selects provider based on Config.method value and instantiates it with the
    provided configuration. Falls back to VAD preview for unknown methods.
    
    Args:
        config: Application configuration object containing method selection
    
    Returns:
        Configured detection provider instance implementing IDetectionProvider
    
    Raises:
        ProviderInitializationError: If provider instantiation fails
    
    Supported Methods:
        - 'spleeter': Full-track AI vocal separation (SpleeterProvider)
        - 'vad_preview': Fast VAD + HPSS preview (VadPreviewProvider) - default
        - 'hq_segment': Windowed Spleeter separation (HqSegmentProvider)
    
    Example:
        >>> config = Config()
        >>> config.method = 'vad_preview'
        >>> provider = get_detection_provider(config)
        >>> provider.get_method_name()
        'vad_preview'
    
    Fallback Behavior:
        If method is unrecognized, logs a warning and returns VadPreviewProvider
        as a safe default for fast processing.
    """
    try:
        method = config.method.lower()
        
        if method == "spleeter":
            logger.debug("Selecting Spleeter detection provider")
            return SpleeterProvider(config)
        
        elif method == "vad_preview":
            logger.debug("Selecting VAD Preview detection provider")
            return VadPreviewProvider(config)
        
        elif method == "hq_segment":
            logger.debug("Selecting HQ Segment detection provider")
            return HqSegmentProvider(config)
        
        else:
            logger.warning(
                f"Unknown detection method '{method}' in config, "
                f"falling back to VAD Preview (default)"
            )
            return VadPreviewProvider(config)
    
    except Exception as e:
        raise ProviderInitializationError(
            f"Failed to initialize detection provider for method '{config.method}': {e}"
        ) from e
