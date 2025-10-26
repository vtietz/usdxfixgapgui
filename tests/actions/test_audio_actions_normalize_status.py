"""Tests for AudioActions normalization status restoration behavior.

Covers the fix for stuck PROCESSING status after normalization completes.
Status restoration is now handled by BaseActions._on_song_worker_finished()
which calls _restore_status_from_gap_info().
"""

from unittest.mock import Mock, patch

from actions.audio_actions import AudioActions
from model.gap_info import GapInfoStatus
from model.song import SongStatus


class TestNormalizeStatusRestoration:
    """Test suite for status restoration after normalization.

    Note: Status restoration is now implemented in BaseActions, but we test
    it through the normalization workflow as that's where the issue was found.
    """

    def test_normalize_restores_match_status_on_finish(self, app_data, song_factory, tmp_path):
        """Test: Status transitions NOT_PROCESSED → PROCESSING → MATCH after normalization"""
        # Setup: Song with MATCH status from prior detection
        audio_file = tmp_path / "test.mp3"
        audio_file.write_text("audio data")

        song = song_factory(
            title="Match Song",
            gap=1000,
            audio_file=str(audio_file),
            with_notes=True
        )

        # Set gap_info with MATCH status (as if detection already ran)
        song.gap_info.detected_gap = 1000
        song.gap_info.diff = 0
        song.gap_info.status = GapInfoStatus.MATCH

        # Verify initial status is MATCH (via owner hook)
        assert song.status == SongStatus.MATCH, "Precondition: Song should start with MATCH status"

        # Mock worker and signals
        with patch('actions.audio_actions.NormalizeAudioWorker') as mock_worker_class, \
             patch('actions.audio_actions.SongActions') as mock_song_actions_class:

            mock_worker = Mock()
            mock_worker.signals = Mock()
            mock_worker.signals.started = Mock()
            mock_worker.signals.finished = Mock()
            mock_worker.signals.error = Mock()
            mock_worker_class.return_value = mock_worker

            mock_song_actions = Mock()
            mock_song_actions_class.return_value = mock_song_actions

            # Create AudioActions
            audio_actions = AudioActions(app_data)

            # Action: Normalize song
            audio_actions._normalize_song(song, start_now=True)

            # Simulate started signal → status should become PROCESSING
            started_callback = mock_worker.signals.started.connect.call_args_list[0][0][0]
            started_callback()
            assert song.status == SongStatus.PROCESSING, "Status should be PROCESSING after started"

            # Simulate finished signal → status should restore to MATCH
            finished_callbacks = [
                call[0][0] for call in mock_worker.signals.finished.connect.call_args_list
            ]
            for callback in finished_callbacks:
                callback()

            # Assert: Status restored to MATCH (from gap_info)
            assert song.status == SongStatus.MATCH, "Status should restore to MATCH after finished"

            # Assert: songs.updated.emit was called (UI refresh)
            assert app_data.songs.updated.emit.called, "UI should be notified of status change"

    def test_normalize_restores_mismatch_status_on_finish(self, app_data, song_factory, tmp_path):
        """Test: MISMATCH status is restored after normalization"""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_text("audio")

        song = song_factory(title="Mismatch Song", audio_file=str(audio_file))
        song.gap_info.detected_gap = 1200
        song.gap_info.diff = 200
        song.gap_info.status = GapInfoStatus.MISMATCH

        assert song.status == SongStatus.MISMATCH, "Precondition: MISMATCH status"

        with patch('actions.audio_actions.NormalizeAudioWorker') as mock_worker_class, \
             patch('actions.audio_actions.SongActions'):

            mock_worker = Mock()
            mock_worker.signals = Mock()
            mock_worker.signals.started = Mock()
            mock_worker.signals.finished = Mock()
            mock_worker.signals.error = Mock()
            mock_worker_class.return_value = mock_worker

            audio_actions = AudioActions(app_data)
            audio_actions._normalize_song(song, start_now=True)

            # Simulate started → PROCESSING
            started_callback = mock_worker.signals.started.connect.call_args_list[0][0][0]
            started_callback()
            assert song.status == SongStatus.PROCESSING

            # Simulate finished → should restore MISMATCH
            finished_callbacks = [
                call[0][0] for call in mock_worker.signals.finished.connect.call_args_list
            ]
            for callback in finished_callbacks:
                callback()

            assert song.status == SongStatus.MISMATCH, "Status should restore to MISMATCH"

    def test_normalize_does_not_override_error_status(self, app_data, song_factory, tmp_path):
        """Test: ERROR status is NOT overridden by status restoration"""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_text("audio")

        song = song_factory(title="Error Song", audio_file=str(audio_file))
        song.gap_info.status = GapInfoStatus.MATCH

        with patch('actions.audio_actions.NormalizeAudioWorker') as mock_worker_class, \
             patch('actions.audio_actions.SongActions'):

            mock_worker = Mock()
            mock_worker.signals = Mock()
            mock_worker.signals.started = Mock()
            mock_worker.signals.finished = Mock()
            mock_worker.signals.error = Mock()
            mock_worker_class.return_value = mock_worker

            audio_actions = AudioActions(app_data)
            audio_actions._normalize_song(song, start_now=True)

            # Simulate started
            started_callback = mock_worker.signals.started.connect.call_args_list[0][0][0]
            started_callback()

            # Simulate error → set ERROR status
            error_callback = mock_worker.signals.error.connect.call_args_list[0][0][0]
            error_callback(Exception("Normalization failed"))
            assert song.status == SongStatus.ERROR

            # Simulate finished → ERROR should NOT be overridden
            finished_callbacks = [
                call[0][0] for call in mock_worker.signals.finished.connect.call_args_list
            ]
            for callback in finished_callbacks:
                callback()

            # Assert: Status remains ERROR
            assert song.status == SongStatus.ERROR, "ERROR status should not be overridden"

    def test_normalize_fallback_to_not_processed_when_no_gap_info(self, app_data, song_factory, tmp_path):
        """Test: Status falls back to NOT_PROCESSED when no gap_info exists"""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_text("audio")

        song = song_factory(title="No GapInfo", audio_file=str(audio_file))
        song.gap_info = None  # Explicitly remove gap_info
        song.status = SongStatus.NOT_PROCESSED

        with patch('actions.audio_actions.NormalizeAudioWorker') as mock_worker_class, \
             patch('actions.audio_actions.SongActions'):

            mock_worker = Mock()
            mock_worker.signals = Mock()
            mock_worker.signals.started = Mock()
            mock_worker.signals.finished = Mock()
            mock_worker.signals.error = Mock()
            mock_worker_class.return_value = mock_worker

            audio_actions = AudioActions(app_data)
            audio_actions._normalize_song(song, start_now=True)

            # Simulate started → PROCESSING
            started_callback = mock_worker.signals.started.connect.call_args_list[0][0][0]
            started_callback()
            assert song.status == SongStatus.PROCESSING

            # Simulate finished → should fallback to NOT_PROCESSED
            finished_callbacks = [
                call[0][0] for call in mock_worker.signals.finished.connect.call_args_list
            ]
            for callback in finished_callbacks:
                callback()

            assert song.status == SongStatus.NOT_PROCESSED, "Status should fallback to NOT_PROCESSED"

    def test_normalize_schedules_deferred_reload(self, app_data, song_factory, tmp_path):
        """Test: Deferred reload is scheduled after normalization (cache persistence)"""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_text("audio")

        song = song_factory(title="Reload Test", audio_file=str(audio_file))
        song.gap_info.status = GapInfoStatus.MATCH

        with patch('actions.audio_actions.NormalizeAudioWorker') as mock_worker_class, \
             patch('actions.audio_actions.SongActions') as mock_song_actions_class, \
             patch('PySide6.QtCore.QTimer.singleShot') as mock_timer:

            mock_worker = Mock()
            mock_worker.signals = Mock()
            mock_worker.signals.started = Mock()
            mock_worker.signals.finished = Mock()
            mock_worker.signals.error = Mock()
            mock_worker_class.return_value = mock_worker

            mock_song_actions = Mock()
            mock_song_actions_class.return_value = mock_song_actions

            audio_actions = AudioActions(app_data)
            audio_actions._normalize_song(song, start_now=True)

            # Simulate finished
            finished_callbacks = [
                call[0][0] for call in mock_worker.signals.finished.connect.call_args_list
            ]
            for callback in finished_callbacks:
                callback()

            # Assert: Deferred reload was scheduled (QTimer.singleShot called)
            # The reload is in the _reload_if_success handler
            assert mock_timer.call_count >= 1, "Deferred reload should be scheduled"

            # Trigger the deferred reload callback
            reload_callback = mock_timer.call_args_list[-1][0][1]  # Get the callback from singleShot
            reload_callback()

            # Assert: reload_song was called
            mock_song_actions.reload_song.assert_called_once_with(specific_song=song)

    def test_normalize_does_not_reload_on_error_status(self, app_data, song_factory, tmp_path):
        """Test: Deferred reload is skipped when status is ERROR"""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_text("audio")

        song = song_factory(title="Error No Reload", audio_file=str(audio_file))

        with patch('actions.audio_actions.NormalizeAudioWorker') as mock_worker_class, \
             patch('actions.audio_actions.SongActions') as mock_song_actions_class, \
             patch('PySide6.QtCore.QTimer.singleShot') as mock_timer:

            mock_worker = Mock()
            mock_worker.signals = Mock()
            mock_worker.signals.started = Mock()
            mock_worker.signals.finished = Mock()
            mock_worker.signals.error = Mock()
            mock_worker_class.return_value = mock_worker

            mock_song_actions = Mock()
            mock_song_actions_class.return_value = mock_song_actions

            audio_actions = AudioActions(app_data)
            audio_actions._normalize_song(song, start_now=True)

            # Simulate error
            error_callback = mock_worker.signals.error.connect.call_args_list[0][0][0]
            error_callback(Exception("Fail"))
            song.status = SongStatus.ERROR

            # Simulate finished
            finished_callbacks = [
                call[0][0] for call in mock_worker.signals.finished.connect.call_args_list
            ]
            for callback in finished_callbacks:
                callback()

            # Trigger deferred callback if scheduled
            if mock_timer.called:
                reload_callback = mock_timer.call_args_list[-1][0][1]
                reload_callback()

            # Assert: reload_song was NOT called (guard prevented it)
            mock_song_actions.reload_song.assert_not_called()

    def test_normalize_multi_selection_restores_status_per_song(self, app_data, song_factory, tmp_path):
        """Test: Multi-selection normalization restores status independently per song"""
        audio1 = tmp_path / "song1.mp3"
        audio2 = tmp_path / "song2.mp3"
        audio1.write_text("audio1")
        audio2.write_text("audio2")

        song1 = song_factory(title="Song 1", audio_file=str(audio1))
        song1.gap_info.status = GapInfoStatus.MATCH

        song2 = song_factory(title="Song 2", audio_file=str(audio2))
        song2.gap_info.status = GapInfoStatus.MISMATCH

        assert song1.status == SongStatus.MATCH
        assert song2.status == SongStatus.MISMATCH

        with patch('actions.audio_actions.NormalizeAudioWorker') as mock_worker_class, \
             patch('actions.audio_actions.SongActions'):

            # Track workers created per song
            workers = {}

            def create_worker(song):
                worker = Mock()
                worker.signals = Mock()
                worker.signals.started = Mock()
                worker.signals.finished = Mock()
                worker.signals.error = Mock()
                workers[song.title] = worker
                return worker

            mock_worker_class.side_effect = create_worker

            audio_actions = AudioActions(app_data)

            # Normalize both songs
            audio_actions._normalize_song(song1, start_now=True)
            audio_actions._normalize_song(song2, start_now=True)

            # Simulate workers finishing independently
            for song, worker in [(song1, workers["Song 1"]), (song2, workers["Song 2"])]:
                # Started
                started_callback = worker.signals.started.connect.call_args_list[0][0][0]
                started_callback()
                assert song.status == SongStatus.PROCESSING

                # Finished
                finished_callbacks = [
                    call[0][0] for call in worker.signals.finished.connect.call_args_list
                ]
                for callback in finished_callbacks:
                    callback()

            # Assert: Each song restored its own status
            assert song1.status == SongStatus.MATCH, "Song 1 should restore to MATCH"
            assert song2.status == SongStatus.MISMATCH, "Song 2 should restore to MISMATCH"

    def test_normalize_restoration_updated_status(self, app_data, song_factory, tmp_path):
        """Test: UPDATED status is restored after normalization"""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_text("audio")

        song = song_factory(title="Updated Song", audio_file=str(audio_file))
        song.gap_info.detected_gap = 1200
        song.gap_info.updated_gap = 1150
        song.gap_info.status = GapInfoStatus.UPDATED

        assert song.status == SongStatus.UPDATED

        with patch('actions.audio_actions.NormalizeAudioWorker') as mock_worker_class, \
             patch('actions.audio_actions.SongActions'):

            mock_worker = Mock()
            mock_worker.signals = Mock()
            mock_worker.signals.started = Mock()
            mock_worker.signals.finished = Mock()
            mock_worker.signals.error = Mock()
            mock_worker_class.return_value = mock_worker

            audio_actions = AudioActions(app_data)
            audio_actions._normalize_song(song, start_now=True)

            # Simulate started
            started_callback = mock_worker.signals.started.connect.call_args_list[0][0][0]
            started_callback()
            assert song.status == SongStatus.PROCESSING

            # Simulate finished
            finished_callbacks = [
                call[0][0] for call in mock_worker.signals.finished.connect.call_args_list
            ]
            for callback in finished_callbacks:
                callback()

            assert song.status == SongStatus.UPDATED, "Status should restore to UPDATED"

    def test_normalize_restoration_solved_status(self, app_data, song_factory, tmp_path):
        """Test: SOLVED status is restored after normalization"""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_text("audio")

        song = song_factory(title="Solved Song", audio_file=str(audio_file))
        song.gap_info.status = GapInfoStatus.SOLVED

        assert song.status == SongStatus.SOLVED

        with patch('actions.audio_actions.NormalizeAudioWorker') as mock_worker_class, \
             patch('actions.audio_actions.SongActions'):

            mock_worker = Mock()
            mock_worker.signals = Mock()
            mock_worker.signals.started = Mock()
            mock_worker.signals.finished = Mock()
            mock_worker.signals.error = Mock()
            mock_worker_class.return_value = mock_worker

            audio_actions = AudioActions(app_data)
            audio_actions._normalize_song(song, start_now=True)

            # Simulate started
            started_callback = mock_worker.signals.started.connect.call_args_list[0][0][0]
            started_callback()
            assert song.status == SongStatus.PROCESSING

            # Simulate finished
            finished_callbacks = [
                call[0][0] for call in mock_worker.signals.finished.connect.call_args_list
            ]
            for callback in finished_callbacks:
                callback()

            assert song.status == SongStatus.SOLVED, "Status should restore to SOLVED"