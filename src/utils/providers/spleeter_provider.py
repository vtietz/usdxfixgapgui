"""
Spleeter-based detection provider.

This provider uses the Spleeter AI model to perform full-track vocal stem separation,
then detects silence boundaries in the isolated vocal track.
"""

import logging
import os
from typing import List, Tuple, Optional, Callable

from utils.providers.base import IDetectionProvider
from utils.providers.exceptions import DetectionFailedError

logger = logging.getLogger(__name__)


class SpleeterProvider(IDetectionProvider):
    """
    Legacy Spleeter-based detection provider.

    This provider performs full-track AI-powered vocal separation using the Spleeter
    2-stems model, then applies FFmpeg silencedetect to find silence boundaries.

    Performance: 30-60 seconds per song (GPU-accelerated or CPU)
    Output: True isolated vocal stem for entire track
    Detection: Silence boundary-based (finds nearest silence edge)
    Confidence: Fixed 0.8 (no dynamic confidence scoring)

    Use Cases:
        - When you need actual isolated vocals for listening
        - Manual gap adjustment with clean audio
        - Songs with complex arrangements
        - Quality over speed priority
    """

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
        Extract vocals using Spleeter 2-stems model.

        Process:
            1. Run Spleeter separation (vocals + accompaniment)
            2. Apply voice clarity filter to enhance vocals
            3. Convert to MP3 for efficient storage
            4. Move to destination path
            5. Cleanup temporary files

        Args:
            audio_file: Absolute path to input audio
            temp_root: Root directory for temporary Spleeter outputs
            destination_vocals_filepath: Target path for final vocals file
            duration: Track duration in seconds (used for progress estimation)
            overwrite: If True, regenerate even if destination exists
            check_cancellation: Callback returning True if user cancelled

        Returns:
            Absolute path to vocals file (equals destination_vocals_filepath)

        Raises:
            DetectionFailedError: If Spleeter separation fails or vocals not found

        Side Effects:
            - Creates temp files in {temp_root}/spleeter/
            - Applies voice clarity filter (highpass/lowpass)
            - Converts to MP3 format
            - Removes temporary Spleeter output directory
        """
        import utils.files as files
        import utils.audio as audio
        from utils.separate import separate_audio

        logger.debug(f"Spleeter: Extracting vocals from {audio_file}")

        if not overwrite and os.path.exists(destination_vocals_filepath):
            logger.debug(f"Spleeter: Vocals file already exists: {destination_vocals_filepath}")
            return destination_vocals_filepath

        output_path = os.path.join(temp_root, "spleeter")

        try:
            vocals_file, instrumental_file = separate_audio(
                audio_file,
                duration,
                output_path,
                overwrite,
                check_cancellation=check_cancellation
            )

            if vocals_file is None:
                raise DetectionFailedError(
                    f"Spleeter failed to extract vocals from '{audio_file}'",
                    provider_name="spleeter"
                )

            # Apply voice clarity filter
            vocals_file = audio.make_clearer_voice(vocals_file, check_cancellation)
            vocals_file = audio.convert_to_mp3(vocals_file, check_cancellation)

            # Move to destination
            if vocals_file and destination_vocals_filepath:
                if os.path.exists(destination_vocals_filepath):
                    os.remove(destination_vocals_filepath)
                files.move_file(vocals_file, destination_vocals_filepath)

            files.rmtree(output_path)

            logger.info(f"Spleeter: Successfully extracted vocals to {destination_vocals_filepath}")
            return destination_vocals_filepath

        except DetectionFailedError:
            raise
        except Exception as e:
            raise DetectionFailedError(
                f"Spleeter vocal extraction failed: {e}",
                provider_name="spleeter",
                cause=e
            )

    def detect_silence_periods(
        self,
        audio_file: str,
        vocals_file: str,
        original_gap_ms: Optional[float] = None,
        check_cancellation: Optional[Callable[[], bool]] = None
    ) -> List[Tuple[float, float]]:
        """
        Detect silence periods in isolated vocal stem using FFmpeg silencedetect.

        Returns SILENCE periods (not speech), so orchestration uses silence boundary
        selection logic (detect_nearest_gap).

        Args:
            audio_file: Original audio file (unused by Spleeter, kept for interface)
            vocals_file: Path to Spleeter-separated vocals file
            check_cancellation: Callback returning True if user cancelled

        Returns:
            List of (start_ms, end_ms) tuples for silence regions, sorted ascending

        Raises:
            DetectionFailedError: If silencedetect fails to run
        """
        import utils.audio as audio

        try:
            # Use spleeter-specific silence detection parameters from config
            silence_periods = audio.detect_silence_periods(
                vocals_file,
                silence_detect_params=self.config.spleeter_silence_detect_params,
                check_cancellation=check_cancellation
            )

            logger.debug(f"Spleeter: Detected {len(silence_periods)} silence periods")
            return silence_periods

        except Exception as e:
            raise DetectionFailedError(
                f"Spleeter silence detection failed: {e}",
                provider_name="spleeter",
                cause=e
            )

    def compute_confidence(
        self,
        audio_file: str,
        detected_gap_ms: float,
        check_cancellation: Optional[Callable[[], bool]] = None
    ) -> float:
        """
        Return fixed confidence for Spleeter detections.

        Spleeter doesn't provide dynamic confidence scoring, so we return
        a reasonable fixed value indicating high-quality stem separation.

        Args:
            audio_file: Original audio file (unused)
            detected_gap_ms: Detected gap position (unused)
            check_cancellation: Callback (unused)

        Returns:
            Fixed confidence score of 0.8 (reasonable for Spleeter quality)
        """
        return 0.8  # Assume reasonable confidence for full Spleeter separation

    def get_method_name(self) -> str:
        """Return provider identifier."""
        return "spleeter"
