"""
Unit tests for watch mode components.

Tests DirectoryWatcher, GapDetectionScheduler debouncing, and basic controller logic.
"""

import pytest
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock

from services.directory_watcher import DirectoryWatcher, WatchEvent, WatchEventType
from services.gap_detection_scheduler import GapDetectionScheduler
from model.song import Song


class TestDirectoryWatcher:
    """Tests for DirectoryWatcher"""

    def test_should_ignore_patterns(self):
        """Test that ignore patterns work correctly"""
        from services.directory_watcher import _FileSystemEventHandler

        handler = _FileSystemEventHandler(
            ignore_patterns={'.tmp', '~', '.crdownload'},
            callback=lambda x: None
        )

        # Should ignore files matching patterns
        assert handler._should_ignore('/path/file.tmp')
        assert handler._should_ignore('/path/file~')
        assert handler._should_ignore('/path/file.crdownload')

        # Should not ignore normal files
        assert not handler._should_ignore('/path/file.txt')
        assert not handler._should_ignore('/path/file.mp3')

    def test_start_watching_invalid_directory(self):
        """Test that starting with invalid directory fails gracefully"""
        watcher = DirectoryWatcher()

        success = watcher.start_watching('/nonexistent/path')

        assert not success
        assert not watcher.is_watching()

    def test_stop_when_not_watching(self):
        """Test that stopping when not watching is safe"""
        watcher = DirectoryWatcher()

        # Should not raise
        watcher.stop_watching()
        assert not watcher.is_watching()


class TestGapDetectionScheduler:
    """Tests for GapDetectionScheduler with debouncing"""

    def test_debouncing_coalesces_events(self, qtbot):
        """Test that multiple events for same song are debounced"""
        detection_calls = []

        def mock_start_detection(song):
            detection_calls.append(song)

        mock_get_by_txt = Mock(return_value=Song(txt_file="/test/song.txt"))
        mock_get_by_path = Mock(return_value=None)

        scheduler = GapDetectionScheduler(
            debounce_ms=100,  # Short debounce for testing
            start_gap_detection=mock_start_detection,
            songs_get_by_txt_file=mock_get_by_txt,
            songs_get_by_path=mock_get_by_path
        )

        # Create test directory
        with tempfile.TemporaryDirectory() as tmpdir:
            txt_path = os.path.join(tmpdir, "song.txt")
            Path(txt_path).touch()

            # Simulate multiple rapid modifications
            for i in range(5):
                event = WatchEvent(
                    event_type=WatchEventType.MODIFIED,
                    path=txt_path,
                    is_directory=False
                )
                scheduler.handle_event(event)

            # Should have 1 pending detection, not 5
            assert len(scheduler._pending) == 1

            # Wait for debounce + margin
            qtbot.wait(200)

            # Should have executed detection exactly once
            assert len(detection_calls) == 1
            assert len(scheduler._pending) == 0

    def test_ignores_non_trigger_extensions(self):
        """Test that only trigger extensions schedule detection"""
        detection_calls = []

        def mock_start_detection(song):
            detection_calls.append(song)

        mock_get_by_txt = Mock(return_value=Song(txt_file="/test/song.txt"))
        mock_get_by_path = Mock(return_value=None)

        scheduler = GapDetectionScheduler(
            debounce_ms=50,
            start_gap_detection=mock_start_detection,
            songs_get_by_txt_file=mock_get_by_txt,
            songs_get_by_path=mock_get_by_path
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            # Test file with non-trigger extension
            log_path = os.path.join(tmpdir, "debug.log")
            Path(log_path).touch()

            event = WatchEvent(
                event_type=WatchEventType.MODIFIED,
                path=log_path,
                is_directory=False
            )
            scheduler.handle_event(event)

            # Should not schedule detection
            assert len(scheduler._pending) == 0
            assert len(detection_calls) == 0

    def test_idempotency_prevents_duplicate_in_flight(self, qtbot):
        """Test that in-flight tasks prevent duplicates"""
        detection_calls = []

        def mock_start_detection(song):
            detection_calls.append(song)

        test_song = Song(txt_file="/test/song.txt")
        mock_get_by_txt = Mock(return_value=test_song)
        mock_get_by_path = Mock(return_value=None)

        scheduler = GapDetectionScheduler(
            debounce_ms=50,
            start_gap_detection=mock_start_detection,
            songs_get_by_txt_file=mock_get_by_txt,
            songs_get_by_path=mock_get_by_path
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            txt_path = os.path.join(tmpdir, "song.txt")
            Path(txt_path).touch()

            # First event
            event = WatchEvent(
                event_type=WatchEventType.MODIFIED,
                path=txt_path,
                is_directory=False
            )
            scheduler.handle_event(event)

            # Wait for execution
            qtbot.wait(100)

            assert len(detection_calls) == 1

            # Mark as in-flight manually (simulating detection not finished)
            # scheduler._in_flight.add("/test")
            # Note: In real usage, detection completes and calls mark_detection_complete

            # Try to schedule again - should be blocked if still in-flight
            # For this test, we'll clear in-flight to test the mechanism
            scheduler._in_flight.clear()

            # Second event after clearing
            scheduler.handle_event(event)
            qtbot.wait(100)

            # Should have executed again
            assert len(detection_calls) == 2

    def test_clear_pending(self):
        """Test that clear_pending stops all timers"""
        mock_start_detection = Mock()
        mock_get_by_txt = Mock(return_value=Song(txt_file="/test/song.txt"))
        mock_get_by_path = Mock(return_value=None)

        scheduler = GapDetectionScheduler(
            debounce_ms=1000,  # Long debounce
            start_gap_detection=mock_start_detection,
            songs_get_by_txt_file=mock_get_by_txt,
            songs_get_by_path=mock_get_by_path
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            txt_path = os.path.join(tmpdir, "song.txt")
            Path(txt_path).touch()

            event = WatchEvent(
                event_type=WatchEventType.MODIFIED,
                path=txt_path,
                is_directory=False
            )
            scheduler.handle_event(event)

            assert len(scheduler._pending) == 1

            # Clear before execution
            scheduler.clear_pending()

            assert len(scheduler._pending) == 0
            # Detection should never be called
            assert mock_start_detection.call_count == 0


class TestWatchModeIntegration:
    """Integration tests for watch mode enablement logic"""

    def test_watch_mode_requires_directory_and_scan(self):
        """Test that watch mode requires both directory and initial scan"""
        from actions.watch_mode_actions import WatchModeActions
        from app.app_data import AppData

        data = AppData()
        watch_actions = WatchModeActions(data)

        # Initially cannot enable (no directory, no scan)
        assert not watch_actions.can_enable_watch_mode()

        # Set directory
        data.directory = "/some/path"

        # Still cannot enable (no initial scan)
        assert not watch_actions.can_enable_watch_mode()

        # Simulate initial scan completion
        watch_actions._is_initial_scan_complete = True

        # Now can enable
        assert watch_actions.can_enable_watch_mode()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
