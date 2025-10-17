"""
Detection provider package for gap detection.

This package contains pluggable detection strategies for vocal onset and gap detection,
each with different trade-offs between speed, quality, and accuracy.

Public API:
    - IDetectionProvider: Base interface for all providers
    - get_detection_provider: Factory function for provider selection
    - SpleeterProvider: Full-track AI vocal separation (lazy-loaded)
    - HqSegmentProvider: Windowed Spleeter separation (lazy-loaded)
    - MdxProvider: MDX-Net with chunked scanning and energy-based onset (lazy-loaded)
    - ProviderError, ProviderInitializationError, DetectionFailedError: Exceptions

Usage:
    >>> from utils.providers import get_detection_provider
    >>> from common.config import Config
    >>>
    >>> config = Config()
    >>> provider = get_detection_provider(config)
    >>> method = provider.get_method_name()  # 'spleeter', 'hq_segment', 'mdx'
"""

# Base interface and factory
from utils.providers.base import IDetectionProvider
from utils.providers.factory import get_detection_provider

# Provider implementations - DO NOT import here to avoid early torch import
# They are lazy-loaded in factory.py when actually needed
# from utils.providers.spleeter_provider import SpleeterProvider
# from utils.providers.hq_segment_provider import HqSegmentProvider
# from utils.providers.mdx_provider import MdxProvider

# Exceptions
from utils.providers.exceptions import (
    ProviderError,
    ProviderInitializationError,
    DetectionFailedError,
)

__all__ = [
    # Core interface and factory
    "IDetectionProvider",
    "get_detection_provider",
    # Providers (lazy-loaded, not re-exported)
    # "SpleeterProvider",
    # "HqSegmentProvider",
    # "MdxProvider",
    # Exceptions
    "ProviderError",
    "ProviderInitializationError",
    "DetectionFailedError",
]

