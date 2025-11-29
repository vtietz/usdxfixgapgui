"""
Vocal separation logic for MDX detection.

Provides chunk-based Demucs separation with GPU optimizations (FP16, cuDNN).
"""

import logging
import time
from typing import Optional, Callable

import numpy as np
import torch
from demucs.apply import apply_model

from utils.providers.exceptions import DetectionFailedError
from utils.logging_utils import flush_logs

logger = logging.getLogger(__name__)

# Demucs htdemucs model: drums=0, bass=1, other=2, vocals=3
VOCALS_INDEX = 3


def separate_vocals_chunk(
    model,
    waveform: "torch.Tensor",
    sample_rate: int,
    device: str,
    use_fp16: bool,
    check_cancellation: Optional[Callable[[], bool]] = None,
) -> np.ndarray:
    """
    Separate vocals from audio chunk using Demucs with GPU optimizations.

    Applies device-specific optimizations:
    - FP16 mixed precision on CUDA (if enabled)
    - Batch inference with apply_model

    Args:
        model: Loaded Demucs model
        waveform: Audio waveform tensor (channels, samples)
        sample_rate: Sample rate of audio
        device: Target device ('cuda' or 'cpu')
        use_fp16: Enable FP16 mixed precision (CUDA only)
        check_cancellation: Cancellation callback

    Returns:
        Vocals-only numpy array (channels, samples)

    Raises:
        DetectionFailedError: If cancelled or separation fails
    """
    # Check cancellation
    if check_cancellation and check_cancellation():
        raise DetectionFailedError("Separation cancelled by user", provider_name="mdx")

    # Log separation start
    duration_s = waveform.shape[1] / sample_rate
    logger.debug(f"Running Demucs separation on {duration_s:.1f}s audio chunk...")
    flush_logs()

    with torch.no_grad():
        # Apply FP16 if enabled and on GPU
        if use_fp16 and device == "cuda":
            logger.debug("Using FP16 precision on GPU")
            waveform_gpu = waveform.to(device).to(torch.float16)
        else:
            waveform_gpu = waveform.to(device)

        # Run Demucs separation
        start_time = time.time()
        sources = apply_model(model, waveform_gpu.unsqueeze(0), device=device)
        elapsed = time.time() - start_time

        # Extract vocals using VOCALS_INDEX (htdemucs: drums=0, bass=1, other=2, vocals=3)
        vocals = sources[0, VOCALS_INDEX].cpu().numpy()

        logger.debug(f"Separation complete in {elapsed:.1f}s ({duration_s / elapsed:.1f}x realtime)")
        flush_logs()

    return vocals
