"""Factory for creating GapDetectionResult-like mocks in tests."""

from unittest.mock import Mock
from model.gap_info import GapInfoStatus


def create_gap_detection_result(
    song_file_path: str,
    detected_gap: int = 1000,
    gap_diff: int = 0,
    notes_overlap: int = 0,
    silence_periods: list = None,
    duration_ms: int = 180000,
    status: GapInfoStatus = GapInfoStatus.MATCH,
) -> Mock:
    """
    Create a mock GapDetectionResult object.

    Args:
        song_file_path: Path to the song file
        detected_gap: Detected gap value in milliseconds
        gap_diff: Difference between detected and current gap
        notes_overlap: Notes overlap value in milliseconds
        silence_periods: List of silence period tuples (start, end)
        duration_ms: Total duration in milliseconds
        status: GapInfoStatus enum value

    Returns:
        A Mock object with GapDetectionResult attributes
    """
    if silence_periods is None:
        silence_periods = [(0, 500), (1000, 1500)]

    result = Mock()
    result.song_file_path = song_file_path
    result.detected_gap = detected_gap
    result.gap_diff = gap_diff
    result.notes_overlap = notes_overlap
    result.silence_periods = silence_periods
    result.duration_ms = duration_ms
    result.status = status

    return result


def create_match_result(song_file_path: str, detected_gap: int = 1000) -> Mock:
    """
    Create a GapDetectionResult mock for a MATCH scenario.

    Args:
        song_file_path: Path to the song file
        detected_gap: Detected gap value (default: 1000ms)

    Returns:
        A Mock with MATCH status and zero gap_diff
    """
    return create_gap_detection_result(
        song_file_path=song_file_path, detected_gap=detected_gap, gap_diff=0, status=GapInfoStatus.MATCH
    )


def create_mismatch_result(song_file_path: str, detected_gap: int = 1200, gap_diff: int = 200) -> Mock:
    """
    Create a GapDetectionResult mock for a MISMATCH scenario.

    Args:
        song_file_path: Path to the song file
        detected_gap: Detected gap value
        gap_diff: Difference from current gap

    Returns:
        A Mock with MISMATCH status
    """
    return create_gap_detection_result(
        song_file_path=song_file_path, detected_gap=detected_gap, gap_diff=gap_diff, status=GapInfoStatus.MISMATCH
    )
