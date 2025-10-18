"""Gap detection pipeline module.

Provides refactored, modular gap detection implementation
with clear separation of concerns and testable components.
"""

from .pipeline import (
    GapDetectionContext,
    validate_inputs,
    calculate_detection_time,
    normalize_context,
    detect_gap_from_silence,
    should_retry_detection,
    perform_refactored,
)

__all__ = [
    'GapDetectionContext',
    'validate_inputs',
    'calculate_detection_time',
    'normalize_context',
    'detect_gap_from_silence',
    'should_retry_detection',
    'perform_refactored',
]
