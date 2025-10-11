"""
Provider-specific exceptions for gap detection.

This module defines custom exceptions to distinguish provider initialization
failures from detection failures, enabling better error handling and user feedback.
"""


class ProviderError(Exception):
    """Base exception for all provider-related errors."""
    pass


class ProviderInitializationError(ProviderError):
    """
    Raised when a provider cannot be initialized.
    
    Common causes:
    - Missing required configuration
    - Invalid configuration values
    - Missing dependencies or models
    """
    pass


class DetectionFailedError(ProviderError):
    """
    Raised when gap detection fails during processing.
    
    Common causes:
    - Audio file cannot be read
    - Vocal separation fails
    - Silence/speech detection fails
    - Cancellation requested
    """
    
    def __init__(self, message: str, provider_name: str = None, cause: Exception = None):
        """
        Initialize detection failure error.
        
        Args:
            message: Human-readable error message
            provider_name: Name of the provider that failed (e.g., 'vad_preview')
            cause: Original exception that caused the failure
        """
        super().__init__(message)
        self.provider_name: str | None = provider_name
        self.cause: Exception | None = cause
