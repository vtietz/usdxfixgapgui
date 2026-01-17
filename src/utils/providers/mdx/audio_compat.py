"""
Audio format compatibility utilities for torchaudio.

Handles formats not natively supported by torchaudio/soundfile (e.g., M4A/AAC).
"""

import logging
import os
import subprocess
import tempfile
from typing import Optional
from contextlib import contextmanager

import torchaudio

logger = logging.getLogger(__name__)


def _needs_conversion(audio_file: str) -> bool:
    """Check if audio file needs conversion for torchaudio compatibility.

    Formats requiring ffmpeg conversion:
    - .m4a / .aac: AAC audio (not supported by libsndfile)
    - .opus: Opus audio (not supported by libsndfile)
    """
    return audio_file.lower().endswith((".m4a", ".aac", ".opus"))


def _convert_to_wav(audio_file: str, duration_sec: Optional[float] = None) -> str:
    """
    Convert M4A/AAC to temporary WAV file.

    Args:
        audio_file: Path to M4A/AAC file
        duration_sec: Optional duration limit in seconds (for probing)

    Returns:
        Path to temporary WAV file

    Raises:
        RuntimeError: If conversion fails
    """
    fd, temp_wav = tempfile.mkstemp(suffix=".wav", prefix="usdxfixgap_")
    os.close(fd)

    cmd = ["ffmpeg", "-y", "-i", audio_file, "-ar", "44100"]
    if duration_sec is not None:
        cmd.extend(["-t", str(duration_sec)])
    cmd.append(temp_wav)

    logger.debug("Converting %s to WAV...", audio_file)
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        os.remove(temp_wav)
        raise RuntimeError(f"Failed to convert audio to WAV: {result.stderr}")

    return temp_wav


@contextmanager
def load_audio_compat(audio_file: str, frame_offset: int = 0, num_frames: int = -1):
    """
    Load audio with M4A/AAC compatibility.

    Context manager that converts M4A/AAC to WAV if needed, loads with torchaudio,
    and cleans up temporary files automatically.

    Args:
        audio_file: Path to audio file
        frame_offset: Starting frame for partial load
        num_frames: Number of frames to load (-1 for all)

    Yields:
        Tuple of (waveform, sample_rate)

    Example:
        with load_audio_compat(audio_file) as (waveform, sr):
            # Use waveform
            pass
        # Temp file cleaned up automatically
    """
    temp_file = None
    try:
        if _needs_conversion(audio_file):
            temp_file = _convert_to_wav(audio_file)
            audio_to_load = temp_file
        else:
            audio_to_load = audio_file

        waveform, sample_rate = torchaudio.load(audio_to_load, frame_offset=frame_offset, num_frames=num_frames)
        yield waveform, sample_rate

    finally:
        if temp_file and os.path.exists(temp_file):
            os.remove(temp_file)


def get_audio_info_compat(audio_file: str) -> torchaudio.AudioMetaData:
    """
    Get audio info with M4A/AAC compatibility.

    Args:
        audio_file: Path to audio file

    Returns:
        AudioMetaData with sample rate, num_frames, etc.

    Raises:
        RuntimeError: If probing fails
    """
    if _needs_conversion(audio_file):
        # Use ffprobe to get duration directly
        cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration,sample_rate", "-of", "json", audio_file]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(f"Failed to probe audio file: {result.stderr}")

        import json

        data = json.loads(result.stdout)
        duration_sec = float(data["format"]["duration"])

        # Create a minimal AudioMetaData-like object
        # We'll probe a tiny chunk to get sample rate
        temp_file = _convert_to_wav(audio_file, duration_sec=0.1)
        try:
            info = torchaudio.info(temp_file)
            # Replace num_frames with actual duration
            num_frames = int(duration_sec * info.sample_rate)

            # Return modified info
            class AudioInfo:
                def __init__(self, sample_rate: int, num_frames: int, num_channels: int = 2):
                    self.sample_rate = sample_rate
                    self.num_frames = num_frames
                    self.num_channels = num_channels

            return AudioInfo(info.sample_rate, num_frames, info.num_channels)
        finally:
            if os.path.exists(temp_file):
                os.remove(temp_file)
    else:
        return torchaudio.info(audio_file)
