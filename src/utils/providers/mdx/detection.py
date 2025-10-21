"""
Vocal onset detection logic for MDX provider.

Provides energy-based onset detection on separated vocal stems using:
- Short-time RMS energy computation
- Adaptive noise floor estimation
- SNR-based threshold with hysteresis
- Energy derivative refinement for precise onset timing
"""

import logging
from typing import Optional, Tuple

import numpy as np

from utils.providers.mdx.config import MdxConfig

logger = logging.getLogger(__name__)


def compute_rms(
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


def estimate_noise_floor(
    rms_values: np.ndarray,
    noise_floor_frames: int
) -> Tuple[float, float]:
    """
    Estimate noise floor and standard deviation from initial frames.

    Uses median for robustness against outliers.

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


def detect_onset_in_vocal_chunk(
    vocal_audio: np.ndarray,
    sample_rate: int,
    chunk_start_ms: float,
    config: MdxConfig
) -> Optional[float]:
    """
    Detect vocal onset in a vocal stem chunk using energy threshold.

    Implementation strategy:
        1. Convert to mono
        2. Estimate noise floor from first 800ms
        3. Compute short-time RMS (25ms frames, 10ms hop)
        4. Find onset where RMS > noise_floor + k*sigma for ≥180ms
        5. Refine using energy derivative (steepest rise)
        6. Return absolute timestamp (chunk_start + offset)

    Args:
        vocal_audio: Numpy array of vocal stem audio (channels, samples)
        sample_rate: Audio sample rate
        chunk_start_ms: Chunk start position in original audio (ms)
        config: MDX configuration with detection parameters

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
        frame_samples = int((config.frame_duration_ms / 1000.0) * sample_rate)
        hop_samples = int((config.hop_duration_ms / 1000.0) * sample_rate)

        rms_values = compute_rms(vocal_mono, frame_samples, hop_samples)

        # Guard against empty/short audio
        if len(rms_values) == 0:
            logger.warning("RMS values empty (audio too short), no onset detected")
            return None

        # Estimate noise floor
        noise_floor_frames = int(
            (config.noise_floor_duration_ms / 1000.0)
            / (config.hop_duration_ms / 1000.0)
        )
        # Clamp noise_floor_frames if it exceeds available frames
        if noise_floor_frames >= len(rms_values):
            logger.warning(
                f"Noise floor duration ({noise_floor_frames} frames) >= RMS length ({len(rms_values)}), "
                f"using entire audio as noise floor"
            )
            noise_floor_frames = max(1, len(rms_values) - 1)

        noise_floor, noise_sigma = estimate_noise_floor(rms_values, noise_floor_frames)

        max_rms = np.max(rms_values)
        mean_rms = np.mean(rms_values)

        logger.info(f"Chunk analysis - Noise floor={noise_floor:.6f}, sigma={noise_sigma:.6f}, "
                    f"max_rms={max_rms:.6f}, mean_rms={mean_rms:.6f}")

        # Detect onset - use BOTH SNR threshold AND absolute threshold
        snr_threshold = noise_floor + config.onset_snr_threshold * noise_sigma
        combined_threshold = max(snr_threshold, config.onset_abs_threshold)

        logger.info(f"Thresholds - SNR_threshold={snr_threshold:.6f}, "
                    f"Absolute_threshold={config.onset_abs_threshold:.6f}, "
                    f"Combined={combined_threshold:.6f}")

        # Find sustained energy above threshold
        min_frames = int(
            (config.min_voiced_duration_ms / 1000.0)
            / (config.hop_duration_ms / 1000.0)
        )
        hysteresis_frames = int(
            (config.hysteresis_ms / 1000.0)
            / (config.hop_duration_ms / 1000.0)
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

                # Refine onset by looking for energy rise pattern
                # For abrupt onsets: find steepest rise
                # For gradual fade-ins: find first consistent rise
                refine_window = min(15, onset_frame - search_start)  # 15 frames = 300ms window
                if refine_window > 2:
                    window_start = max(search_start, onset_frame - refine_window)
                    window_end = min(onset_frame + 5, len(rms_values) - 1)

                    # Compute energy derivative (rate of change)
                    rms_window = rms_values[window_start:window_end]
                    if len(rms_window) > 1:
                        energy_derivative = np.diff(rms_window)

                        if len(energy_derivative) > 0:
                            # Strategy: Find the first significant positive derivative
                            # This catches gradual fade-ins better than finding the steepest rise
                            mean_derivative = np.mean(np.abs(energy_derivative))
                            threshold_derivative = mean_derivative * 0.5  # 50% of mean change
                            
                            # Find first frame where derivative exceeds threshold (consistent rise)
                            first_rise_idx = None
                            for idx, deriv in enumerate(energy_derivative):
                                if deriv > threshold_derivative:
                                    first_rise_idx = idx
                                    break
                            
                            if first_rise_idx is not None:
                                refined_onset = window_start + first_rise_idx
                                
                                # Only use refined onset if it makes sense (earlier than or close to original)
                                if refined_onset <= onset_frame:
                                    logger.debug(f"Refined onset from frame {onset_frame} to {refined_onset} "
                                                 f"(first rise: {energy_derivative[first_rise_idx]:.4f}, "
                                                 f"threshold: {threshold_derivative:.4f})")
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
