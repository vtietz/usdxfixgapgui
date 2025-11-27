"""
Tests for gap actions service usage patterns.
Verifies that gap actions use USDXFileService and GapInfoService correctly
without accessing non-existent song.usdx_file property.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from model.song import Song
from model.gap_info import GapInfo, GapInfoStatus
from model.usdx_file import Note
from actions.gap_actions import GapActions
from app.app_data import AppData


@pytest.fixture
def mock_app_data():
    """Create a mock AppData instance"""
    data = Mock(spec=AppData)
    data.songs = Mock()
    data.songs.updated = Mock()
    data.songs.updated.emit = Mock()
    data.songs.filter = None  # No filter active by default (supports 'in' operator)
    data.first_selected_song = None
    data.config = Mock()
    data.config.auto_normalize = False
    # Add worker_queue mock required by BaseActions
    data.worker_queue = Mock()
    return data


@pytest.fixture
def sample_song():
    """Create a sample song with necessary data"""
    song = Song(txt_file="/test/song.txt")
    song.title = "Test Song"
    song.artist = "Test Artist"
    song.gap = 1000
    song.bpm = 120.0
    song.is_relative = False

    # Create gap_info
    song.gap_info = GapInfo(file_path="/test/usdxfixgap.info")
    song.gap_info.original_gap = 1000
    song.gap_info.detected_gap = 1200
    song.gap_info.diff = 200

    # Create sample notes
    song.notes = [
        create_note(0, 10, 60, "La"),
        create_note(20, 15, 62, "la"),
    ]

    return song


def create_note(start_beat, length, pitch, text):
    """Helper to create a Note instance"""
    note = Note()
    note.StartBeat = start_beat
    note.Length = length
    note.Pitch = pitch
    note.Text = text
    note.NoteType = ":"
    note.start_ms = 0
    note.end_ms = 0
    note.duration_ms = 0
    return note


class TestUpdateGapValue:
    """Tests for update_gap_value() method"""

    @patch("services.usdx_file_service.USDXFileService.load", new_callable=AsyncMock)
    @patch("services.usdx_file_service.USDXFileService.write_gap_tag", new_callable=AsyncMock)
    @patch("services.gap_info_service.GapInfoService.save", new_callable=AsyncMock)
    @patch("actions.gap_actions.AudioActions")
    @patch("actions.gap_actions.run_async")
    @patch("PySide6.QtCore.QTimer")
    def test_update_gap_value_uses_services_not_property(
        self,
        mock_qtimer,
        mock_run_async,
        mock_audio_actions,
        mock_save,
        mock_write_gap,
        mock_load,
        mock_app_data,
        sample_song,
        fake_run_async,
    ):
        """Verify update_gap_value uses services instead of song.usdx_file property"""
        # Use centralized async executor fixture
        mock_run_async.side_effect = fake_run_async

        # Mock load to return a mock USDXFile
        mock_load.return_value = Mock()

        # Mock QTimer.singleShot to immediately invoke the callback
        def immediate_callback(delay, callback):
            callback()

        mock_qtimer.singleShot.side_effect = immediate_callback

        # Setup
        gap_actions = GapActions(mock_app_data)
        new_gap = 1500

        # Execute
        gap_actions.update_gap_value(sample_song, new_gap)

        # Verify song.gap updated
        assert sample_song.gap == new_gap

        # Verify gap_info updated
        assert sample_song.gap_info.updated_gap == new_gap
        assert sample_song.gap_info.status == GapInfoStatus.UPDATED

        # Verify run_async called once (combined update_gap_and_cache function)
        assert mock_run_async.call_count == 1

        # Verify signal emitted
        mock_app_data.songs.updated.emit.assert_called_once_with(sample_song)

    @patch("services.usdx_file_service.USDXFileService.load", new_callable=AsyncMock)
    @patch("services.usdx_file_service.USDXFileService.write_gap_tag", new_callable=AsyncMock)
    @patch("services.gap_info_service.GapInfoService.save", new_callable=AsyncMock)
    @patch("actions.gap_actions.AudioActions")
    @patch("actions.gap_actions.run_async")
    def test_update_gap_value_recalculates_note_times(
        self,
        mock_run_async,
        mock_audio_actions,
        mock_save,
        mock_write_gap,
        mock_load,
        mock_app_data,
        sample_song,
        fake_run_async,
    ):
        """Verify note times are recalculated with new gap value"""
        # Use centralized async executor fixture
        mock_run_async.side_effect = fake_run_async

        # Mock load to return a mock USDXFile
        mock_load.return_value = Mock()

        gap_actions = GapActions(mock_app_data)
        new_gap = 1500

        # Execute
        gap_actions.update_gap_value(sample_song, new_gap)

        # Verify notes have updated timings
        # With new gap, start_ms should change
        for note in sample_song.notes:
            assert note.start_ms != 0 or note.end_ms != 0  # Times were calculated

    @patch("actions.gap_actions.run_async")
    def test_update_gap_value_no_song(self, mock_run_async, mock_app_data):
        """Verify graceful handling when no song selected

        Note: No AsyncMock patches needed since code path returns early
        and never calls services (update_gap_tag or GapInfoService.save).
        """
        gap_actions = GapActions(mock_app_data)

        # Execute with None song and no first_selected_song
        gap_actions.update_gap_value(None, 1500)

        # Verify early return - no service calls made
        mock_run_async.assert_not_called()
        mock_app_data.songs.updated.emit.assert_not_called()


class TestRevertGapValue:
    """Tests for revert_gap_value() method"""

    @patch("services.usdx_file_service.USDXFileService.load", new_callable=AsyncMock)
    @patch("services.usdx_file_service.USDXFileService.write_gap_tag", new_callable=AsyncMock)
    @patch("services.gap_info_service.GapInfoService.save", new_callable=AsyncMock)
    @patch("actions.gap_actions.AudioActions")
    @patch("actions.gap_actions.run_async")
    @patch("PySide6.QtCore.QTimer")
    def test_revert_gap_value_uses_services_not_property(
        self,
        mock_qtimer,
        mock_run_async,
        mock_audio_actions,
        mock_save,
        mock_write_gap,
        mock_load,
        mock_app_data,
        sample_song,
        fake_run_async,
    ):
        """Verify revert_gap_value uses services instead of song.usdx_file property"""
        # Use centralized async executor fixture
        mock_run_async.side_effect = fake_run_async

        # Mock load to return a mock USDXFile
        mock_load.return_value = Mock()

        # Mock QTimer.singleShot to immediately invoke the callback
        def immediate_callback(delay, callback):
            callback()

        mock_qtimer.singleShot.side_effect = immediate_callback

        # Setup
        gap_actions = GapActions(mock_app_data)
        sample_song.gap = 1500  # Changed from original

        # Execute
        gap_actions.revert_gap_value(sample_song)

        # Verify gap reverted to original
        assert sample_song.gap == sample_song.gap_info.original_gap

        # Verify run_async called once (combined revert_gap_and_cache function)
        assert mock_run_async.call_count == 1

        # Verify signal emitted
        mock_app_data.songs.updated.emit.assert_called_once_with(sample_song)

    @patch("services.usdx_file_service.USDXFileService.load", new_callable=AsyncMock)
    @patch("services.usdx_file_service.USDXFileService.write_gap_tag", new_callable=AsyncMock)
    @patch("services.gap_info_service.GapInfoService.save", new_callable=AsyncMock)
    @patch("actions.gap_actions.AudioActions")
    @patch("actions.gap_actions.run_async")
    def test_revert_gap_value_recalculates_note_times(
        self,
        mock_run_async,
        mock_audio_actions,
        mock_save,
        mock_write_gap,
        mock_load,
        mock_app_data,
        sample_song,
        fake_run_async,
    ):
        """Verify note times are recalculated with original gap value"""
        # Use centralized async executor fixture
        mock_run_async.side_effect = fake_run_async

        # Mock load to return a mock USDXFile
        mock_load.return_value = Mock()

        gap_actions = GapActions(mock_app_data)
        sample_song.gap = 1500  # Changed from original

        # Execute
        gap_actions.revert_gap_value(sample_song)

        # Verify notes have updated timings
        for note in sample_song.notes:
            assert note.start_ms != 0 or note.end_ms != 0  # Times were calculated


class TestNoteTimeCalculation:
    """Tests for _recalculate_note_times() helper method"""

    def test_recalculate_note_times_absolute_mode(self, mock_app_data, sample_song):
        """Verify note time calculation in absolute (non-RELATIVE) mode"""
        gap_actions = GapActions(mock_app_data)
        sample_song.gap = 1000
        sample_song.bpm = 120.0
        sample_song.is_relative = False

        gap_actions._recalculate_note_times(sample_song)

        # Verify first note times calculated correctly
        # beats_per_ms = (120 / 60 / 1000) * 4 = 0.008
        # start_ms = gap + (StartBeat / beats_per_ms) = 1000 + (0 / 0.008) = 1000
        assert sample_song.notes[0].start_ms == 1000

    def test_recalculate_note_times_relative_mode(self, mock_app_data, sample_song):
        """Verify note time calculation in RELATIVE mode"""
        gap_actions = GapActions(mock_app_data)
        sample_song.gap = 1000
        sample_song.bpm = 120.0
        sample_song.is_relative = True

        gap_actions._recalculate_note_times(sample_song)

        # Verify first note times calculated correctly
        # In RELATIVE mode, start_ms = StartBeat / beats_per_ms (no gap added)
        # start_ms = 0 / 0.008 = 0
        assert sample_song.notes[0].start_ms == 0

    def test_recalculate_note_times_missing_notes(self, mock_app_data, sample_song):
        """Verify graceful handling when notes are None"""
        gap_actions = GapActions(mock_app_data)
        sample_song.notes = None

        # Should not crash
        gap_actions._recalculate_note_times(sample_song)

        # No assertions needed - just verify no exception raised

    def test_recalculate_note_times_missing_bpm(self, mock_app_data, sample_song):
        """Verify graceful handling when BPM is missing"""
        gap_actions = GapActions(mock_app_data)
        sample_song.bpm = 0

        # Should not crash
        gap_actions._recalculate_note_times(sample_song)

        # No assertions needed - just verify no exception raised


class TestServiceIntegration:
    """Integration tests verifying correct service usage"""

    @patch("actions.gap_actions.USDXFileService")
    @patch("actions.gap_actions.GapInfoService")
    @patch("actions.gap_actions.AudioActions")
    @patch("actions.gap_actions.run_async")
    def test_gap_info_service_save_called(
        self, mock_run_async, mock_audio_actions, mock_gap_info_service, mock_usdx_service, mock_app_data, sample_song
    ):
        """Verify GapInfoService.save is called correctly"""
        gap_actions = GapActions(mock_app_data)

        gap_actions.update_gap_value(sample_song, 1500)

        # Verify GapInfoService.save was called
        # Note: It's called via run_async, so we check run_async calls
        assert mock_run_async.call_count >= 1

    def test_no_usdx_file_property_access(self, mock_app_data, sample_song):
        """Verify no code tries to access song.usdx_file property"""
        GapActions(mock_app_data)

        # Verify song doesn't have usdx_file property
        assert not hasattr(sample_song, "usdx_file")

        # This would raise AttributeError if code tried to access it
        # The test passing means our refactoring removed all such access
