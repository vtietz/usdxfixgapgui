"""
Factory for detection provider selection.

This module provides a factory function that selects and instantiates the MDX
detection provider based on configuration.

IMPORTANT: Provider classes are lazy-loaded to prevent early torch import.
GPU Pack bootstrap must run before any provider is instantiated.
"""

import logging
from typing import TYPE_CHECKING

from common.config import Config
from utils.providers.base import IDetectionProvider
# DO NOT import provider classes here - they import torch which must happen
# AFTER GPU Pack bootstrap. Import them lazily in get_detection_provider().
# from utils.providers.mdx_provider import MdxProvider
from utils.providers.exceptions import ProviderInitializationError

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def get_detection_provider(config: Config) -> IDetectionProvider:
    """
    Factory function to get the MDX detection provider.

    Provider class is imported lazily to avoid early torch import. GPU Pack
    bootstrap must complete before this function is called.

    Args:
        config: Application configuration object containing method selection

    Returns:
        Configured MdxProvider instance implementing IDetectionProvider

    Raises:
        ProviderInitializationError: If provider instantiation fails

    Example:
        >>> config = Config()
        >>> provider = get_detection_provider(config)
        >>> provider.get_method_name()
        'mdx'
    """
    try:
        method = config.method.lower()

        if method != "mdx":
            logger.warning(
                f"Detection method '{method}' is not supported. Only 'mdx' is available. "
                f"Using MDX provider."
            )

        logger.debug("Selecting MDX detection provider")
        # Lazy import to prevent early torch import
        from utils.providers.mdx_provider import MdxProvider
        return MdxProvider(config)

    except Exception as e:
        raise ProviderInitializationError(
            f"Failed to initialize MDX detection provider: {e}"
        ) from e

