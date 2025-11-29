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
from services.gap_detection_scheduler import GapDetectionScheduler, _PendingDetection
from model.songs import normalize_path
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

            # Wait for debounced reload signal
            qtbot.wait(150)  # Wait longer than debounce_ms=100

            # Should emit reload signal
            assert len(reload_calls) == 1
            from model.songs import normalize_path
            assert reload_calls[0] == normalize_path(tmpdir)

            # Should schedule gap detection since status is NOT_PROCESSED
            assert len(scheduler._pending) == 1

    def test_skips_txt_modified_for_recently_created_but_not_audio(self, qtbot):
        """Test that MODIFIED events skip .txt but NOT audio for recently created songs"""
        from services.cache_update_scheduler import CacheUpdateScheduler
        from model.song import SongStatus

        mock_start_detection = Mock()
        mock_worker_queue = Mock()

        # Create cache scheduler
        cache_scheduler = CacheUpdateScheduler(
            worker_queue_add_task=mock_worker_queue,
            songs_get_by_txt_file=Mock(return_value=None),
            debounce_ms=100,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            txt_path = os.path.join(tmpdir, "song.txt")
            audio_path = os.path.join(tmpdir, "song.mp3")
            Path(txt_path).touch()
            Path(audio_path).touch()

            # Mark txt as recently created (use normalized key)
            from datetime import datetime
            from model.songs import normalize_path
            cache_scheduler._recently_created[normalize_path(txt_path)] = datetime.now()

            # Create song with NOT_PROCESSED status
            song = Song(txt_file=txt_path)
            song.status = SongStatus.NOT_PROCESSED
            song.audio_file = audio_path

            mock_get_by_txt = Mock(return_value=song)
            mock_get_by_path = Mock(return_value=song)

            scheduler = GapDetectionScheduler(
                debounce_ms=100,
                start_gap_detection=mock_start_detection,
                songs_get_by_txt_file=mock_get_by_txt,
                songs_get_by_path=mock_get_by_path,
                cache_scheduler=cache_scheduler,
            )

            # Simulate MODIFIED on .txt (should be skipped)
            txt_event = WatchEvent(event_type=WatchEventType.MODIFIED, path=txt_path, is_directory=False)
            scheduler.handle_event(txt_event)
            assert len(scheduler._pending) == 0, "txt MODIFIED should be skipped"

            # Simulate MODIFIED on audio (should NOT be skipped)
            audio_event = WatchEvent(event_type=WatchEventType.MODIFIED, path=audio_path, is_directory=False)
            scheduler.handle_event(audio_event)
            assert len(scheduler._pending) == 1, "audio MODIFIED should trigger detection"

    def test_directory_scan_funnels_through_debounced_scheduler(self, qtbot):
        """Test that directory scan uses debounced scheduler instead of direct enqueue"""
        from services.cache_update_scheduler import CacheUpdateScheduler

        enqueue_calls = []

        def mock_enqueue(worker):
            enqueue_calls.append(worker)

        mock_get_by_txt = Mock(return_value=None)

        scheduler = CacheUpdateScheduler(
            worker_queue_add_task=mock_enqueue,
            songs_get_by_txt_file=mock_get_by_txt,
            debounce_ms=100,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            txt_path = os.path.join(tmpdir, "song.txt")
            Path(txt_path).touch()

            # Scan directory (should schedule via debounced path)
            scheduler._scan_directory_for_songs(tmpdir)

            # Should NOT enqueue immediately (debounced)
            assert len(enqueue_calls) == 0

            # Should have pending creation
            assert len(scheduler._pending_creations) == 1

    def test_duplicate_enqueue_suppression(self, qtbot):
        """Test that duplicate enqueues are suppressed by creation guard"""
        from services.cache_update_scheduler import CacheUpdateScheduler

        enqueue_calls = []

        def mock_enqueue(worker):
            enqueue_calls.append(worker)

        mock_get_by_txt = Mock(return_value=None)

        scheduler = CacheUpdateScheduler(
            worker_queue_add_task=mock_enqueue,
            songs_get_by_txt_file=mock_get_by_txt,
            debounce_ms=50,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            txt_path = os.path.join(tmpdir, "song.txt")
            Path(txt_path).write_text("#ARTIST:Test\n#TITLE:Song\n")

            # Schedule creation check twice rapidly (simulates dir + file CREATED)
            scheduler._schedule_creation_check(txt_path)
            scheduler._schedule_creation_check(txt_path)

            # Only one pending creation should exist (coalesced)
            assert len(scheduler._pending_creations) == 1

            # Wait for debounce + stability check (need two cycles)
            qtbot.wait(200)

            # Only one enqueue should have occurred
            assert len(enqueue_calls) == 1
            # Check using normalized key
            from model.songs import normalize_path
            assert normalize_path(txt_path) in scheduler._creation_enqueued

            # Clear guard
            scheduler.clear_creation_guard(txt_path)
            assert txt_path not in scheduler._creation_enqueued

            # Can schedule again after clearing
            scheduler._schedule_creation_check(txt_path)
            qtbot.wait(200)
            assert len(enqueue_calls) == 2

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

    def test_txt_modification_triggers_detection_for_processed_songs(self, qtbot):
        """Processed songs should reset to NOT_PROCESSED when content actually changes."""
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

            # Wait for debounced reload signal
            qtbot.wait(100)  # Wait longer than debounce_ms=50

            # Should emit reload signal
            assert len(reload_calls) == 1
            from model.songs import normalize_path
            assert reload_calls[0] == normalize_path(tmpdir)

            # Should schedule gap detection now that content change is detected
            assert len(scheduler._pending) == 1
            mock_start_detection.assert_not_called()

    def test_scheduler_runs_for_solved_songs(self, qtbot):
        """Scheduler should re-run detection even when current status is SOLVED."""
        from datetime import datetime
        from PySide6.QtCore import QTimer
        from model.song import SongStatus
        from model.gap_info import GapInfo, GapInfoStatus

        detection_calls = []

        def mock_start_detection(song):
            detection_calls.append(song)

        with tempfile.TemporaryDirectory() as tmpdir:
            txt_path = os.path.join(tmpdir, "song.txt")
            audio_path = os.path.join(tmpdir, "song.mp3")
            Path(txt_path).write_text("#TITLE:Test\n")
            Path(audio_path).write_text("fake audio")

            song = Song(txt_file=txt_path)
            song.audio_file = audio_path
            gap_info = GapInfo(file_path=os.path.join(tmpdir, "usdxfixgap.info"), txt_basename="song.txt")
            gap_info.status = GapInfoStatus.SOLVED
            song.gap_info = gap_info
            song.status = SongStatus.SOLVED

            scheduler = GapDetectionScheduler(
                debounce_ms=50,
                start_gap_detection=mock_start_detection,
                songs_get_by_txt_file=lambda _: song,
                songs_get_by_path=lambda _: song,
            )

            pending_timer = QTimer()
            pending_detection = _PendingDetection(
                song_path=normalize_path(song.path),
                txt_file=txt_path,
                last_event_time=datetime.now(),
                timer=pending_timer,
                original_path=song.path,
            )
            normalized_path = normalize_path(song.path)
            scheduler._pending[normalized_path] = pending_detection

            scheduler._execute_detection(normalized_path)

            assert len(detection_calls) == 1
            assert detection_calls[0] is song

    def test_immediate_start_cancels_pending_detection(self, qtbot):
        """Immediate detection start should clear pending timers and avoid duplicates."""
        from datetime import datetime
        from PySide6.QtCore import QTimer

        detection_calls = []

        def mock_start_detection(song):
            detection_calls.append(song)

        with tempfile.TemporaryDirectory() as tmpdir:
            txt_path = os.path.join(tmpdir, "song.txt")
            audio_path = os.path.join(tmpdir, "song.mp3")
            Path(txt_path).write_text("#TITLE:Test\n")
            Path(audio_path).write_text("fake audio")

            song = Song(txt_file=txt_path)
            song.audio_file = audio_path

            scheduler = GapDetectionScheduler(
                debounce_ms=50,
                start_gap_detection=mock_start_detection,
                songs_get_by_txt_file=lambda _: song,
                songs_get_by_path=lambda _: song,
            )

            pending_timer = QTimer()
            pending_detection = _PendingDetection(
                song_path=normalize_path(song.path),
                txt_file=txt_path,
                last_event_time=datetime.now(),
                timer=pending_timer,
                original_path=song.path,
            )
            normalized_path = normalize_path(song.path)
            scheduler._pending[normalized_path] = pending_detection

            started = scheduler.start_detection_immediately(song)

            assert started
            assert len(detection_calls) == 1
            assert normalized_path not in scheduler._pending
            assert normalized_path in scheduler._in_flight

            # Simulate completion to release in-flight lock
            scheduler.mark_detection_complete(song)
            assert normalized_path not in scheduler._in_flight

    def test_reschedules_when_song_missing_during_detection(self, qtbot):
        """Gap detection should retry when the song is not yet back in the collection."""
        from model.song import SongStatus

        start_calls = []

        def mock_start_detection(song):
            start_calls.append(song)

        with tempfile.TemporaryDirectory() as tmpdir:
            txt_path = os.path.join(tmpdir, "song.txt")
            audio_path = os.path.join(tmpdir, "song.mp3")
            Path(txt_path).touch()
            Path(audio_path).touch()

            song = Song(txt_file=txt_path)
            song.audio_file = audio_path
            song.status = SongStatus.NOT_PROCESSED
            song.artist = "Wise Guys"
            song.title = "Nur für dich"

            lookup_calls = {"count": 0}

            def mock_get_by_txt_file(path):
                lookup_calls["count"] += 1
                if lookup_calls["count"] < 3:
                    return None
                return song

            scheduler = GapDetectionScheduler(
                debounce_ms=50,
                start_gap_detection=mock_start_detection,
                songs_get_by_txt_file=mock_get_by_txt_file,
                songs_get_by_path=lambda _: None,
            )

            event = WatchEvent(event_type=WatchEventType.MODIFIED, path=txt_path, is_directory=False)
            scheduler.handle_event(event)

            qtbot.waitUntil(lambda: len(start_calls) == 1, timeout=1000)

            assert start_calls[0] is song
            assert lookup_calls["count"] >= 3


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
