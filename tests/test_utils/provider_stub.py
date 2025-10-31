"""
Provider stub for Tier-3 pipeline integration tests.

Implements IDetectionProvider interface with configurable behavior for testing
pipeline orchestration without Demucs execution.
"""

import logging
from pathlib import Path
from typing import List, Tuple, Optional, Callable

import torchaudio

from common.config import Config
from utils.providers.base import IDetectionProvider
from utils.providers.exceptions import DetectionFailedError

logger = logging.getLogger(__name__)


class StubProvider(IDetectionProvider):
    """
    Stub implementation of IDetectionProvider for testing.

    Behavior:
    - get_vocals_file: Extracts right channel from stereo input (ground-truth vocals)
    - detect_silence_periods: Returns configurable silence periods
    - compute_confidence: Returns fixed or SNR-based confidence score
    - get_method_name: Returns "mdx"

    This allows testing pipeline orchestration with real file I/O but without
    expensive Demucs execution.
    """

    def __init__(
        self,
        config: Config,
        truth_onset_ms: Optional[float] = None,
        confidence_value: float = 0.95,
        raise_on_get_vocals: bool = False,
        raise_on_detect_silence: bool = False,
        raise_on_confidence: bool = False,
    ):
        """
        Initialize stub provider with configurable behavior.

        Args:
            config: Configuration object (used for interface compliance)
            truth_onset_ms: Ground truth onset position in ms. If provided,
                          detect_silence_periods returns [(0, truth_onset_ms)]
            confidence_value: Fixed confidence score to return (0.0-1.0)
            raise_on_get_vocals: If True, get_vocals_file raises DetectionFailedError
            raise_on_detect_silence: If True, detect_silence_periods raises
            raise_on_confidence: If True, compute_confidence raises
        """
        super().__init__(config)
        self.truth_onset_ms = truth_onset_ms
        self.confidence_value = confidence_value
        self.raise_on_get_vocals = raise_on_get_vocals
        self.raise_on_detect_silence = raise_on_detect_silence
        self.raise_on_confidence = raise_on_confidence

        # Track method calls for assertions
        self.get_vocals_call_count = 0
        self.detect_silence_call_count = 0
        self.compute_confidence_call_count = 0

    def get_vocals_file(
        self,
        audio_file: str,
        temp_root: str,
        destination_vocals_filepath: str,
        duration: int = 60,
        overwrite: bool = False,
        check_cancellation: Optional[Callable[[], bool]] = None,
    ) -> str:
        """
        Extract right channel from stereo audio as vocals.

        Simulates vocal separation by extracting the right channel (ground truth)
        from test audio files generated with audio_factory.
        """
        self.get_vocals_call_count += 1

        if self.raise_on_get_vocals:
            raise DetectionFailedError("Stub configured to fail on get_vocals_file", provider_name="mdx")

        # Check if destination exists and overwrite=False
        dest_path = Path(destination_vocals_filepath)
        if dest_path.exists() and not overwrite:
            logger.info(f"StubProvider: Using existing vocals file: {dest_path}")
            return str(dest_path)

        # Load audio
        waveform, sr = torchaudio.load(audio_file)

        # Extract right channel (vocals)
        if waveform.shape[0] >= 2:
            vocals_mono = waveform[1:2, :]  # Right channel
        else:
            vocals_mono = waveform[0:1, :]  # Mono fallback

        # Duplicate to stereo
        vocals_stereo = vocals_mono.repeat(2, 1)

        # Ensure destination directory exists
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        # Save vocals file
        torchaudio.save(str(dest_path), vocals_stereo, sr)
        logger.info(f"StubProvider: Extracted vocals to {dest_path}")

        return str(dest_path)

    def detect_silence_periods(
        self,
        audio_file: str,
        vocals_file: str,
        original_gap_ms: Optional[float] = None,
        check_cancellation: Optional[Callable[[], bool]] = None,
    ) -> List[Tuple[float, float]]:
        """
        Return configurable silence periods.

        If truth_onset_ms is set, returns [(0.0, truth_onset_ms)] representing
        silence from start to onset. Otherwise returns empty list.
        """
        self.detect_silence_call_count += 1

        if self.raise_on_detect_silence:
            raise DetectionFailedError("Stub configured to fail on detect_silence_periods", provider_name="mdx")

        if self.truth_onset_ms is not None:
            # Return silence period from 0 to onset (MDX-style)
            periods = [(0.0, self.truth_onset_ms)]
            logger.info(f"StubProvider: Returning silence periods: {periods}")
            return periods
        else:
            # No silence periods
            logger.info("StubProvider: No silence periods configured")
            return []

    def compute_confidence(
        self, audio_file: str, detected_gap_ms: float, check_cancellation: Optional[Callable[[], bool]] = None
    ) -> float:
        """
        Return fixed confidence value.

        In production, this would analyze signal quality. For testing,
        we return the configured fixed value.
        """
        self.compute_confidence_call_count += 1

        if self.raise_on_confidence:
            raise DetectionFailedError("Stub configured to fail on compute_confidence", provider_name="mdx")

        logger.info(f"StubProvider: Returning confidence: {self.confidence_value}")
        return self.confidence_value

    def get_method_name(self) -> str:
        """Return 'mdx' to match production provider."""
        return "mdx"
