"""
Detection provider package for gap detection.

This package contains pluggable detection strategies for vocal onset and gap detection,
each with different trade-offs between speed, quality, and accuracy.

Public API:
    - IDetectionProvider: Base interface for all providers
    - get_detection_provider: Factory function for provider selection
    - SpleeterProvider: Full-track AI vocal separation
    - VadPreviewProvider: Fast VAD + HPSS preview
    - HqSegmentProvider: Windowed Spleeter separation
    - ProviderError, ProviderInitializationError, DetectionFailedError: Exceptions

Usage:
    >>> from utils.providers import get_detection_provider
    >>> from common.config import Config
    >>> 
    >>> config = Config()
    >>> provider = get_detection_provider(config)
    >>> method = provider.get_method_name()  # 'vad_preview', 'spleeter', etc.
"""

# Base interface and factory
from utils.providers.base import IDetectionProvider
from utils.providers.factory import get_detection_provider

# Provider implementations
from utils.providers.spleeter_provider import SpleeterProvider
from utils.providers.vad_preview_provider import VadPreviewProvider
from utils.providers.hq_segment_provider import HqSegmentProvider

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
    # Providers
    "SpleeterProvider",
    "VadPreviewProvider",
    "HqSegmentProvider",
    # Exceptions
    "ProviderError",
    "ProviderInitializationError",
    "DetectionFailedError",
]
