"""
Confidence computation for MDX detection based on SNR (Signal-to-Noise Ratio).

This module computes detection confidence by analyzing the SNR at the detected onset position.
Uses cached vocals from detection phase when available to avoid redundant Demucs separation.
"""

import logging
import numpy as np
from typing import Optional, Callable, OrderedDict
import torchaudio


logger = logging.getLogger(__name__)


def compute_confidence_score(
    audio_file: str,
    detected_gap_ms: float,
    vocals_cache: "OrderedDict",
    separate_vocals_fn: Callable,
    check_cancellation: Optional[Callable[[], bool]] = None,
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
        vocals_cache: OrderedDict mapping (file, start_ms, end_ms) to vocals numpy arrays
        separate_vocals_fn: Function(waveform, sample_rate, check_cancellation) -> vocals_numpy
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

        for (cached_file, start_ms, end_ms), cached_vocals in vocals_cache.items():
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
                waveform, sample_rate = torchaudio.load(audio_file, frame_offset=0, num_frames=num_frames)

            # Convert to stereo if needed
            if waveform.shape[0] == 1:
                waveform = waveform.repeat(2, 1)

            # Separate vocals using provided function
            vocals = separate_vocals_fn(waveform, sample_rate, check_cancellation)
            chunk_start_ms = 0.0
            onset_in_chunk_ms = detected_gap_ms

        # Convert to mono for RMS calculation
        vocals_mono = np.mean(vocals, axis=0)

        # Compute RMS in noise floor region (first 800ms of chunk)
        noise_samples = int(0.8 * sample_rate)
        noise_rms = np.sqrt(np.mean(vocals_mono[: min(noise_samples, len(vocals_mono))] ** 2))

        # Compute RMS in signal region (300ms after onset)
        onset_sample = int((onset_in_chunk_ms / 1000.0) * sample_rate)
        signal_duration_samples = int(0.3 * sample_rate)
        signal_end = min(onset_sample + signal_duration_samples, len(vocals_mono))

        if onset_sample < len(vocals_mono):
            signal_rms = np.sqrt(np.mean(vocals_mono[onset_sample:signal_end] ** 2))
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
