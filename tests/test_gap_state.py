"""
Tests for GapState service.
"""

import pytest
from src.services.gap_state import GapState, SeverityBand


def test_gap_state_initialization():
    """Test GapState initialization with default values."""
    state = GapState(current_gap_ms=1000, detected_gap_ms=950)

    assert state.current_gap_ms == 1000
    assert state.detected_gap_ms == 950
    assert state.saved_gap_ms == 1000
    assert state.is_dirty is False
    assert state.diff_ms == 50  # current - detected


def test_gap_state_no_detected_gap():
    """Test GapState when no detected gap is available."""
    state = GapState(current_gap_ms=1000)

    assert state.current_gap_ms == 1000
    assert state.detected_gap_ms is None
    assert state.has_detected_gap is False
    assert state.diff_ms is None


def test_set_current_gap_ms_marks_dirty():
    """Test that changing current gap marks state as dirty."""
    state = GapState(current_gap_ms=1000)

    assert state.is_dirty is False

    state.set_current_gap_ms(1100)

    assert state.current_gap_ms == 1100
    assert state.is_dirty is True
    assert state.can_revert is True


def test_set_current_gap_ms_same_value():
    """Test that setting same value doesn't mark dirty."""
    state = GapState(current_gap_ms=1000)

    state.set_current_gap_ms(1000)

    assert state.is_dirty is False


def test_mark_clean():
    """Test mark_clean updates saved value and clears dirty flag."""
    state = GapState(current_gap_ms=1000)
    state.set_current_gap_ms(1100)

    assert state.is_dirty is True

    state.mark_clean()

    assert state.saved_gap_ms == 1100
    assert state.is_dirty is False
    assert state.can_revert is False


def test_revert():
    """Test revert restores saved gap and clears dirty flag."""
    state = GapState(current_gap_ms=1000)
    state.set_current_gap_ms(1100)

    assert state.current_gap_ms == 1100
    assert state.is_dirty is True

    state.revert()

    assert state.current_gap_ms == 1000
    assert state.is_dirty is False


def test_revert_when_not_dirty():
    """Test revert does nothing when state is clean."""
    state = GapState(current_gap_ms=1000)

    state.revert()

    assert state.current_gap_ms == 1000
    assert state.is_dirty is False


def test_apply_detected():
    """Test apply_detected sets current to detected value."""
    state = GapState(current_gap_ms=1000, detected_gap_ms=950)

    state.apply_detected()

    assert state.current_gap_ms == 950
    assert state.is_dirty is True  # Different from saved (1000)
    assert state.diff_ms == 0  # Now equal


def test_apply_detected_when_no_detection():
    """Test apply_detected does nothing when no detected gap."""
    state = GapState(current_gap_ms=1000)

    state.apply_detected()

    assert state.current_gap_ms == 1000
    assert state.is_dirty is False


def test_severity_band_good():
    """Test severity band for small differences (0-50ms)."""
    state = GapState(current_gap_ms=1025, detected_gap_ms=1000)

    assert state.diff_ms == 25
    assert state.severity_band() == SeverityBand.GOOD


def test_severity_band_warning():
    """Test severity band for medium differences (50-200ms)."""
    state = GapState(current_gap_ms=1100, detected_gap_ms=1000)

    assert state.diff_ms == 100
    assert state.severity_band() == SeverityBand.WARNING


def test_severity_band_error():
    """Test severity band for large differences (200+ms)."""
    state = GapState(current_gap_ms=1300, detected_gap_ms=1000)

    assert state.diff_ms == 300
    assert state.severity_band() == SeverityBand.ERROR


def test_severity_band_negative_diff():
    """Test severity band works with negative differences."""
    state = GapState(current_gap_ms=900, detected_gap_ms=1000)

    assert state.diff_ms == -100
    assert state.severity_band() == SeverityBand.WARNING  # abs(100)


def test_severity_band_no_detection():
    """Test severity band returns None when no detected gap."""
    state = GapState(current_gap_ms=1000)

    assert state.severity_band() is None


def test_format_diff_positive():
    """Test format_diff with positive difference."""
    state = GapState(current_gap_ms=1050, detected_gap_ms=1000)

    assert state.format_diff() == "+50ms"


def test_format_diff_negative():
    """Test format_diff with negative difference."""
    state = GapState(current_gap_ms=950, detected_gap_ms=1000)

    assert state.format_diff() == "-50ms"


def test_format_diff_zero():
    """Test format_diff with zero difference."""
    state = GapState(current_gap_ms=1000, detected_gap_ms=1000)

    assert state.format_diff() == "+0ms"


def test_format_diff_no_detection():
    """Test format_diff when no detected gap."""
    state = GapState(current_gap_ms=1000)

    assert state.format_diff() == "No detection"


def test_from_song_factory():
    """Test from_song factory method."""
    state = GapState.from_song(current_gap=1000, detected_gap=950)

    assert state.current_gap_ms == 1000
    assert state.detected_gap_ms == 950
    assert state.saved_gap_ms == 1000
    assert state.is_dirty is False


def test_from_song_no_detection():
    """Test from_song factory without detected gap."""
    state = GapState.from_song(current_gap=1000)

    assert state.current_gap_ms == 1000
    assert state.detected_gap_ms is None
    assert state.has_detected_gap is False


def test_on_change_callback():
    """Test on_change callback is triggered."""
    state = GapState(current_gap_ms=1000)
    callback_count = [0]

    def callback():
        callback_count[0] += 1

    state.subscribe_on_change(callback)

    state.set_current_gap_ms(1100)
    assert callback_count[0] == 1

    state.set_detected_gap_ms(1050)
    assert callback_count[0] == 2

    state.mark_clean()
    assert callback_count[0] == 3


def test_on_change_callback_same_value():
    """Test callback not triggered when value unchanged."""
    state = GapState(current_gap_ms=1000)
    callback_count = [0]

    def callback():
        callback_count[0] += 1

    state.subscribe_on_change(callback)

    state.set_current_gap_ms(1000)
    assert callback_count[0] == 0  # No change, no callback


def test_unsubscribe_callback():
    """Test unsubscribe removes callback."""
    state = GapState(current_gap_ms=1000)
    callback_count = [0]

    def callback():
        callback_count[0] += 1

    state.subscribe_on_change(callback)
    state.set_current_gap_ms(1100)
    assert callback_count[0] == 1

    state.unsubscribe_on_change(callback)
    state.set_current_gap_ms(1200)
    assert callback_count[0] == 1  # No additional callback


def test_multiple_callbacks():
    """Test multiple callbacks can be registered."""
    state = GapState(current_gap_ms=1000)
    counts = {"a": 0, "b": 0}

    def callback_a():
        counts["a"] += 1

    def callback_b():
        counts["b"] += 1

    state.subscribe_on_change(callback_a)
    state.subscribe_on_change(callback_b)

    state.set_current_gap_ms(1100)

    assert counts["a"] == 1
    assert counts["b"] == 1


def test_callback_error_doesnt_crash():
    """Test that callback errors don't crash the state."""
    state = GapState(current_gap_ms=1000)
    callback_count = [0]

    def bad_callback():
        raise ValueError("Test error")

    def good_callback():
        callback_count[0] += 1

    state.subscribe_on_change(bad_callback)
    state.subscribe_on_change(good_callback)

    # Should not raise
    state.set_current_gap_ms(1100)

    # Good callback should still be called
    assert callback_count[0] == 1