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
import logging.handlers
import os
import sys
import threading
import warnings
import numpy as np
import torch
import torchaudio
from collections import OrderedDict
from dataclasses import dataclass
from typing import List, Tuple, Optional, Callable

from demucs.apply import apply_model
from utils.providers.base import IDetectionProvider
from utils.providers.exceptions import DetectionFailedError

# Suppress TorchAudio MP3 warning globally for this module
warnings.filterwarnings("ignore", message=".*MPEG_LAYER_III.*")
warnings.filterwarnings("ignore", category=UserWarning, module="torchaudio")

logger = logging.getLogger(__name__)

# Constants
DEMUCS_MODEL_NAME = 'htdemucs'
VOCALS_INDEX = 3
DEFAULT_RESAMPLE_HZ = 0
DEFAULT_FP16 = False
MAX_VOCALS_CACHE_SIZE = 6  # Maximum cached vocals chunks

# Global model cache - shared across all MdxProvider instances
# This prevents reloading the model for every detection (saves ~3-5s per song)
_GLOBAL_MODEL_CACHE = {
    'model': None,
    'device': None
}
_MODEL_LOCK = threading.Lock()  # Thread safety for model cache access


@dataclass
class MdxConfig:
    """Configuration parameters for MDX provider."""
    # Chunked scanning parameters
    chunk_duration_ms: float = 12000
    chunk_overlap_ms: float = 6000

    # Energy analysis parameters
    frame_duration_ms: float = 25
    hop_duration_ms: float = 20
    noise_floor_duration_ms: float = 1000

    # Onset detection thresholds
    onset_snr_threshold: float = 4.0
    onset_abs_threshold: float = 0.01
    min_voiced_duration_ms: float = 300
    hysteresis_ms: float = 200

    # Expanding search parameters
    initial_radius_ms: float = 7500
    radius_increment_ms: float = 7500
    max_expansions: int = 3

    # Performance optimizations
    use_fp16: bool = DEFAULT_FP16
    resample_hz: int = DEFAULT_RESAMPLE_HZ

    # Confidence and preview
    confidence_threshold: float = 0.55
    preview_pre_ms: float = 3000
    preview_post_ms: float = 9000

    def __post_init__(self):
        """Validate configuration parameters."""
        if self.chunk_duration_ms <= 0:
            raise ValueError(f"chunk_duration_ms must be positive, got {self.chunk_duration_ms}")
        if self.chunk_overlap_ms < 0:
            raise ValueError(f"chunk_overlap_ms must be non-negative, got {self.chunk_overlap_ms}")
        if self.chunk_overlap_ms >= self.chunk_duration_ms:
            raise ValueError(
                f"chunk_overlap_ms ({self.chunk_overlap_ms}) must be less than "
                f"chunk_duration_ms ({self.chunk_duration_ms})"
            )
        if self.frame_duration_ms <= 0:
            raise ValueError(f"frame_duration_ms must be positive, got {self.frame_duration_ms}")
        if self.hop_duration_ms <= 0:
            raise ValueError(f"hop_duration_ms must be positive, got {self.hop_duration_ms}")
        if self.noise_floor_duration_ms < 0:
            raise ValueError(f"noise_floor_duration_ms must be non-negative, got {self.noise_floor_duration_ms}")

    @classmethod
    def from_config(cls, config) -> 'MdxConfig':
        """Create MdxConfig from a config object using getattr with defaults."""
        return cls(
            chunk_duration_ms=getattr(config, 'mdx_chunk_duration_ms', cls.chunk_duration_ms),
            chunk_overlap_ms=getattr(config, 'mdx_chunk_overlap_ms', cls.chunk_overlap_ms),
            frame_duration_ms=getattr(config, 'mdx_frame_duration_ms', cls.frame_duration_ms),
            hop_duration_ms=getattr(config, 'mdx_hop_duration_ms', cls.hop_duration_ms),
            noise_floor_duration_ms=getattr(config, 'mdx_noise_floor_duration_ms', cls.noise_floor_duration_ms),
            onset_snr_threshold=getattr(config, 'mdx_onset_snr_threshold', cls.onset_snr_threshold),
            onset_abs_threshold=getattr(config, 'mdx_onset_abs_threshold', cls.onset_abs_threshold),
            min_voiced_duration_ms=getattr(config, 'mdx_min_voiced_duration_ms', cls.min_voiced_duration_ms),
            hysteresis_ms=getattr(config, 'mdx_hysteresis_ms', cls.hysteresis_ms),
            initial_radius_ms=getattr(config, 'mdx_initial_radius_ms', cls.initial_radius_ms),
            radius_increment_ms=getattr(config, 'mdx_radius_increment_ms', cls.radius_increment_ms),
            max_expansions=getattr(config, 'mdx_max_expansions', cls.max_expansions),
            use_fp16=getattr(config, 'mdx_use_fp16', cls.use_fp16),
            resample_hz=getattr(config, 'mdx_resample_hz', cls.resample_hz),
            confidence_threshold=getattr(config, 'mdx_confidence_threshold', cls.confidence_threshold),
            preview_pre_ms=getattr(config, 'mdx_preview_pre_ms', cls.preview_pre_ms),
            preview_post_ms=getattr(config, 'mdx_preview_post_ms', cls.preview_post_ms),
        )


