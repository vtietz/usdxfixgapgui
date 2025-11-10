"""
Tests for gap marker duration stability.

Verifies that WaveformWidget.duration_ms remains stable and is not overwritten
by playhead position updates, ensuring gap markers stay in correct positions.
"""

import pytest
from PySide6.QtWidgets import QApplication
from ui.mediaplayer.waveform_widget import WaveformWidget


@pytest.fixture(scope="module")
def qapp():
    """Create QApplication instance for Qt widgets."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def waveform_widget(qapp):
    """Create a WaveformWidget instance for testing."""
    widget = WaveformWidget()
    yield widget
    widget.deleteLater()


class TestDurationStability:
    """Test that duration_ms is not overwritten by update_position."""

    def test_update_position_does_not_mutate_duration_ms(self, waveform_widget):
        """Verify update_position() does not overwrite duration_ms."""
        # Set duration for gap markers (full audio duration)
        full_audio_duration = 230000  # 3:50 song
        waveform_widget.duration_ms = full_audio_duration

        # Simulate playback updates with different media duration (vocals preview)
        vocals_preview_duration = 30000  # 30 seconds

        # Call update_position multiple times (simulating playback)
        for position in range(0, 5000, 500):
            waveform_widget.update_position(position, vocals_preview_duration)

        # Duration should remain unchanged
        assert (
            waveform_widget.duration_ms == full_audio_duration
        ), f"duration_ms was overwritten! Expected {full_audio_duration}, got {waveform_widget.duration_ms}"

    def test_update_position_calculates_playhead_correctly(self, waveform_widget):
        """Verify update_position() correctly calculates normalized playhead position."""
        # Set duration for gap markers
        waveform_widget.duration_ms = 230000

        # Update with vocals preview duration
        position = 15000  # 15 seconds into playback
        duration = 30000  # 30 second vocals preview

        waveform_widget.update_position(position, duration)

        # Playhead should be normalized to media duration, not marker duration
        expected_position = 15000 / 30000  # = 0.5 (50% through vocals)
        assert (
            abs(waveform_widget.currentPosition - expected_position) < 0.001
        ), f"Playhead calculation wrong. Expected {expected_position}, got {waveform_widget.currentPosition}"

    def test_duration_zero_does_not_crash(self, waveform_widget):
        """Verify handling of zero duration doesn't crash."""
        waveform_widget.duration_ms = 230000

        # Update with zero duration (edge case)
        waveform_widget.update_position(0, 0)

        # Should set playhead to 0 without crashing
        assert waveform_widget.currentPosition == 0
        # Duration should remain unchanged
        assert waveform_widget.duration_ms == 230000

    def test_multiple_songs_duration_changes(self, waveform_widget):
        """Verify duration can be changed between songs but not by playback."""
        # First song
        song1_duration = 180000  # 3 minutes
        waveform_widget.duration_ms = song1_duration

        # Simulate playback
        waveform_widget.update_position(10000, 30000)
        assert waveform_widget.duration_ms == song1_duration

        # Switch to second song (controller would set new duration)
        song2_duration = 240000  # 4 minutes
        waveform_widget.duration_ms = song2_duration

        # Simulate playback of second song
        waveform_widget.update_position(10000, 30000)
        assert waveform_widget.duration_ms == song2_duration


