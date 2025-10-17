"""
Factory for detection provider selection.

This module provides a factory function that selects and instantiates the appropriate
detection provider based on configuration, with fallback handling for unknown methods.

IMPORTANT: Provider classes are lazy-loaded to prevent early torch import.
GPU Pack bootstrap must run before any provider is instantiated.
"""

import logging
from typing import TYPE_CHECKING

from common.config import Config
from utils.providers.base import IDetectionProvider
# DO NOT import provider classes here - they import torch which must happen
# AFTER GPU Pack bootstrap. Import them lazily in get_detection_provider().
# from utils.providers.spleeter_provider import SpleeterProvider
# from utils.providers.hq_segment_provider import HqSegmentProvider
# from utils.providers.mdx_provider import MdxProvider
from utils.providers.exceptions import ProviderInitializationError

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def get_detection_provider(config: Config) -> IDetectionProvider:
    """
    Factory function to get the appropriate detection provider based on configuration.

    Selects provider based on Config.method value and instantiates it with the
    provided configuration. Falls back to Spleeter for unknown methods.

    Provider classes are imported lazily to avoid early torch import. GPU Pack
    bootstrap must complete before this function is called.

    Args:
        config: Application configuration object containing method selection

    Returns:
        Configured detection provider instance implementing IDetectionProvider

    Raises:
        ProviderInitializationError: If provider instantiation fails

    Supported Methods:
        - 'spleeter': Full-track AI vocal separation (SpleeterProvider) - default
        - 'hq_segment': Windowed Spleeter separation (HqSegmentProvider)
        - 'mdx': MDX-Net vocal separation with chunked scanning (MdxProvider)

    Example:
        >>> config = Config()
        >>> config.method = 'spleeter'
        >>> provider = get_detection_provider(config)
        >>> provider.get_method_name()
        'spleeter'

    Fallback Behavior:
        If method is unrecognized, logs a warning and returns SpleeterProvider
        as a safe default for reliable detection.
    """
    try:
        method = config.method.lower()

        if method == "spleeter":
            logger.debug("Selecting Spleeter detection provider")
            # Lazy import to prevent early torch import
            from utils.providers.spleeter_provider import SpleeterProvider
            return SpleeterProvider(config)

        elif method == "hq_segment":
            logger.debug("Selecting HQ Segment detection provider")
            # Lazy import to prevent early torch import
            from utils.providers.hq_segment_provider import HqSegmentProvider
            return HqSegmentProvider(config)

        elif method == "mdx":
            logger.debug("Selecting MDX detection provider")
            # Lazy import to prevent early torch import
            from utils.providers.mdx_provider import MdxProvider
            return MdxProvider(config)

        else:
            logger.warning(
                f"Unknown detection method '{method}' in config, "
                f"falling back to Spleeter (default)"
            )
            # Lazy import to prevent early torch import
            from utils.providers.spleeter_provider import SpleeterProvider
            return SpleeterProvider(config)

    except Exception as e:
        raise ProviderInitializationError(
            f"Failed to initialize detection provider for method '{config.method}': {e}"
        ) from e

