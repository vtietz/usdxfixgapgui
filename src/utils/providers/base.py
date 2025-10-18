"""
Base interface for gap detection providers.

This module defines the abstract interface that all detection providers must implement,
establishing a consistent contract for pluggable detection strategies.
"""

import logging
from abc import ABC, abstractmethod
from typing import List, Tuple, Optional, Callable

from common.config import Config

logger = logging.getLogger(__name__)


class IDetectionProvider(ABC):
    """
    Abstract base interface for gap detection providers.

    All detection providers must implement this interface to be compatible with
    the detection orchestration layer. Providers encapsulate different strategies
    for vocal isolation and boundary detection.

    Attributes:
        config: Configuration object with provider-specific settings

    Lifecycle:
        1. Provider instantiated via factory with Config
        2. get_vocals_file() creates/retrieves vocals or preview audio
        3. detect_silence_periods() analyzes audio for silence/speech boundaries
        4. compute_confidence() calculates detection quality metric
        5. get_method_name() identifies provider for logging/UI
    """

    def __init__(self, config: Config):
        """
        Initialize provider with configuration.

        Args:
            config: Configuration object containing provider-specific settings

        Raises:
            ProviderInitializationError: If required config missing or invalid
        """
        self.config = config

    @abstractmethod
    def get_vocals_file(
        self,
        audio_file: str,
        temp_root: str,
        destination_vocals_filepath: str,
        duration: int = 60,
        overwrite: bool = False,
        check_cancellation: Optional[Callable[[], bool]] = None
    ) -> str:
        """
        Get or create vocals/preview file for gap detection.

        This method is responsible for generating the audio file that will be
        analyzed for silence/speech boundaries. Implementations may:
        - Perform AI-based vocal separation (MDX-Net)
        - Create vocal-forward preview (HPSS + VAD)
        - Extract and separate time windows for analysis

        Args:
            audio_file: Absolute path to input audio file
            temp_root: Root directory for temporary files
            destination_vocals_filepath: Target path for vocals/preview file
            duration: Duration to process in seconds (may be used for estimation)
            overwrite: If True, regenerate even if destination exists
            check_cancellation: Optional callback returning True if cancelled

        Returns:
            Absolute path to vocals/preview file (may differ from destination)

        Raises:
            DetectionFailedError: If vocal extraction fails

        Side Effects:
            - May create temporary files in temp_root
            - May apply audio filters or transformations
            - Should cleanup temp files on success
        """

    @abstractmethod
    def detect_silence_periods(
        self,
        audio_file: str,
        vocals_file: str,
        original_gap_ms: Optional[float] = None,
        check_cancellation: Optional[Callable[[], bool]] = None
    ) -> List[Tuple[float, float]]:
        """
        Detect silence or speech boundary periods in audio.

        **IMPORTANT SEMANTIC NOTE:**
        Providers return different segment types based on their detection strategy:
        - Speech-centric providers (VAD preview): Return SPEECH segments (start, end)
        - Silence-centric providers (AI vocal separation): Return SILENCE segments (start, end)

        The orchestration layer (detect_gap.perform) handles routing to appropriate
        boundary selection logic based on get_method_name().

        Args:
            audio_file: Absolute path to original audio file
            vocals_file: Absolute path to vocals/preview file from get_vocals_file()
            check_cancellation: Optional callback returning True if cancelled

        Returns:
            List of (start_ms, end_ms) tuples representing silence OR speech periods.
            Empty list if no periods detected.

        Raises:
            DetectionFailedError: If silence/speech detection fails

        Invariants:
            - Tuples are sorted by start_ms ascending
            - start_ms < end_ms for all tuples
            - Periods do not overlap
        """

    @abstractmethod
    def compute_confidence(
        self,
        audio_file: str,
        detected_gap_ms: float,
        check_cancellation: Optional[Callable[[], bool]] = None
    ) -> float:
        """
        Compute confidence score for the detected gap.

        Confidence reflects detection quality and can be based on:
        - VAD probability scores
        - Spectral flux magnitude
        - Signal-to-noise ratio
        - Onset detection strength

        Args:
            audio_file: Absolute path to original audio file
            detected_gap_ms: Detected gap position in milliseconds
            check_cancellation: Optional callback returning True if cancelled

        Returns:
            Confidence score in range [0.0, 1.0] where:
            - 0.0 = no confidence
            - 0.5 = moderate confidence
            - 1.0 = maximum confidence

        Raises:
            DetectionFailedError: If confidence computation fails

        Note:
            Some providers may return fixed confidence if dynamic scoring unavailable.
            Returning 0.5 is acceptable for providers without confidence metrics.
        """

    @abstractmethod
    def get_method_name(self) -> str:
        """
        Return the identifier for this detection method.

        This name is used for:
        - Logging and debugging
        - UI display
        - Routing boundary selection logic
        - Configuration selection

        Returns:
            Provider identifier string:
            - 'mdx': MDX-Net AI vocal separation with VAD

        Note:
            Must match the method name in Config.method for factory selection.
        """
