"""Test watch mode gap_info file change detection and song reload"""

import tempfile
import os
from pathlib import Path
from unittest.mock import Mock
from services.gap_detection_scheduler import GapDetectionScheduler
from services.directory_watcher import WatchEvent, WatchEventType
from model.song import Song


class TestGapInfoFileChanges:
    """Tests for usdxfixgap.info file change detection"""

    def test_gap_info_modified_triggers_reload(self, qtbot):
        """Test that modifying usdxfixgap.info triggers reload signal"""
        reload_calls = []

        def mock_reload_handler(song_path):
            reload_calls.append(song_path)

        mock_start_detection = Mock()
        mock_get_by_txt = Mock(return_value=None)
        mock_get_by_path = Mock(return_value=None)

        scheduler = GapDetectionScheduler(
            debounce_ms=50,
            start_gap_detection=mock_start_detection,
            songs_get_by_txt_file=mock_get_by_txt,
            songs_get_by_path=mock_get_by_path,
        )

        # Connect to reload signal
        scheduler.reload_requested.connect(mock_reload_handler)

        with tempfile.TemporaryDirectory() as tmpdir:
            gap_info_path = os.path.join(tmpdir, "usdxfixgap.info")
            Path(gap_info_path).write_text('{"test": "data"}')

            # Simulate usdxfixgap.info modification
            event = WatchEvent(
                event_type=WatchEventType.MODIFIED,
                path=gap_info_path,
                is_directory=False
            )
            scheduler.handle_event(event)

            # Should have emitted reload signal
            assert len(reload_calls) == 1
            assert reload_calls[0] == tmpdir

            # Should NOT have scheduled gap detection
            assert len(scheduler._pending) == 0
            mock_start_detection.assert_not_called()

    def test_gap_info_deleted_triggers_reload(self, qtbot):
        """Test that deleting usdxfixgap.info triggers reload signal"""
        reload_calls = []

        def mock_reload_handler(song_path):
            reload_calls.append(song_path)

        mock_start_detection = Mock()
        mock_get_by_txt = Mock(return_value=None)
        mock_get_by_path = Mock(return_value=None)

        scheduler = GapDetectionScheduler(
            debounce_ms=50,
            start_gap_detection=mock_start_detection,
            songs_get_by_txt_file=mock_get_by_txt,
            songs_get_by_path=mock_get_by_path,
        )

        # Connect to reload signal
        scheduler.reload_requested.connect(mock_reload_handler)

        with tempfile.TemporaryDirectory() as tmpdir:
            gap_info_path = os.path.join(tmpdir, "usdxfixgap.info")

            # Simulate usdxfixgap.info deletion
            event = WatchEvent(
                event_type=WatchEventType.DELETED,
                path=gap_info_path,
                is_directory=False
            )
            scheduler.handle_event(event)

            # Should have emitted reload signal
            assert len(reload_calls) == 1
            assert reload_calls[0] == tmpdir

            # Should NOT have scheduled gap detection
            assert len(scheduler._pending) == 0
            mock_start_detection.assert_not_called()

    def test_txt_file_modified_triggers_reload(self, qtbot):
        """Test that .txt file changes trigger reload (not gap detection)"""
        reload_calls = []

        def mock_reload_handler(song_path):
            reload_calls.append(song_path)

        with tempfile.TemporaryDirectory() as tmpdir:
            txt_path = os.path.join(tmpdir, "song.txt")
            Path(txt_path).touch()

            mock_get_by_txt = Mock(return_value=None)
            mock_get_by_path = Mock(return_value=None)
            mock_start_detection = Mock()

            scheduler = GapDetectionScheduler(
                debounce_ms=50,
                start_gap_detection=mock_start_detection,
                songs_get_by_txt_file=mock_get_by_txt,
                songs_get_by_path=mock_get_by_path,
            )

            # Connect to reload signal
            scheduler.reload_requested.connect(mock_reload_handler)

            # Create song with NOT_PROCESSED status
            from model.song import SongStatus
            song = Song(txt_file=txt_path)
            song.status = SongStatus.NOT_PROCESSED
            mock_get_by_txt.return_value = song
            mock_get_by_path.return_value = song

            # Simulate .txt file modification
            event = WatchEvent(
                event_type=WatchEventType.MODIFIED,
                path=txt_path,
                is_directory=False
            )
            scheduler.handle_event(event)

            # Should emit reload signal
            assert len(reload_calls) == 1
            assert reload_calls[0] == tmpdir

            # Should schedule gap detection since status is NOT_PROCESSED
            assert len(scheduler._pending) == 1

    def test_multiple_gap_info_changes_all_trigger_reload(self, qtbot):
        """Test that multiple usdxfixgap.info changes all trigger reload"""
        reload_calls = []

        def mock_reload_handler(song_path):
            reload_calls.append(song_path)

        mock_start_detection = Mock()
        mock_get_by_txt = Mock(return_value=None)
        mock_get_by_path = Mock(return_value=None)

        scheduler = GapDetectionScheduler(
            debounce_ms=50,
            start_gap_detection=mock_start_detection,
            songs_get_by_txt_file=mock_get_by_txt,
            songs_get_by_path=mock_get_by_path,
        )

        # Connect to reload signal
        scheduler.reload_requested.connect(mock_reload_handler)

        with tempfile.TemporaryDirectory() as tmpdir:
            gap_info_path = os.path.join(tmpdir, "usdxfixgap.info")

            # Multiple modifications
            for i in range(3):
                event = WatchEvent(
                    event_type=WatchEventType.MODIFIED,
                    path=gap_info_path,
                    is_directory=False
                )
                scheduler.handle_event(event)

            # Should have emitted reload signal for each change
            assert len(reload_calls) == 3
            assert all(path == tmpdir for path in reload_calls)
