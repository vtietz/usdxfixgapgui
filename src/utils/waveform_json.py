"""
Waveform JSON generator for efficient UI visualization.
Creates downsampled waveform data with min/max bins.
"""

import logging
import os
import json
from typing import Optional, Callable

logger = logging.getLogger(__name__)

try:
    import librosa
    import numpy as np

    LIBROSA_AVAILABLE = True
except ImportError:
    LIBROSA_AVAILABLE = False
    # Bind names to avoid 'possibly unbound' type checker diagnostics
    librosa = None  # type: ignore
    np = None  # type: ignore
    logger.warning("librosa not available. Waveform JSON generation will be limited.")


def build_waveform_json(
    audio_file: str,
    output_file: Optional[str] = None,
    bins: int = 2048,
    check_cancellation: Optional[Callable[[], bool]] = None,
) -> str:
    """
    Generate waveform JSON with min/max bins for UI visualization.

    Args:
        audio_file: Path to input audio file
        output_file: Path for output JSON file (defaults to .json next to audio)
        bins: Number of bins to generate
        check_cancellation: Optional cancellation check callback

    Returns:
        Path to generated JSON file
    """
    if not LIBROSA_AVAILABLE:
        logger.warning("librosa not available, using simplified waveform generation")
        return _build_waveform_json_ffmpeg(audio_file, output_file, bins, check_cancellation)

    logger.debug(f"Generating waveform JSON for {audio_file} with {bins} bins")

    # Load audio via librosa with type-narrowing to satisfy static analysis
    assert LIBROSA_AVAILABLE and librosa is not None and np is not None
    from typing import cast, Any

    lib = cast(Any, librosa)
    np_mod = cast(Any, np)
    y, sr = lib.load(audio_file, sr=None, mono=True)

    if check_cancellation and check_cancellation():
        raise Exception("Operation cancelled")

    # Calculate samples per bin
    total_samples = len(y)
    samples_per_bin = max(1, total_samples // bins)

    # Generate min/max for each bin
    waveform_data = []

    for i in range(bins):
        if check_cancellation and check_cancellation():
            raise Exception("Operation cancelled")

        start_idx = i * samples_per_bin
        end_idx = min(start_idx + samples_per_bin, total_samples)

        if start_idx >= total_samples:
            # Fill remaining bins with zeros
            waveform_data.append({"min": 0.0, "max": 0.0})
            continue

        bin_samples = y[start_idx:end_idx]

        if len(bin_samples) > 0:
            min_val = float(np_mod.min(bin_samples))
            max_val = float(np_mod.max(bin_samples))
        else:
            min_val = 0.0
            max_val = 0.0

        waveform_data.append({"min": min_val, "max": max_val})

    # Prepare output data
    output_data = {
        "sample_rate": int(sr),
        "duration_seconds": float(total_samples / sr),
        "bins": bins,
        "samples_per_bin": samples_per_bin,
        "data": waveform_data,
    }

    # Determine output file
    if output_file is None:
        base_name = os.path.splitext(audio_file)[0]
        output_file = f"{base_name}_waveform.json"

    # Save JSON
    logger.debug(f"Saving waveform JSON to {output_file}")
    with open(output_file, "w") as f:
        json.dump(output_data, f, indent=2)

    logger.info(f"Waveform JSON created: {output_file}")
    return output_file


def _build_waveform_json_ffmpeg(
    audio_file: str,
    output_file: Optional[str] = None,
    bins: int = 2048,
    check_cancellation: Optional[Callable[[], bool]] = None,
) -> str:
    """
    Fallback waveform generation using ffmpeg (when librosa unavailable).

    Args:
        audio_file: Path to input audio file
        output_file: Path for output JSON file
        bins: Number of bins to generate
        check_cancellation: Optional cancellation check callback

    Returns:
        Path to generated JSON file
    """
    from utils.cancellable_process import run_cancellable_process
    import tempfile

    logger.debug("Using ffmpeg fallback for waveform JSON generation")

    # Convert to raw PCM samples
    temp_dir = os.path.dirname(audio_file)
    raw_file = tempfile.NamedTemporaryFile(delete=False, suffix=".raw", dir=temp_dir).name

    try:
        # Extract raw PCM data
        command = [
            "ffmpeg",
            "-y",
            "-i",
            audio_file,
            "-f",
            "s16le",  # 16-bit signed little-endian PCM
            "-ac",
            "1",  # Mono
            "-ar",
            "44100",  # 44.1kHz
            raw_file,
        ]

        returncode, stdout, stderr = run_cancellable_process(command, check_cancellation)

        if returncode != 0:
            raise Exception(f"Failed to extract PCM data: {stderr}")

        # Read raw PCM data
        import struct

        with open(raw_file, "rb") as f:
            raw_data = f.read()

        # Unpack 16-bit signed integers
        num_samples = len(raw_data) // 2
        samples = struct.unpack(f"{num_samples}h", raw_data)

        # Normalize to -1.0 to 1.0
        samples = [s / 32768.0 for s in samples]

        # Calculate samples per bin
        samples_per_bin = max(1, num_samples // bins)

        # Generate min/max for each bin
        waveform_data = []
        for i in range(bins):
            if check_cancellation and check_cancellation():
                raise Exception("Operation cancelled")

            start_idx = i * samples_per_bin
            end_idx = min(start_idx + samples_per_bin, num_samples)

            if start_idx >= num_samples:
                waveform_data.append({"min": 0.0, "max": 0.0})
                continue

            bin_samples = samples[start_idx:end_idx]

            if bin_samples:
                min_val = min(bin_samples)
                max_val = max(bin_samples)
            else:
                min_val = 0.0
                max_val = 0.0

            waveform_data.append({"min": min_val, "max": max_val})

        # Prepare output data
        output_data = {
            "sample_rate": 44100,
            "duration_seconds": num_samples / 44100.0,
            "bins": bins,
            "samples_per_bin": samples_per_bin,
            "data": waveform_data,
        }

        # Determine output file
        if output_file is None:
            base_name = os.path.splitext(audio_file)[0]
            output_file = f"{base_name}_waveform.json"

        # Save JSON
        with open(output_file, "w") as f:
            json.dump(output_data, f, indent=2)

        logger.info(f"Waveform JSON created (ffmpeg): {output_file}")
        return output_file

    finally:
        # Clean up temporary file
        if os.path.exists(raw_file):
            os.remove(raw_file)