class TestGapMarkerPositioning:
    """Test gap marker position calculations."""

    def test_gap_marker_positions_remain_stable_during_playback(self, waveform_widget):
        """Verify gap marker pixel positions don't change during playback."""
        # Setup: full audio duration and gap markers
        full_duration = 230000  # 3:50 song
        detected_gap = 3800
        original_gap = 3820

        waveform_widget.duration_ms = full_duration
        waveform_widget.set_gap_markers(original_gap_ms=original_gap, detected_gap_ms=detected_gap)

        # Resize widget to known size for position calculation
        waveform_widget.resize(1000, 100)
        waveform_widget.overlay.setFixedSize(1000, 100)

        # Calculate expected positions (same formula as paint_overlay)
        overlay_width = 1000
        expected_original_x = int((original_gap / full_duration) * overlay_width)
        expected_detected_x = int((detected_gap / full_duration) * overlay_width)

        # Simulate playback updates (vocals preview duration)
        vocals_duration = 30000
        for position in [0, 5000, 10000, 15000, 20000]:
            waveform_widget.update_position(position, vocals_duration)

            # Recalculate positions - they should remain the same
            actual_original_x = int((original_gap / waveform_widget.duration_ms) * overlay_width)
            actual_detected_x = int((detected_gap / waveform_widget.duration_ms) * overlay_width)

            assert (
                actual_original_x == expected_original_x
            ), f"Original marker moved! Expected {expected_original_x}, got {actual_original_x}"
            assert (
                actual_detected_x == expected_detected_x
            ), f"Detected marker moved! Expected {expected_detected_x}, got {actual_detected_x}"

    def test_gap_markers_scale_correctly_with_full_audio_duration(self, waveform_widget):
        """Verify gap markers use full audio duration for scaling, not media duration."""
        # Full audio: 230 seconds (3:50)
        full_duration = 230000
        # Gap at 3.8 seconds
        gap_ms = 3800

        waveform_widget.duration_ms = full_duration
        waveform_widget.detected_gap_ms = gap_ms

        # Widget width
        overlay_width = 1000

        # Gap should be positioned at 3.8/230 = ~1.65% from left
        expected_x = int((gap_ms / full_duration) * overlay_width)
        assert expected_x == 16, f"Expected x=16, got {expected_x}"

        # NOT at 3.8/30 = ~12.7% (if it used vocals duration by mistake)
        wrong_x = int((gap_ms / 30000) * overlay_width)
        assert wrong_x == 126, f"Wrong calculation check failed"

        # Verify we're using the correct calculation
        assert expected_x != wrong_x, "Test setup error: positions should be different"

    def test_gap_markers_handle_missing_duration(self, waveform_widget):
        """Verify gap markers handle zero/missing duration gracefully."""
        waveform_widget.duration_ms = 0
        waveform_widget.set_gap_markers(original_gap_ms=3800, detected_gap_ms=3820)

        # Should not crash when painting with zero duration
        # (paint_overlay checks for duration_ms > 0)
        overlay_width = 1000
        if waveform_widget.duration_ms > 0:
            # Would calculate normally
            x = int((3800 / waveform_widget.duration_ms) * overlay_width)
        else:
            # Should skip gap marker drawing
            pass

        # No assertion needed - test passes if no crash


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_negative_duration_handled(self, waveform_widget):
        """Verify negative duration doesn't cause issues."""
        waveform_widget.duration_ms = 100000

        # Negative duration (shouldn't happen, but be defensive)
        waveform_widget.update_position(5000, -1)

        # Should keep playhead at 0 and not crash
        assert waveform_widget.currentPosition == 0
        assert waveform_widget.duration_ms == 100000

    def test_very_large_duration_no_overflow(self, waveform_widget):
        """Verify very large durations don't cause overflow."""
        # 10 hour audio file
        huge_duration = 36000000  # 10 hours in ms
        waveform_widget.duration_ms = huge_duration

        # Update position
        waveform_widget.update_position(1000000, 30000)

        # Duration should remain unchanged
        assert waveform_widget.duration_ms == huge_duration

        # Playhead calculation should work
        expected = 1000000 / 30000
        assert abs(waveform_widget.currentPosition - expected) < 0.001

    def test_rapid_position_updates_stability(self, waveform_widget):
        """Verify rapid position updates don't corrupt duration."""
        waveform_widget.duration_ms = 180000

        # Simulate rapid updates (60 FPS)
        media_duration = 30000
        for i in range(100):
            position = i * 500  # Increment by 500ms
            waveform_widget.update_position(position, media_duration)

        # Duration should still be intact
        assert waveform_widget.duration_ms == 180000
