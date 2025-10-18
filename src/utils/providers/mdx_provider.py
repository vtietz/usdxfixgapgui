"""
Demucs-based vocal separation provider with chunked scanning and energy-based onset detection.

This provider uses Demucs (state-of-the-art audio separation) for vocal separation combined with
adaptive energy-based onset detection. Unlike full-track separation, it scans audio in chunks
and stops as soon as the first vocal onset is detected, making it significantly faster
than traditional approaches while maintaining high accuracy.

Performance: 5-15 seconds per song (GPU), 15-45 seconds (CPU)
Output: Clean vocal stem (Demucs separated)
Detection: Energy-based onset on vocal stem
Confidence: SNR-based (signal-to-noise ratio)

Process:
    1. Scan audio in overlapping chunks (12s chunks, 50% overlap)
    2. Run Demucs on each chunk to get vocal stem
    3. Compute adaptive energy threshold from chunk's noise floor
    4. Detect vocal onset when RMS > noise_floor + k*sigma for min_duration
    5. Stop scanning as soon as first onset found (early exit)
    6. Refine detection in [onset-3s, onset+9s] window for preview
    7. Optional micro-snap using RMS rise peak
"""

import logging
import os
import warnings
import numpy as np
import torch
import torchaudio
from typing import List, Tuple, Optional, Callable

from demucs.apply import apply_model
from utils.providers.base import IDetectionProvider
from utils.providers.exceptions import DetectionFailedError
from utils.providers.mdx.config import MdxConfig
from utils.providers.mdx.model_loader import ModelLoader
from utils.providers.mdx.logging import flush_logs as _flush_logs
from utils.providers.mdx.separator import separate_vocals_chunk
from utils.providers.mdx.detection import detect_onset_in_vocal_chunk
from utils.providers.mdx.confidence import compute_confidence_score
from utils.providers.mdx.vocals_cache import VocalsCache

# Suppress TorchAudio MP3 warning globally for this module
warnings.filterwarnings("ignore", message=".*MPEG_LAYER_III.*")
warnings.filterwarnings("ignore", category=UserWarning, module="torchaudio")

logger = logging.getLogger(__name__)


