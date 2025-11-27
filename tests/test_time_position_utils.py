"""Tests for time/position conversion utilities."""

import pytest
from utils.time_position import (
    time_to_normalized_position,
    normalized_position_to_time,
    time_to_pixel,
    pixel_to_time,
)


class TestTimeToNormalizedPosition:
    """Test time_to_normalized_position function."""

    def test_converts_time_to_normalized_position(self):
        """Test basic time to normalized position conversion."""
        # 1 second out of 10 seconds = 0.1
        assert time_to_normalized_position(1000, 10000) == pytest.approx(0.1)

        # Halfway through = 0.5
        assert time_to_normalized_position(5000, 10000) == pytest.approx(0.5)

        # End = 1.0
        assert time_to_normalized_position(10000, 10000) == pytest.approx(1.0)

        # Start = 0.0
        assert time_to_normalized_position(0, 10000) == pytest.approx(0.0)

    def test_handles_zero_duration(self):
        """Test zero duration returns 0.0."""
        assert time_to_normalized_position(1000, 0) == 0.0

    def test_handles_negative_duration(self):
        """Test negative duration returns 0.0."""
        assert time_to_normalized_position(1000, -5000) == 0.0


class TestNormalizedPositionToTime:
    """Test normalized_position_to_time function."""

    def test_converts_normalized_position_to_time(self, fake_run_async):
        """Test basic normalized position to time conversion."""
        from unittest.mock import patch

        with patch("actions.gap_actions.run_async") as mock_run_async:
            mock_run_async.side_effect = fake_run_async

            # 0.1 of 10 seconds = 1 second
            assert normalized_position_to_time(0.1, 10000) == pytest.approx(1000)

            # Halfway = 5 seconds
            assert normalized_position_to_time(0.5, 10000) == pytest.approx(5000)

            # End = 10 seconds
            assert normalized_position_to_time(1.0, 10000) == pytest.approx(10000)

            # Start = 0 seconds
            assert normalized_position_to_time(0.0, 10000) == pytest.approx(0)


class TestTimeToPixel:
    """Test time_to_pixel function."""

    def test_converts_time_to_pixel_position(self):
        """Test basic time to pixel conversion."""
        # 1 second out of 10 seconds on 800px width = 80px
        assert time_to_pixel(1000, 10000, 800) == 80

        # Halfway = 400px
        assert time_to_pixel(5000, 10000, 800) == 400

        # End = 800px
        assert time_to_pixel(10000, 10000, 800) == 800

        # Start = 0px
        assert time_to_pixel(0, 10000, 800) == 0

    def test_handles_vocals_mode_shorter_duration(self):
        """Test gap marker positioning in vocals mode (shorter duration)."""
        # Audio mode: gap at 1000ms, audio duration 241s (241000ms), width 800px
        # Position: 1000/241000 * 800 = 3.32px (WRONG - old behavior)

        # Vocals mode: gap at 1000ms, vocals duration 45s (45000ms), width 800px
        # Position: 1000/45000 * 800 = 17.78px (CORRECT - new behavior)
        assert time_to_pixel(1000, 45000, 800) == 17

        # Compare: both modes should show gap at same absolute time
        audio_pos = time_to_pixel(1000, 241000, 800)
        vocals_pos = time_to_pixel(1000, 45000, 800)

        # Vocals position should be further right (shorter duration = more relative position)
        assert vocals_pos > audio_pos

    def test_handles_zero_duration(self):
        """Test zero duration returns 0."""
        assert time_to_pixel(1000, 0, 800) == 0

    def test_handles_negative_duration(self):
        """Test negative duration returns 0."""
        assert time_to_pixel(1000, -5000, 800) == 0


class TestPixelToTime:
    """Test pixel_to_time function."""

    def test_converts_pixel_to_time_position(self):
        """Test basic pixel to time conversion."""
        # 80px out of 800px on 10s duration = 1 second
        assert pixel_to_time(80, 10000, 800) == pytest.approx(1000)

        # Halfway = 5 seconds
        assert pixel_to_time(400, 10000, 800) == pytest.approx(5000)

        # End = 10 seconds
        assert pixel_to_time(800, 10000, 800) == pytest.approx(10000)

        # Start = 0 seconds
        assert pixel_to_time(0, 10000, 800) == pytest.approx(0)

    def test_handles_zero_width(self):
        """Test zero width returns 0.0."""
        assert pixel_to_time(100, 10000, 0) == 0.0

    def test_handles_negative_width(self):
        """Test negative width returns 0.0."""
        assert pixel_to_time(100, 10000, -800) == 0.0


class TestRoundTripConversions:
    """Test that conversions are reversible."""

    def test_time_to_pixel_to_time_roundtrip(self):
        """Test time -> pixel -> time conversion."""
        original_time = 5000  # 5 seconds
        duration = 10000  # 10 seconds
        width = 800  # pixels

        pixel = time_to_pixel(original_time, duration, width)
        recovered_time = pixel_to_time(pixel, duration, width)

        # Should be very close (within 1ms due to integer pixel rounding)
        assert recovered_time == pytest.approx(original_time, abs=1)

    def test_normalized_position_roundtrip(self):
        """Test time -> normalized -> time conversion."""
        original_time = 5000  # 5 seconds
        duration = 10000  # 10 seconds

        normalized = time_to_normalized_position(original_time, duration)
        recovered_time = normalized_position_to_time(normalized, duration)

        assert recovered_time == pytest.approx(original_time)
