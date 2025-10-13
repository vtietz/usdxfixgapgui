"""
High-quality windowed segment detection provider.

This provider extracts a focused time window around the expected gap, then runs
Spleeter on just that segment for true stem isolation without full-track processing.
"""

import logging
import os
from typing import List, Tuple, Optional, Callable

from utils.providers.base import IDetectionProvider
from utils.providers.exceptions import DetectionFailedError

logger = logging.getLogger(__name__)


class HqSegmentProvider(IDetectionProvider):
    """
    High-quality short-window provider using windowed Spleeter.

    Strategy: Extract a short window around the detected gap, then apply Spleeter
    only to that segment for efficient high-quality vocal isolation.

    Performance: 3-5 seconds per song (windowed Spleeter)
    Output: True isolated vocal stem for preview window only
    Detection: Silence boundary-based (on windowed stem)
    Confidence: Fixed 0.85 (high quality, windowed context)

    Process:
        1. Calculate window bounds around expected gap (3s pre + 9s post)
        2. Extract focused time segment from audio
        3. Run Spleeter on segment only (not full track)
        4. Detect silence in windowed vocal stem
        5. Fallback to VAD preview if processing fails

    Use Cases:
        - Balanced speed/quality tradeoff
        - When VAD preview is insufficient
        - When full Spleeter is too slow
        - Quality vocal playback for gap region
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
        Extract vocals using Spleeter on short window around expected gap.

        This method calculates a focused time window around the expected gap position,
        extracts just that segment, runs Spleeter separation on it, and returns the
        windowed vocal stem.

        Args:
            audio_file: Absolute path to input audio
            temp_root: Root directory for temporary files
            destination_vocals_filepath: Target path for windowed vocals file
            duration: Track duration in seconds (used to estimate gap position)
            overwrite: If True, regenerate even if destination exists
            check_cancellation: Callback returning True if user cancelled

        Returns:
            Absolute path to windowed vocals file

        Raises:
            DetectionFailedError: If window extraction or Spleeter fails

        Side Effects:
            - Creates temporary window audio file
            - Runs Spleeter on segment
            - Falls back to VAD preview on failure
            - Cleans up temporary files on success

        Fallback Behavior:
            On any failure, automatically delegates to VadPreviewProvider for
            graceful degradation without user intervention.
        """
        from utils.preview import extract_time_window
        from utils.separate import separate_audio
        import utils.files as files

        if not overwrite and os.path.exists(destination_vocals_filepath):
            logger.debug(f"HQ segment: Vocals file already exists: {destination_vocals_filepath}")
            return destination_vocals_filepath

        try:
            # Calculate window bounds around expected gap location
            # Use duration as proxy for expected gap timing (rough estimate)
            expected_gap_ms = duration * 1000  # Convert to ms
            window_start_ms = max(0, expected_gap_ms - self.config.hq_preview_pre_ms)
            window_end_ms = expected_gap_ms + self.config.hq_preview_post_ms

            logger.info(f"HQ segment: Extracting window {window_start_ms}ms - {window_end_ms}ms "
                       f"(duration: {window_end_ms - window_start_ms}ms)")

            # Extract the focused window
            temp_dir = files.get_tmp_path(temp_root, audio_file)
            window_file = extract_time_window(
                audio_file,
                window_start_ms,
                window_end_ms,
                check_cancellation=check_cancellation
            )

            if check_cancellation and check_cancellation():
                if os.path.exists(window_file):
                    os.remove(window_file)
                raise DetectionFailedError(
                    "HQ segment extraction cancelled by user",
                    provider_name="hq_segment"
                )

            # Run Spleeter on the extracted window only (much faster than full track)
            output_path = os.path.join(temp_dir, "hq_segment_spleeter")
            window_duration_sec = int((window_end_ms - window_start_ms) / 1000) + 1

            vocals_file, _ = separate_audio(
                window_file,
                window_duration_sec,
                output_path,
                overvrite=True,  # Note: typo in separate_audio signature
                check_cancellation=check_cancellation
            )

            # Move to destination
            if os.path.exists(destination_vocals_filepath):
                os.remove(destination_vocals_filepath)
            files.move_file(vocals_file, destination_vocals_filepath)

            # Cleanup temporary files
            if os.path.exists(window_file):
                os.remove(window_file)
            files.rmtree(output_path)

            logger.info(f"HQ segment: Successfully extracted vocals to {destination_vocals_filepath}")
            return destination_vocals_filepath

        except DetectionFailedError:
            raise
        except Exception as e:
            logger.error(f"HQ segment separation failed: {e}, falling back to VAD preview")
            # Fallback to VAD preview if HQ processing fails
            from utils.providers.vad_preview_provider import VadPreviewProvider
            provider = VadPreviewProvider(self.config)
            return provider.get_vocals_file(
                audio_file,
                temp_root,
                destination_vocals_filepath,
                duration,
                overwrite,
                check_cancellation
            )

    def detect_silence_periods(
        self,
        audio_file: str,
        vocals_file: str,
        original_gap_ms: Optional[float] = None,
        check_cancellation: Optional[Callable[[], bool]] = None
    ) -> List[Tuple[float, float]]:
        """
        Detect silence periods in the HQ windowed vocal stem.

        Returns SILENCE periods (not speech), so orchestration uses silence boundary
        selection logic (detect_nearest_gap).

        Args:
            audio_file: Original audio file (unused, kept for interface)
            vocals_file: Path to windowed vocal stem from get_vocals_file()
            check_cancellation: Callback returning True if user cancelled

        Returns:
            List of (start_ms, end_ms) tuples for silence regions in the window

        Raises:
            DetectionFailedError: If silence detection fails

        Fallback Behavior:
            On failure, delegates to VadPreviewProvider for graceful degradation.
        """
        import utils.audio as audio

        try:
            silence_periods = audio.detect_silence_periods(
                vocals_file,
                silence_detect_params=self.config.spleeter_silence_detect_params,
                check_cancellation=check_cancellation
            )

            logger.debug(f"HQ segment: Detected {len(silence_periods)} silence periods")
            return silence_periods

        except Exception as e:
            logger.error(f"HQ silence detection failed: {e}, falling back to VAD preview")
            from utils.providers.vad_preview_provider import VadPreviewProvider
            provider = VadPreviewProvider(self.config)
            return provider.detect_silence_periods(audio_file, vocals_file, check_cancellation)

    def compute_confidence(
        self,
        audio_file: str,
        detected_gap_ms: float,
        check_cancellation: Optional[Callable[[], bool]] = None
    ) -> float:
        """
        Return fixed confidence for HQ segment detections.

        HQ segment uses true Spleeter separation on a focused window, providing
        high-quality stems with slight uncertainty from windowing effects.

        Args:
            audio_file: Original audio file (unused)
            detected_gap_ms: Detected gap position (unused)
            check_cancellation: Callback (unused)

        Returns:
            Fixed confidence score of 0.85 (high quality, windowed context)

        Note:
            Could be enhanced with:
            - Spectral analysis of stem quality
            - Signal-to-noise ratio of isolated vocal
            - Onset detection strength within window
        """
        return 0.85  # High confidence for true stem separation on focused window

    def get_method_name(self) -> str:
        """Return provider identifier."""
        return "hq_segment"