class MdxProvider(IDetectionProvider):
    """
    Demucs-based provider with chunked scanning and energy onset detection.

    This provider performs efficient vocal onset detection by scanning audio in chunks,
    separating vocals with Demucs, and using simple energy-based onset detection on the
    clean vocal stem. Stops as soon as the first vocal onset is detected.

    Advantages over VAD:
        - Demucs removes instruments → clean vocal stem
        - Energy threshold on clean stem is reliable
        - No PYIN needed (works on clean vocals)
        - Chunked scanning saves processing time
        - Early-stop on first detection

    Use Cases:
        - Fast vocal onset detection with high accuracy
        - Songs with continuous intro music (where VAD fails)
        - Reliable AI-based vocal separation for gap detection
    """

    def __init__(self, config):
        """Initialize MDX provider with configuration."""
        super().__init__(config)

        # Parse and validate configuration
        self.mdx_config = MdxConfig.from_config(config)

        # Model loader (lazy loading)
        self._model_loader = ModelLoader()
        self._device = self._model_loader.get_device()

        # LRU cache for separated vocals (avoid re-separation in compute_confidence)
        self._vocals_cache = VocalsCache()

        logger.debug(
            f"MDX provider initialized: chunk={self.mdx_config.chunk_duration_ms}ms, "
            f"SNR_threshold={self.mdx_config.onset_snr_threshold}, "
            f"abs_threshold={self.mdx_config.onset_abs_threshold}, "
            f"initial_radius=±{self.mdx_config.initial_radius_ms/1000:.1f}s, "
            f"max_expansions={self.mdx_config.max_expansions}, "
            f"device={self._device}, "
            f"fp16={self.mdx_config.use_fp16 and self._device=='cuda'}"
        )

    def _get_demucs_model(self):
        """
        Get Demucs model (lazy loading via ModelLoader).

        Returns cached model or loads new one with optimizations.
        Thread-safe via ModelLoader's internal lock.
        """
        return self._model_loader.get_model(self._device, self.mdx_config.use_fp16)

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
        Prepare vocals using Demucs separation.

        For preview/final vocals, this creates a full-quality separated vocal file.
        Uses Demucs 'htdemucs' model for high-quality separation.

        Args:
            audio_file: Absolute path to input audio
            temp_root: Root directory for temporary files
            destination_vocals_filepath: Target path for vocals file
            duration: Track duration in seconds (not used - separates full track)
            overwrite: If True, regenerate even if destination exists
            check_cancellation: Callback returning True if user cancelled

        Returns:
            Absolute path to vocals file

        Raises:
            DetectionFailedError: If Demucs separation fails
        """
        logger.info(f"Preparing vocals from {audio_file}")

        if not os.path.exists(destination_vocals_filepath) or overwrite:
            try:
                # Check cancellation
                if check_cancellation and check_cancellation():
                    raise DetectionFailedError("Separation cancelled by user", provider_name="mdx")

                # Load audio
                logger.info("Loading full audio file...")
                import warnings
                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore", message=".*MPEG_LAYER_III.*")
                    waveform, sample_rate = torchaudio.load(audio_file)

                # Convert to stereo if needed
                if waveform.shape[0] == 1:
                    waveform = waveform.repeat(2, 1)

                # Check cancellation
                if check_cancellation and check_cancellation():
                    raise DetectionFailedError("Separation cancelled by user", provider_name="mdx")

                # Run Demucs separation
                logger.info("Running full-track Demucs separation (this may take a while)...")
                model = self._get_demucs_model()

                import time
                start_time = time.time()
                with torch.no_grad():
                    # Prepare input
                    waveform = waveform.to(self._device)
                    # Use apply_model for Demucs inference (not direct call)
                    sources = apply_model(model, waveform.unsqueeze(0), device=self._device)

                    # Extract vocals using index 3 (htdemucs: drums=0, bass=1, other=2, vocals=3)
                    vocals = sources[0, 3].cpu()  # Remove batch dimension, get vocals

                elapsed = time.time() - start_time
                logger.info(f"Full-track separation complete in {elapsed:.1f}s")

                # Check cancellation
                if check_cancellation and check_cancellation():
                    raise DetectionFailedError("Separation cancelled by user", provider_name="mdx")

                # Save vocals
                logger.info(f"Saving vocals to: {destination_vocals_filepath}")
                os.makedirs(os.path.dirname(destination_vocals_filepath), exist_ok=True)
                torchaudio.save(destination_vocals_filepath, vocals, sample_rate)

                logger.info(f"Vocals prepared successfully at {destination_vocals_filepath}")

            except Exception as e:
                if "cancelled" in str(e).lower():
                    raise
                raise DetectionFailedError(
                    f"Demucs vocals preparation failed: {e}",
                    provider_name="mdx",
                    cause=e
                )
        else:
            logger.debug(f"Using existing vocals at {destination_vocals_filepath}")

        return destination_vocals_filepath

    def detect_silence_periods(
        self,
        audio_file: str,
        vocals_file: str,
        original_gap_ms: Optional[float] = None,
        check_cancellation: Optional[Callable[[], bool]] = None
    ) -> List[Tuple[float, float]]:
        """
        Detect silence periods using expanding window Demucs scanning.

        **Expanding Window Search Strategy** (NEW - optimized for speed and robustness):
            1. Start with window: [expected_gap ± 7.5s]
            2. Process chunks in window with Demucs separation
            3. If no onset found, expand by 7.5s (max 3 expansions = ±30s)
            4. Only process NEW chunks in each expansion (no redundant work)
            5. Return FIRST onset closest to expected gap

        **Performance** (compared to previous implementations):
            - Metadata accurate (±7.5s): 1-2 Demucs calls → 8-15s (GPU), 15-30s (CPU)
            - Metadata off (±22.5s): 4-6 Demucs calls → 20-40s (GPU), 40-80s (CPU)
            - Handles wrong metadata gracefully via expansion

        **Optimizations Applied**:
            - FP16 precision on GPU for faster inference
            - cuDNN benchmark mode for optimal convolution
            - CPU thread optimization (uses N-1 cores)
            - Vocals caching to reuse in compute_confidence()
            - Optional downsampling to 32kHz for CPU speedup
            - Tuned parameters: 20ms hop, 300ms min duration

        **Energy-based Onset Detection**:
            - Estimate noise floor from first ~800ms of chunk
            - Compute short-time RMS (25ms frames, 20ms hop)
            - Onset when RMS > max(noise_floor + 6.0*sigma, 0.02 RMS) for ≥300ms
            - Use 200ms hysteresis for onset refinement

        Args:
            audio_file: Original audio file for chunked processing
            vocals_file: Pre-separated vocals (not used - we separate during search)
            original_gap_ms: Expected gap position from song metadata (for focused search)
            check_cancellation: Callback returning True if user cancelled

        Returns:
            List of (start_ms, end_ms) tuples for SILENCE regions

        Raises:
            DetectionFailedError: If Demucs scanning fails
        """
        logger.debug("Detecting onset using fast focused search")

        # Use original gap if provided, otherwise assume vocals at start
        expected_gap = original_gap_ms if original_gap_ms is not None else 0.0

        logger.info(f"Starting vocal onset detection (expected gap: {expected_gap:.0f}ms)")
        _flush_logs()
        logger.info(f"Analyzing audio file: {audio_file}")
        _flush_logs()

        try:
            # Scan for first vocal onset using fast focused search
            onset_ms = self._scan_chunks_for_onset(audio_file, expected_gap, check_cancellation)

            if onset_ms is None:
                logger.warning("No vocal onset detected, assuming vocals at start")
                onset_ms = 0.0

            logger.info(f"Detected vocal onset at {onset_ms:.1f}ms "
                        f"(expected: {expected_gap:.1f}ms, diff: {abs(onset_ms - expected_gap):.1f}ms)")

            # Convert onset to silence period
            # Return one silence period from 0 to onset
            if onset_ms > 0:
                silence_periods = [(0.0, onset_ms)]
            else:
                silence_periods = []

            logger.debug(f"Detected {len(silence_periods)} silence periods")
            return silence_periods

        except Exception as e:
            if "cancelled" in str(e).lower():
                raise
            raise DetectionFailedError(
                f"MDX onset detection failed: {e}",
                provider_name="mdx",
                cause=e
            )

    def compute_confidence(
        self,
        audio_file: str,
        detected_gap_ms: float,
        check_cancellation: Optional[Callable[[], bool]] = None
    ) -> float:
        """
        Compute confidence based on SNR (Signal-to-Noise Ratio) at onset.

        Delegates to confidence module which uses cached vocals when available.

        Args:
            audio_file: Original audio file
            detected_gap_ms: Detected gap position in milliseconds
            check_cancellation: Callback returning True if user cancelled

        Returns:
            Confidence score in range [0.0, 1.0]
        """
        return compute_confidence_score(
            audio_file=audio_file,
            detected_gap_ms=detected_gap_ms,
            vocals_cache=self._vocals_cache.cache_dict,
            separate_vocals_fn=self._separate_vocals_chunk,
            check_cancellation=check_cancellation
        )

    def get_method_name(self) -> str:
        """Return provider identifier."""
        return "mdx"

    # ============================================================================
    # Private helper methods for chunked scanning
    # ============================================================================

    def _scan_chunks_for_onset(
        self,
        audio_file: str,
        expected_gap_ms: float,
        check_cancellation: Optional[Callable[[], bool]] = None
    ) -> Optional[float]:
        """
        Expanding window vocal onset detection around expected gap position.

        Strategy: Start with small window, expand only if no onset found.
        This balances speed (small window when metadata is accurate) with
        robustness (expands when metadata is wrong).

        Implementation:
            1. Start with window: [expected_gap ± initial_radius]
            2. Process chunks in this window with Demucs separation
            3. If no onset found, expand by radius_increment (max 3 expansions)
            4. Only process NEW chunks in each expansion (not redundant work)
            5. Return first onset closest to expected gap

        Performance:
            - If metadata accurate (±7.5s): 1-2 Demucs calls (~8-15s)
            - If metadata off (±22.5s): 4-6 Demucs calls (~20-40s)
            - Falls back gracefully when metadata is very wrong

        Args:
            audio_file: Path to audio file
            expected_gap_ms: Expected gap position from song metadata (ms)
            check_cancellation: Cancellation callback

        Returns:
            Absolute timestamp in milliseconds of first vocal onset, or None
        """
        # Check feature flag for refactored implementation
        from common.feature_flags import FeatureFlags
        flags = FeatureFlags.from_config(self.config)
        
        if flags.USE_MODULAR_MDX_SCANNING:
            from utils.providers.mdx.scanner import scan_for_onset_refactored
            
            # Get audio duration
            info = torchaudio.info(audio_file)
            total_duration_ms = (info.num_frames / info.sample_rate) * 1000.0
            
            logger.debug("Using refactored MDX scanner (modular architecture)")
            return scan_for_onset_refactored(
                audio_file=audio_file,
                expected_gap_ms=expected_gap_ms,
                model=self._get_demucs_model(),
                device=self._device,
                config=self.mdx_config,
                vocals_cache=self._vocals_cache,
                total_duration_ms=total_duration_ms,
                check_cancellation=check_cancellation
            )
        
        # Legacy implementation
        logger.debug("Using legacy MDX scanner")
        try:
            # Get audio info
            logger.info("Loading audio file info...")
            _flush_logs()
            info = torchaudio.info(audio_file)
            sample_rate = info.sample_rate
            total_duration_ms = (info.num_frames / sample_rate) * 1000.0

            logger.info(f"Audio file: {total_duration_ms/1000:.1f}s duration, {sample_rate}Hz sample rate")
            _flush_logs()

            # Track all processed chunks to avoid redundant work
            processed_chunks = set()  # Set of (chunk_start_ms, chunk_end_ms)
            all_onsets = []

            # Expanding search loop
            current_radius_ms = self.mdx_config.initial_radius_ms
            expansion_num = 0

            while expansion_num <= self.mdx_config.max_expansions:
                # Calculate current search window
                search_start_ms = max(0, expected_gap_ms - current_radius_ms)
                search_end_ms = min(total_duration_ms, expected_gap_ms + current_radius_ms)

                logger.info(f"Expanding search #{expansion_num}: "
                            f"radius=±{current_radius_ms/1000:.1f}s, "
                            f"window {search_start_ms/1000:.1f}s - {search_end_ms/1000:.1f}s")
                _flush_logs()

                # Process chunks in current window (skip already processed)
                chunk_duration_s = self.mdx_config.chunk_duration_ms / 1000.0
                chunk_hop_s = (self.mdx_config.chunk_duration_ms - self.mdx_config.chunk_overlap_ms) / 1000.0
                chunk_start_s = search_start_ms / 1000.0
                chunks_processed = 0

                while chunk_start_s < search_end_ms / 1000.0:
                    # Check cancellation
                    if check_cancellation and check_cancellation():
                        raise DetectionFailedError("Search cancelled by user", provider_name="mdx")

                    # Calculate chunk boundaries
                    chunk_start_ms = chunk_start_s * 1000.0
                    chunk_end_ms = min((chunk_start_s + chunk_duration_s) * 1000.0, total_duration_ms)
                    chunk_key = (int(chunk_start_ms), int(chunk_end_ms))

                    # Skip if already processed
                    if chunk_key in processed_chunks:
                        chunk_start_s += chunk_hop_s
                        continue

                    processed_chunks.add(chunk_key)
                    chunks_processed += 1

                    # Load chunk
                    frame_offset = int(chunk_start_s * sample_rate)
                    num_frames = min(
                        int(chunk_duration_s * sample_rate),
                        info.num_frames - frame_offset
                    )

                    if num_frames <= 0:
                        break

                    logger.info(f"Loading chunk at {chunk_start_s:.1f}s-{chunk_start_s + chunk_duration_s:.1f}s "
                                f"(expansion #{expansion_num}, chunk {chunks_processed+1})")
                    _flush_logs()

                    # Suppress torchaudio MP3 warning
                    import warnings
                    with warnings.catch_warnings():
                        warnings.filterwarnings("ignore", message=".*MPEG_LAYER_III.*")
                        waveform, _ = torchaudio.load(
                            audio_file,
                            frame_offset=frame_offset,
                            num_frames=num_frames
                        )

                    # Convert to stereo if needed
                    if waveform.shape[0] == 1:
                        waveform = waveform.repeat(2, 1)

                    # Apply optional downsampling for CPU speedup
                    if self.mdx_config.resample_hz > 0 and sample_rate != self.mdx_config.resample_hz:
                        waveform = torchaudio.functional.resample(waveform, sample_rate, self.mdx_config.resample_hz)
                        current_sample_rate = self.mdx_config.resample_hz
                    else:
                        current_sample_rate = sample_rate

                    # Separate vocals with Demucs (with GPU optimizations)
                    vocals = self._separate_vocals_chunk(waveform, current_sample_rate, check_cancellation)

                    # Cache vocals for potential reuse in compute_confidence
                    self._vocals_cache.put(audio_file, chunk_start_ms, chunk_end_ms, vocals)

                    # Detect onset in this chunk
                    onset_ms = self._detect_onset_in_vocal_chunk(vocals, current_sample_rate, chunk_start_ms)

                    if onset_ms is not None:
                        # Check if this is a new detection (not duplicate from overlap)
                        is_new = True
                        for existing_onset in all_onsets:
                            if abs(onset_ms - existing_onset) < 1000:  # Within 1 second
                                is_new = False
                                break

                        if is_new:
                            all_onsets.append(onset_ms)
                            logger.info(f"Found vocal onset at {onset_ms:.0f}ms "
                                        f"(distance from expected: {abs(onset_ms - expected_gap_ms):.0f}ms)")

                    # Move to next chunk
                    chunk_start_s += chunk_hop_s

                logger.info(f"Expansion #{expansion_num} complete: processed {chunks_processed} new chunks, "
                            f"found {len(all_onsets)} total onset(s) so far")

                # If we found onsets, return the closest one
                if all_onsets:
                    logger.info("Onset(s) detected! Finding closest to expected position...")
                    all_onsets_sorted = sorted(all_onsets, key=lambda x: abs(x - expected_gap_ms))
                    closest = all_onsets_sorted[0]

                    logger.info(f"Returning closest onset: {closest:.0f}ms "
                                f"(expected: {expected_gap_ms:.0f}ms, diff: {abs(closest - expected_gap_ms):.0f}ms)")
                    return closest

                # No onset found, expand search if we haven't hit max expansions
                if expansion_num < self.mdx_config.max_expansions:
                    expansion_num += 1
                    current_radius_ms += self.mdx_config.radius_increment_ms
                    logger.info(f"No onset found, expanding to ±{current_radius_ms/1000:.1f}s")
                else:
                    logger.info(f"Reached max expansions ({self.mdx_config.max_expansions}), no onset found")
                    break

            # No onset found after all expansions
            logger.warning(f"No onset detected after {expansion_num+1} expansions")
            return None

        except Exception as e:
            if "cancelled" in str(e).lower():
                raise
            logger.error(f"MDX expanding search failed: {e}")
            raise

    def _separate_vocals_chunk(
        self,
        waveform: torch.Tensor,
        sample_rate: int,
        check_cancellation: Optional[Callable[[], bool]] = None
    ) -> np.ndarray:
        """
        Separate vocals from audio chunk using Demucs (delegates to separator module).

        Args:
            waveform: Audio waveform tensor (channels, samples)
            sample_rate: Sample rate of audio
            check_cancellation: Cancellation callback

        Returns:
            Vocals-only numpy array (channels, samples)
        """
        model = self._get_demucs_model()
        return separate_vocals_chunk(
            model=model,
            waveform=waveform,
            sample_rate=sample_rate,
            device=self._device,
            use_fp16=self.mdx_config.use_fp16,
            check_cancellation=check_cancellation
        )

    def _detect_onset_in_vocal_chunk(
        self,
        vocal_audio: np.ndarray,
        sample_rate: int,
        chunk_start_ms: float
    ) -> Optional[float]:
        """
        Detect vocal onset in a vocal stem chunk (delegates to detection module).

        Args:
            vocal_audio: Numpy array of vocal stem audio (channels, samples)
            sample_rate: Audio sample rate
            chunk_start_ms: Chunk start position in original audio (ms)

        Returns:
            Absolute timestamp in milliseconds of onset, or None if not found
        """
        return detect_onset_in_vocal_chunk(
            vocal_audio=vocal_audio,
            sample_rate=sample_rate,
            chunk_start_ms=chunk_start_ms,
            config=self.mdx_config
        )
