"""Utility functions for time/position calculations in waveforms and media playback.

Provides reusable functions for converting between:
- Time (milliseconds) <-> Normalized position (0.0-1.0)
- Time (milliseconds) <-> Pixel position on waveform
"""


def time_to_normalized_position(time_ms: float, duration_ms: float) -> float:
    """Convert absolute time to normalized position (0.0-1.0).

    Args:
        time_ms: Absolute time position in milliseconds
        duration_ms: Total duration in milliseconds

    Returns:
        Normalized position between 0.0 and 1.0
        Returns 0.0 if duration is 0 or negative
    """
    if duration_ms <= 0:
        return 0.0
    return time_ms / duration_ms


def normalized_position_to_time(position: float, duration_ms: float) -> float:
    """Convert normalized position (0.0-1.0) to absolute time.

    Args:
        position: Normalized position between 0.0 and 1.0
        duration_ms: Total duration in milliseconds

    Returns:
        Absolute time in milliseconds
    """
    return position * duration_ms


def time_to_pixel(time_ms: float, duration_ms: float, width_pixels: int) -> int:
    """Convert absolute time to pixel position on waveform.

    Args:
        time_ms: Absolute time position in milliseconds
        duration_ms: Total duration in milliseconds
        width_pixels: Width of waveform in pixels

    Returns:
        Pixel position (integer)
        Returns 0 if duration is 0 or negative
    """
    if duration_ms <= 0:
        return 0
    normalized = time_to_normalized_position(time_ms, duration_ms)
    return int(normalized * width_pixels)


def pixel_to_time(pixel_x: int, duration_ms: float, width_pixels: int) -> float:
    """Convert pixel position on waveform to absolute time.

    Args:
        pixel_x: Pixel position on waveform
        duration_ms: Total duration in milliseconds
        width_pixels: Width of waveform in pixels

    Returns:
        Absolute time in milliseconds
        Returns 0.0 if width is 0 or negative
    """
    if width_pixels <= 0:
        return 0.0
    normalized = pixel_x / width_pixels
    return normalized_position_to_time(normalized, duration_ms)
