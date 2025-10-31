"""
Separation stub for Tier-2 scanner tests.

Replaces separate_vocals_chunk() to return the right channel as vocals,
simulating perfect separation without running Demucs.
"""

from typing import Optional, Callable

import numpy as np
import torch


def stub_separate_vocals_chunk(
    model,
    waveform: torch.Tensor,
    sample_rate: int,
    device: str,
    use_fp16: bool,
    check_cancellation: Optional[Callable[[], bool]] = None,
) -> np.ndarray:
    """
    Stub for separate_vocals_chunk that returns the right channel as vocals.

    Test audio files have:
    - Left channel: mixture (vocals + instruments)
    - Right channel: isolated vocals (ground truth)

    This stub simulates perfect separation by returning the right channel.

    Args:
        model: Demucs model (unused in stub)
        waveform: Audio waveform tensor (channels, samples)
        sample_rate: Sample rate (unused in stub)
        device: Device (unused in stub)
        use_fp16: FP16 flag (unused in stub)
        check_cancellation: Cancellation callback (unused in stub)

    Returns:
        Right channel as numpy array (channels, samples)
    """
    # Convert to numpy if needed
    if isinstance(waveform, torch.Tensor):
        wave_np = waveform.cpu().numpy()
    else:
        wave_np = waveform

    # Extract right channel (index 1)
    if wave_np.ndim == 2 and wave_np.shape[0] >= 2:
        # Stereo or more: return right channel as stereo (duplicate mono to stereo)
        vocals_mono = wave_np[1:2, :]  # Shape (1, samples)
        vocals_stereo = np.repeat(vocals_mono, 2, axis=0)  # Shape (2, samples)
        return vocals_stereo
    elif wave_np.ndim == 2 and wave_np.shape[0] == 1:
        # Mono: duplicate to stereo
        return np.repeat(wave_np, 2, axis=0)
    elif wave_np.ndim == 1:
        # 1D array: reshape and duplicate
        mono = wave_np[np.newaxis, :]  # Shape (1, samples)
        return np.repeat(mono, 2, axis=0)
    else:
        # Fallback: return as-is
        return wave_np
