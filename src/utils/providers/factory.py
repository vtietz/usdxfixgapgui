"""
Factory for detection provider selection.

This module provides a factory function that selects and instantiates the MDX
detection provider based on configuration and system capabilities.

IMPORTANT: Provider classes are lazy-loaded to prevent early torch import.
GPU Pack bootstrap must run before any provider is instantiated.
"""

import logging
from typing import TYPE_CHECKING, Optional

from common.config import Config
from utils.providers.base import IDetectionProvider
# DO NOT import provider classes here - they import torch which must happen
# AFTER GPU Pack bootstrap. Import them lazily in get_detection_provider().
# from utils.providers.mdx_provider import MdxProvider
from utils.providers.exceptions import ProviderInitializationError

if TYPE_CHECKING:
    from services.system_capabilities import SystemCapabilities

logger = logging.getLogger(__name__)


def get_detection_provider(
    config: Config,
    capabilities: Optional['SystemCapabilities'] = None
) -> IDetectionProvider:
    """
    Factory function to get the MDX detection provider.

    Provider class is imported lazily to avoid early torch import. GPU Pack
    bootstrap must complete before this function is called.

    Args:
        config: Application configuration object containing method selection
        capabilities: Optional SystemCapabilities to check if detection is available.
                     If provided and can_detect is False, raises ProviderInitializationError.

    Returns:
        Configured MdxProvider instance implementing IDetectionProvider

    Raises:
        ProviderInitializationError: If provider instantiation fails or system cannot detect

    Example:
        >>> config = Config()
        >>> provider = get_detection_provider(config)
        >>> provider.get_method_name()
        'mdx'
    """
    try:
        # Check system capabilities if provided
        if capabilities is not None and not capabilities.can_detect:
            error_parts = ["Gap detection is not available on this system:"]

            if not capabilities.has_torch:
                error_parts.append(f"• PyTorch not available: {capabilities.torch_error or 'Not installed'}")
                error_parts.append("  → Reinstall the application or install PyTorch manually")

            if not capabilities.has_ffmpeg:
                error_parts.append("• FFmpeg not available")
                error_parts.append("  → Install FFmpeg and add to system PATH")

            error_msg = "\n".join(error_parts)
            raise ProviderInitializationError(error_msg)

        method = config.method.lower()

        # Only MDX is supported - silently use it regardless of config
        if method != "mdx":
            # Update config to mdx to prevent future warnings
            config.method = "mdx"
            logger.info(
                f"Detection method '{method}' is not supported. Automatically switching to 'mdx'. "
                f"Config has been updated."
            )

        logger.debug("Selecting MDX detection provider")
        # Lazy import to prevent early torch import
        from utils.providers.mdx_provider import MdxProvider
        return MdxProvider(config)

    except ProviderInitializationError:
        # Re-raise capability errors as-is
        raise
    except Exception as e:
        raise ProviderInitializationError(
            f"Failed to initialize MDX detection provider: {e}"
        ) from e