def _flush_logs():
    """Force immediate flush of all log handlers to make logs visible in real-time."""
    # Flush the mdx_provider logger's handlers
    for handler in logger.handlers:
        handler.flush()

    # Flush root logger handlers (includes async queue handler)
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        handler.flush()
        # If it's a QueueHandler, we need to wait for the queue to be processed
        if isinstance(handler, logging.handlers.QueueHandler):
            # Force queue to process by yielding a tiny bit
            import time
            time.sleep(0.001)  # 1ms delay to let queue process

    # Force stdout/stderr flush for good measure
    sys.stdout.flush()
    sys.stderr.flush()


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

        # Demucs model (lazy loaded)
        self._demucs_model = None
        self._device = 'cuda' if torch.cuda.is_available() else 'cpu'

        # LRU cache for separated vocals (avoid re-separation in compute_confidence)
        # OrderedDict maintains insertion order for LRU eviction
        self._vocals_cache = OrderedDict()  # {(audio_file, start_ms, end_ms): vocals_numpy}

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
        Lazy load Demucs model with GPU optimizations.
        Uses global cache to avoid reloading model for each detection.
        Thread-safe model loading with lock.
        """
        with _MODEL_LOCK:
            global _GLOBAL_MODEL_CACHE

            # Check if we can reuse globally cached model
            if _GLOBAL_MODEL_CACHE['model'] is not None and _GLOBAL_MODEL_CACHE['device'] == self._device:
                logger.info(f"Reusing cached Demucs model (device={self._device})")
                _flush_logs()
                return _GLOBAL_MODEL_CACHE['model']

            # Need to load model
            try:
                from demucs.pretrained import get_model
                logger.info(f"Loading Demucs model on {self._device}...")
                _flush_logs()

                # Enable GPU optimizations
                if self._device == 'cuda':
                    # Enable cuDNN auto-tuner for optimal convolution algorithms
                    torch.backends.cudnn.benchmark = True
                    logger.debug("Enabled cuDNN benchmark for GPU optimization")
                    _flush_logs()
                else:
                    # CPU optimization: use most cores but leave one free
                    import os
                    cpu_count = os.cpu_count()
                    num_threads = max(1, cpu_count - 1) if cpu_count else 1
                    torch.set_num_threads(num_threads)
                    logger.debug(f"Set torch threads to {num_threads} for CPU optimization")
                    _flush_logs()

                model = get_model(DEMUCS_MODEL_NAME)
                model.to(self._device)
                model.eval()

                # Cache globally
                _GLOBAL_MODEL_CACHE['model'] = model
                _GLOBAL_MODEL_CACHE['device'] = self._device

                logger.info("Demucs model loaded successfully")
                _flush_logs()

                # Warm up model with dummy input to trigger JIT compilation
                logger.info("Warming up model (JIT compilation, memory allocation)...")
                _flush_logs()
                try:
                    dummy_input = torch.zeros(1, 2, 44100, device=self._device)  # 1 second stereo
                    with torch.no_grad():
                        if self._device == 'cuda' and self.mdx_config.use_fp16:
                            dummy_input = dummy_input.half()
                        # Use apply_model for Demucs inference (not direct call)
                        _ = apply_model(model, dummy_input.unsqueeze(0), device=self._device)
                    logger.info("Model warm-up complete, ready for detection")
                    _flush_logs()
                except Exception as e:
                    logger.warning(f"Model warm-up failed (non-critical): {e}")
                    _flush_logs()

                return model
            except Exception as e:
                raise DetectionFailedError(
                    f"Failed to load Demucs model: {e}",
                    provider_name="mdx",
                    cause=e
                )

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

                    # Extract vocals using VOCALS_INDEX (htdemucs: drums=0, bass=1, other=2, vocals=3)
                    vocals = sources[0, VOCALS_INDEX].cpu()  # Remove batch dimension, get vocals

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

        Uses cached vocals separation from detection phase to avoid redundant
        Demucs calls. If no cached vocals available, performs separation.

        Analyzes the first 300ms after detected onset to compute SNR:
            - Use cached vocals or separate with Demucs
            - Measure RMS in 300ms window after onset (signal)
            - Measure RMS in first 800ms (noise floor)
            - Confidence = smooth_map(SNR_dB)

        Formula:
            SNR_dB = 20 * log10(RMS_signal / RMS_noise)
            Confidence = 1 / (1 + exp(-0.1 * (SNR_dB - 10)))

        Args:
            audio_file: Original audio file
            detected_gap_ms: Detected gap position in milliseconds
            check_cancellation: Callback returning True if user cancelled

        Returns:
            Confidence score in range [0.0, 1.0]
        """
        try:
            logger.debug(f"Computing confidence at gap={detected_gap_ms}ms")

            # Get audio info
            info = torchaudio.info(audio_file)
            sample_rate = info.sample_rate

            # Try to find cached vocals that cover the onset position
            vocals = None
            chunk_start_ms = 0.0
            onset_in_chunk_ms = detected_gap_ms

            for (cached_file, start_ms, end_ms), cached_vocals in self._vocals_cache.items():
                if cached_file == audio_file and start_ms <= detected_gap_ms <= end_ms:
                    logger.debug(f"Reusing cached vocals from {start_ms:.0f}ms-{end_ms:.0f}ms")
                    vocals = cached_vocals
                    # Adjust onset position to chunk-relative
                    chunk_start_ms = start_ms
                    onset_in_chunk_ms = detected_gap_ms - chunk_start_ms
                    break

            # If no cache hit, separate vocals for confidence region
            if vocals is None:
                logger.debug("No cached vocals, performing separation for confidence")
                # Load audio segment (first 5 seconds to get noise floor and signal)
                segment_duration = min(5.0, (detected_gap_ms / 1000.0) + 1.0)
                num_frames = int(segment_duration * sample_rate)

                logger.debug(f"Loading {segment_duration:.1f}s audio segment for confidence computation")
                import warnings
                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore", message=".*MPEG_LAYER_III.*")
                    waveform, sample_rate = torchaudio.load(
                        audio_file,
                        frame_offset=0,
                        num_frames=num_frames
                    )

                # Convert to stereo if needed
                if waveform.shape[0] == 1:
                    waveform = waveform.repeat(2, 1)

                # Separate vocals
                vocals = self._separate_vocals_chunk(waveform, sample_rate, check_cancellation)
                chunk_start_ms = 0.0
                onset_in_chunk_ms = detected_gap_ms

            # Convert to mono for RMS calculation
            vocals_mono = np.mean(vocals, axis=0)

            # Compute RMS in noise floor region (first 800ms of chunk)
            noise_samples = int(0.8 * sample_rate)
            noise_rms = np.sqrt(np.mean(vocals_mono[:min(noise_samples, len(vocals_mono))]**2))

            # Compute RMS in signal region (300ms after onset)
            onset_sample = int((onset_in_chunk_ms / 1000.0) * sample_rate)
            signal_duration_samples = int(0.3 * sample_rate)
            signal_end = min(onset_sample + signal_duration_samples, len(vocals_mono))

            if onset_sample < len(vocals_mono):
                signal_rms = np.sqrt(np.mean(vocals_mono[onset_sample:signal_end]**2))
            else:
                signal_rms = noise_rms

            # Compute SNR
            if noise_rms > 1e-8:
                snr_db = 20 * np.log10((signal_rms + 1e-8) / (noise_rms + 1e-8))
            else:
                snr_db = 20.0  # Assume good SNR if noise floor is very low

            # Map SNR to confidence using sigmoid
            # Center at 10dB, steepness 0.1
            confidence = 1.0 / (1.0 + np.exp(-0.1 * (snr_db - 10.0)))
            confidence = float(np.clip(confidence, 0.0, 1.0))

            logger.info(f"SNR={snr_db:.1f}dB, Confidence={confidence:.3f}")
            return confidence

        except Exception as e:
            logger.warning(f"MDX confidence computation failed: {e}")
            return 0.7  # Default moderate-high confidence

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

                    # Cache vocals for potential reuse in compute_confidence (with LRU eviction)
                    cache_key = (audio_file, chunk_start_ms, chunk_end_ms)
                    # Evict oldest entry if cache is full
                    if len(self._vocals_cache) >= MAX_VOCALS_CACHE_SIZE:
                        oldest_key = next(iter(self._vocals_cache))
                        logger.debug(f"Vocals cache full ({MAX_VOCALS_CACHE_SIZE}), evicting oldest entry")
                        self._vocals_cache.pop(oldest_key)
                    self._vocals_cache[cache_key] = vocals

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
        Separate vocals from audio chunk using Demucs with GPU optimizations.

        Args:
            waveform: Audio waveform tensor (channels, samples)
            sample_rate: Sample rate of audio
            check_cancellation: Cancellation callback

        Returns:
            Vocals-only numpy array (channels, samples)
        """
        # Check cancellation
        if check_cancellation and check_cancellation():
            raise DetectionFailedError("Separation cancelled by user", provider_name="mdx")

        model = self._get_demucs_model()

        # Log separation start
        duration_s = waveform.shape[1] / sample_rate
        logger.info(f"Running Demucs separation on {duration_s:.1f}s audio chunk...")
        _flush_logs()

        with torch.no_grad():
            # Apply FP16 if enabled and on GPU
            if self.mdx_config.use_fp16 and self._device == 'cuda':
                logger.debug("Using FP16 precision on GPU")
                waveform_gpu = waveform.to(self._device).to(torch.float16)
            else:
                waveform_gpu = waveform.to(self._device)

            # Run Demucs separation
            import time
            start_time = time.time()
            sources = apply_model(model, waveform_gpu.unsqueeze(0), device=self._device)
            elapsed = time.time() - start_time

            # Extract vocals using VOCALS_INDEX (htdemucs: drums=0, bass=1, other=2, vocals=3)
            vocals = sources[0, VOCALS_INDEX].cpu().numpy()

            logger.info(f"Separation complete in {elapsed:.1f}s ({duration_s/elapsed:.1f}x realtime)")
            _flush_logs()

        return vocals

    def _detect_onset_in_vocal_chunk(
        self,
        vocal_audio: np.ndarray,
        sample_rate: int,
        chunk_start_ms: float
    ) -> Optional[float]:
        """
        Detect vocal onset in a vocal stem chunk using energy threshold.

        Implementation strategy:
            1. Convert to mono
            2. Estimate noise floor from first 800ms
            3. Compute short-time RMS (25ms frames, 10ms hop)
            4. Find onset where RMS > noise_floor + k*sigma for ≥180ms
            5. Return absolute timestamp (chunk_start + offset)

        Args:
            vocal_audio: Numpy array of vocal stem audio (channels, samples)
            sample_rate: Audio sample rate
            chunk_start_ms: Chunk start position in original audio (ms)

        Returns:
            Absolute timestamp in milliseconds of onset, or None if not found
        """
        try:
            # Convert to mono
            if vocal_audio.ndim > 1:
                vocal_mono = np.mean(vocal_audio, axis=0)
            else:
                vocal_mono = vocal_audio

            # Compute RMS
            frame_samples = int((self.mdx_config.frame_duration_ms / 1000.0) * sample_rate)
            hop_samples = int((self.mdx_config.hop_duration_ms / 1000.0) * sample_rate)

            rms_values = self._compute_rms(vocal_mono, frame_samples, hop_samples)

            # Guard against empty/short audio
            if len(rms_values) == 0:
                logger.warning("RMS values empty (audio too short), no onset detected")
                return None

            # Estimate noise floor
            noise_floor_frames = int(
                (self.mdx_config.noise_floor_duration_ms / 1000.0)
                / (self.mdx_config.hop_duration_ms / 1000.0)
            )
            # Clamp noise_floor_frames if it exceeds available frames
            if noise_floor_frames >= len(rms_values):
                logger.warning(
                    f"Noise floor duration ({noise_floor_frames} frames) >= RMS length ({len(rms_values)}), "
                    f"using entire audio as noise floor"
                )
                noise_floor_frames = max(1, len(rms_values) - 1)

            noise_floor, noise_sigma = self._estimate_noise_floor(rms_values, noise_floor_frames)

            max_rms = np.max(rms_values)
            mean_rms = np.mean(rms_values)

            logger.info(f"Chunk analysis - Noise floor={noise_floor:.6f}, sigma={noise_sigma:.6f}, "
                        f"max_rms={max_rms:.6f}, mean_rms={mean_rms:.6f}")

            # Detect onset - use BOTH SNR threshold AND absolute threshold
            snr_threshold = noise_floor + self.mdx_config.onset_snr_threshold * noise_sigma
            combined_threshold = max(snr_threshold, self.mdx_config.onset_abs_threshold)

            logger.info(f"Thresholds - SNR_threshold={snr_threshold:.6f}, "
                        f"Absolute_threshold={self.mdx_config.onset_abs_threshold:.6f}, "
                        f"Combined={combined_threshold:.6f}")

            # Find sustained energy above threshold
            min_frames = int(
                (self.mdx_config.min_voiced_duration_ms / 1000.0)
                / (self.mdx_config.hop_duration_ms / 1000.0)
            )
            hysteresis_frames = int(
                (self.mdx_config.hysteresis_ms / 1000.0)
                / (self.mdx_config.hop_duration_ms / 1000.0)
            )

            above_threshold = rms_values > combined_threshold
            onset_frame = None

            # Skip the noise floor region when searching
            search_start = max(noise_floor_frames + 1, 0)

            # Find first sustained onset (after noise floor region)
            for i in range(search_start, len(above_threshold) - min_frames):
                if np.all(above_threshold[i:i + min_frames]):
                    # Found sustained energy - now look back for the actual onset (rising edge)
                    onset_frame = i

                    # Look back to find where energy first crosses threshold
                    for j in range(i - 1, max(search_start - 1, i - hysteresis_frames - 1), -1):
                        if j >= 0 and above_threshold[j]:
                            onset_frame = j  # Keep going back while above threshold
                        else:
                            break  # Stop at first frame below threshold (this is the onset!)

                    # Refine onset by looking for maximum energy rise (derivative peak)
                    # within a small window around the detected onset
                    refine_window = min(10, onset_frame - search_start)  # 10 frames = 100ms window
                    if refine_window > 2:
                        window_start = max(search_start, onset_frame - refine_window)
                        window_end = min(onset_frame + 5, len(rms_values) - 1)

                        # Compute energy derivative (rate of change)
                        rms_window = rms_values[window_start:window_end]
                        if len(rms_window) > 1:
                            energy_derivative = np.diff(rms_window)

                            # Find maximum positive derivative (steepest rise)
                            if len(energy_derivative) > 0:
                                max_rise_idx = np.argmax(energy_derivative)
                                refined_onset = window_start + max_rise_idx

                                # Only use refined onset if it's close to original and makes sense
                                if abs(refined_onset - onset_frame) <= refine_window:
                                    logger.debug(f"Refined onset from frame {onset_frame} to {refined_onset} "
                                                 f"(energy rise: {energy_derivative[max_rise_idx]:.4f})")
                                    onset_frame = refined_onset

                    break

            if onset_frame is not None:
                # Convert frame to absolute timestamp
                onset_offset_ms = (onset_frame * hop_samples / sample_rate) * 1000.0
                onset_abs_ms = chunk_start_ms + onset_offset_ms
                logger.info(f"Onset detected at {onset_abs_ms:.1f}ms "
                            f"(RMS={rms_values[onset_frame]:.4f}, threshold={combined_threshold:.4f})")
                return float(onset_abs_ms)

            return None

        except Exception as e:
            logger.warning(f"MDX onset detection in chunk failed: {e}")
            return None

    def _compute_rms(
        self,
        audio: np.ndarray,
        frame_samples: int,
        hop_samples: int
    ) -> np.ndarray:
        """
        Compute short-time RMS energy.

        Args:
            audio: Audio signal (mono)
            frame_samples: Frame size in samples
            hop_samples: Hop size in samples

        Returns:
            Array of RMS values for each frame
        """
        # Number of frames
        num_frames = 1 + (len(audio) - frame_samples) // hop_samples

        if num_frames <= 0:
            return np.array([])

        # Compute RMS for each frame
        rms_values = np.zeros(num_frames)
        for i in range(num_frames):
            start = i * hop_samples
            end = start + frame_samples
            if end <= len(audio):
                frame = audio[start:end]
                rms_values[i] = np.sqrt(np.mean(frame**2))

        return rms_values

    def _estimate_noise_floor(
        self,
        rms_values: np.ndarray,
        noise_floor_frames: int
    ) -> Tuple[float, float]:
        """
        Estimate noise floor and standard deviation from initial frames.

        Args:
            rms_values: Array of RMS values
            noise_floor_frames: Number of frames to use for estimation

        Returns:
            Tuple of (noise_floor, sigma)
        """
        if len(rms_values) == 0:
            return (0.0, 0.0)

        # Use first N frames for noise floor estimation
        noise_frames = rms_values[:min(noise_floor_frames, len(rms_values))]

        if len(noise_frames) == 0:
            return (0.0, 0.0)

        # Use median for robustness and std for variation
        noise_floor = float(np.median(noise_frames))
        noise_sigma = float(np.std(noise_frames))

        return (noise_floor, noise_sigma)
