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

        handler = _FileSystemEventHandler(ignore_patterns={".tmp", "~", ".crdownload"}, callback=lambda x: None)

        # Should ignore files matching patterns
        assert handler._should_ignore("/path/file.tmp")
        assert handler._should_ignore("/path/file~")
        assert handler._should_ignore("/path/file.crdownload")

        # Should not ignore normal files
        assert not handler._should_ignore("/path/file.txt")
        assert not handler._should_ignore("/path/file.mp3")

    def test_start_watching_invalid_directory(self):
        """Test that starting with invalid directory fails gracefully"""
        watcher = DirectoryWatcher()

        success = watcher.start_watching("/nonexistent/path")

        assert not success
        assert not watcher.is_watching()

    def test_stop_when_not_watching(self):
        """Test that stopping when not watching is safe"""
        watcher = DirectoryWatcher()

        # Should not raise
        watcher.stop_watching()
        assert not watcher.is_watching()


class TestGapDetectionScheduler:
    """Tests for GapDetectionScheduler reload signals"""

    def test_txt_modification_triggers_reload_and_detection_for_not_processed(self, qtbot):
        """Test that txt file modifications trigger reload + gap detection if NOT_PROCESSED"""
        from model.song import SongStatus
        
        reload_calls = []

        def mock_reload_handler(song_path):
            reload_calls.append(song_path)

        mock_start_detection = Mock()
        
        # Create song with NOT_PROCESSED status
        song = Song(txt_file="/test/song.txt")
        song.status = SongStatus.NOT_PROCESSED
        mock_get_by_txt = Mock(return_value=song)
        mock_get_by_path = Mock(return_value=song)

        scheduler = GapDetectionScheduler(
            debounce_ms=100,
            start_gap_detection=mock_start_detection,
            songs_get_by_txt_file=mock_get_by_txt,
            songs_get_by_path=mock_get_by_path,
        )

        # Connect to reload signal
        scheduler.reload_requested.connect(mock_reload_handler)

        with tempfile.TemporaryDirectory() as tmpdir:
            txt_path = os.path.join(tmpdir, "song.txt")
            Path(txt_path).touch()

            # Simulate txt file modification
            event = WatchEvent(event_type=WatchEventType.MODIFIED, path=txt_path, is_directory=False)
            scheduler.handle_event(event)

            # Should emit reload signal
            assert len(reload_calls) == 1
            assert reload_calls[0] == tmpdir

            # Should schedule gap detection since status is NOT_PROCESSED
            assert len(scheduler._pending) == 1

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
            songs_get_by_path=mock_get_by_path,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            # Test file with non-trigger extension
            log_path = os.path.join(tmpdir, "debug.log")
            Path(log_path).touch()

            event = WatchEvent(event_type=WatchEventType.MODIFIED, path=log_path, is_directory=False)
            scheduler.handle_event(event)

            # Should not schedule detection
            assert len(scheduler._pending) == 0
            assert len(detection_calls) == 0

    def test_txt_modification_skips_detection_for_processed_songs(self, qtbot):
        """Test that txt file modifications skip gap detection if song status is not NOT_PROCESSED"""
        from model.song import SongStatus
        
        reload_calls = []

        def mock_reload_handler(song_path):
            reload_calls.append(song_path)

        mock_start_detection = Mock()
        
        # Create song with MATCH status (already processed)
        song = Song(txt_file="/test/song.txt")
        song.status = SongStatus.MATCH
        song.audio_file = "/test/song.mp3"
        mock_get_by_txt = Mock(return_value=song)
        mock_get_by_path = Mock(return_value=song)

        scheduler = GapDetectionScheduler(
            debounce_ms=50,
            start_gap_detection=mock_start_detection,
            songs_get_by_txt_file=mock_get_by_txt,
            songs_get_by_path=mock_get_by_path,
        )

        # Connect to reload signal
        scheduler.reload_requested.connect(mock_reload_handler)

        with tempfile.TemporaryDirectory() as tmpdir:
            txt_path = os.path.join(tmpdir, "song.txt")
            Path(txt_path).touch()

            # Simulate txt file modification
            event = WatchEvent(event_type=WatchEventType.MODIFIED, path=txt_path, is_directory=False)
            scheduler.handle_event(event)

            # Should emit reload signal
            assert len(reload_calls) == 1
            assert reload_calls[0] == tmpdir

            # Should NOT schedule gap detection since status is MATCH
            assert len(scheduler._pending) == 0            # Should NOT schedule gap detection
            mock_start_detection.assert_not_called()

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
