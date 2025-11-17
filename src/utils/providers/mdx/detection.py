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


def compute_rms(audio: np.ndarray, frame_samples: int, hop_samples: int) -> np.ndarray:
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


def estimate_noise_floor(rms_values: np.ndarray, noise_floor_frames: int) -> Tuple[float, float]:
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
    noise_frames = rms_values[: min(noise_floor_frames, len(rms_values))]

    if len(noise_frames) == 0:
        return (0.0, 0.0)

    # Use median for robustness and std for variation
    noise_floor = float(np.median(noise_frames))
    noise_sigma = float(np.std(noise_frames))

    logger.debug(f"Noise floor estimation: using {len(noise_frames)} frames out of {len(rms_values)} total")
    logger.debug(f"Noise frames used: {noise_frames[:20] if len(noise_frames) > 20 else noise_frames}")
    logger.debug(f"Calculated: median={noise_floor:.6f}, std={noise_sigma:.6f}")

    return (noise_floor, noise_sigma)


def detect_onset_in_vocal_chunk(
    vocal_audio: np.ndarray, sample_rate: int, chunk_start_ms: float, config: MdxConfig
) -> Optional[float]:
    """
    Detect vocal onset in a vocal stem chunk using silence-to-sound transition.

    NEW STRATEGY (silence-centric):
        1. Convert to mono and compute short-time RMS energy
        2. Estimate noise floor from initial frames
        3. Find ALL silence regions (energy below threshold)
        4. Identify the longest/earliest significant silence
        5. Return the END of that silence (silence→sound boundary) as the onset

    This approach correctly handles cases where vocals start quietly and get louder,
    by finding the actual silence boundary rather than the first sustained loud vocal.

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

        logger.debug(f"Vocal audio shape: {vocal_audio.shape}, mono shape: {vocal_mono.shape}, dtype: {vocal_mono.dtype}")

        # Compute RMS
        frame_samples = int((config.frame_duration_ms / 1000.0) * sample_rate)
        hop_samples = int((config.hop_duration_ms / 1000.0) * sample_rate)

        rms_values = compute_rms(vocal_mono, frame_samples, hop_samples)

        # Guard against empty/short audio
        if len(rms_values) == 0:
            logger.warning("RMS values empty (audio too short), no onset detected")
            return None

        # Estimate noise floor
        noise_floor_frames = int((config.noise_floor_duration_ms / 1000.0) / (config.hop_duration_ms / 1000.0))
        # Clamp noise_floor_frames if it exceeds available frames
        if noise_floor_frames >= len(rms_values):
            logger.warning(
                f"Noise floor duration ({noise_floor_frames} frames) >= RMS length ({len(rms_values)}), "
                f"using entire audio as noise floor"
            )
            noise_floor_frames = max(1, len(rms_values) - 1)

        logger.debug(f"Noise floor config: duration={config.noise_floor_duration_ms}ms, hop={config.hop_duration_ms}ms, calculated frames={noise_floor_frames}")

        noise_floor, noise_sigma = estimate_noise_floor(rms_values, noise_floor_frames)

        max_rms = np.max(rms_values)
        mean_rms = np.mean(rms_values)

        logger.debug(f"First 10 RMS values: {rms_values[:10]}")

        logger.info(
            f"Chunk analysis - Noise floor={noise_floor:.6f}, sigma={noise_sigma:.6f}, "
            f"max_rms={max_rms:.6f}, mean_rms={mean_rms:.6f}"
        )

        # Detect onset - use BOTH SNR threshold AND absolute threshold
        snr_threshold = noise_floor + config.onset_snr_threshold * noise_sigma
        combined_threshold = max(snr_threshold, config.onset_abs_threshold)

        logger.info(
            f"Thresholds - SNR_threshold={snr_threshold:.6f}, "
            f"Absolute_threshold={config.onset_abs_threshold:.6f}, "
            f"Combined={combined_threshold:.6f}"
        )

        # NEW APPROACH: Find the first significant silence→sound transition
        hop_samples = int((config.hop_duration_ms / 1000.0) * sample_rate)
        min_silence_frames = int((config.min_voiced_duration_ms / 1000.0) / (config.hop_duration_ms / 1000.0))
        min_sound_frames = min_silence_frames  # Sound must also sustain for verification

        # Identify frames below/above threshold
        below_threshold = rms_values <= combined_threshold
        above_threshold = ~below_threshold

        # Start search from beginning (don't skip noise floor region - we want to find the FIRST silence)
        search_start = 0

        # Find first significant silence→sound transition
        # Strategy: scan forward looking for pattern: [sustained silence] → [sustained sound]
        onset_frame = None
        i = search_start

        while i < len(below_threshold) - min_silence_frames - min_sound_frames:
            # Check if we have sustained silence starting at i
            if np.all(below_threshold[i : i + min_silence_frames]):
                # Found sustained silence, now check if followed by sustained sound
                silence_end = i + min_silence_frames

                # Look for sound starting after the silence
                for j in range(silence_end, min(silence_end + 50, len(above_threshold) - min_sound_frames)):
                    # Check if we have sustained sound at position j
                    if np.all(above_threshold[j : j + min_sound_frames]):
                        # Found silence→sound transition!
                        onset_frame = j  # Onset is where sound begins
                        logger.info(
                            f"Found silence→sound transition: silence at frames {i}-{silence_end}, "
                            f"sound starts at frame {onset_frame}"
                        )
                        break

                if onset_frame is not None:
                    break  # Found the first transition, stop searching
                else:
                    # No sound after this silence, skip ahead
                    i = silence_end
            else:
                i += 1

        if onset_frame is None:
            logger.info("No silence→sound transition found, falling back to first sustained sound")
            # Fallback: find first sustained sound (original vocal-centric approach)
            for i in range(search_start, len(above_threshold) - min_sound_frames):
                if np.all(above_threshold[i : i + min_sound_frames]):
                    onset_frame = i
                    logger.info(f"Fallback: first sustained sound at frame {onset_frame}")
                    break

        if onset_frame is None:
            logger.info("No onset found")
            return None

        # Refine onset by looking for energy rise pattern
        refine_window = min(10, len(rms_values) - onset_frame - 1)  # 10 frames = 200ms
        if refine_window > 2 and onset_frame < len(rms_values) - 1:
            window_start = max(search_start, onset_frame - 5)  # Look back slightly
            window_end = min(onset_frame + refine_window, len(rms_values))

            # Compute energy derivative
            rms_window = rms_values[window_start:window_end]
            if len(rms_window) > 1:
                energy_derivative = np.diff(rms_window)

                if len(energy_derivative) > 0:
                    # Find first significant positive derivative (rising energy)
                    mean_derivative = np.mean(np.abs(energy_derivative))
                    threshold_derivative = mean_derivative * 0.3  # 30% of mean change

                    first_rise_idx = None
                    for idx, deriv in enumerate(energy_derivative):
                        if deriv > threshold_derivative:
                            first_rise_idx = idx
                            break

                    if first_rise_idx is not None:
                        # Adjust onset to the rising edge
                        refined_onset = window_start + first_rise_idx
                        if refined_onset <= onset_frame:  # Only refine backwards
                            logger.debug(
                                f"Refined onset from frame {onset_frame} to {refined_onset} "
                                f"using energy derivative"
                            )
                            onset_frame = refined_onset

        # Convert frame to absolute timestamp
        onset_offset_ms = (onset_frame * hop_samples / sample_rate) * 1000.0
        onset_abs_ms = chunk_start_ms + onset_offset_ms
        logger.info(
            f"Onset detected at {onset_abs_ms:.1f}ms "
            f"(frame {onset_frame}, RMS={rms_values[min(onset_frame, len(rms_values)-1)]:.4f})"
        )
        return float(onset_abs_ms)

    except Exception as e:
        logger.warning(f"MDX onset detection in chunk failed: {e}")
        return None
