"""Unit tests for GapActions.get_notes_overlap orchestration."""

from unittest.mock import AsyncMock, patch

from actions.gap_actions import GapActions


class TestGetNotesOverlap:
    """Unit tests for notes overlap computation orchestration"""

    def test_sets_overlap_and_persists(self, app_data, song_factory, fake_run_async):
        """Test: Computes overlap, updates gap_info, and persists"""
        # Setup: Create song with notes and gap_info
        song = song_factory(title="Test Song", with_notes=True)

        # Silence periods and detection time (mock data)
        silence_periods = [(0, 500), (1000, 1500)]
        detection_time = 180000  # 3 minutes in ms

        # Mock the utils.usdx.get_notes_overlap function to return a specific value
        with patch('actions.gap_actions.usdx.get_notes_overlap', return_value=123) as mock_overlap, \
             patch('actions.gap_actions.run_async') as mock_run_async, \
             patch('actions.gap_actions.GapInfoService.save', new_callable=AsyncMock) as mock_service_save:

            # Use centralized async executor fixture
            mock_run_async.side_effect = fake_run_async

            # Create GapActions instance
            gap_actions = GapActions(app_data)

            # Action: Call get_notes_overlap
            gap_actions.get_notes_overlap(song, silence_periods, detection_time)

            # Assert: notes_overlap was set on gap_info
            assert song.gap_info.notes_overlap == 123

            # Assert: utils.usdx.get_notes_overlap was called with correct args
            mock_overlap.assert_called_once_with(song.notes, silence_periods, detection_time)

            # Assert: GapInfoService.save was scheduled via run_async
            mock_run_async.assert_called_once()
            # The first arg to run_async should be the result of GapInfoService.save(...)
            mock_service_save.assert_called_once_with(song.gap_info)

            # Assert: songs.updated.emit was called with the song
            app_data.songs.updated.emit.assert_called_once_with(song)

    def test_uses_first_selected_song_when_none_provided(self, app_data, song_factory, fake_run_async):
        """Test: Falls back to first_selected_song when song arg is None"""
        # Setup: Create selected song
        selected_song = song_factory(title="Selected", with_notes=True)
        app_data.first_selected_song = selected_song

        silence_periods = [(0, 500)]
        detection_time = 120000

        with patch('actions.gap_actions.usdx.get_notes_overlap', return_value=456) as mock_overlap, \
             patch('actions.gap_actions.run_async') as mock_run_async, \
             patch('actions.gap_actions.GapInfoService.save', new_callable=AsyncMock) as mock_save:

            # Use centralized async executor fixture
            mock_run_async.side_effect = fake_run_async

            gap_actions = GapActions(app_data)

            # Action: Call with song=None
            gap_actions.get_notes_overlap(None, silence_periods, detection_time)

            # Assert: Used first_selected_song
            assert selected_song.gap_info.notes_overlap == 456
            mock_overlap.assert_called_once_with(selected_song.notes, silence_periods, detection_time)

    def test_early_return_when_no_song(self, app_data):
        """Test: Returns early when no song is available"""
        # Setup: No selected song
        app_data.first_selected_song = None

        with patch('actions.gap_actions.usdx.get_notes_overlap') as mock_overlap, \
             patch('actions.gap_actions.run_async') as mock_run_async:

            gap_actions = GapActions(app_data)

            # Action: Call with no song
            gap_actions.get_notes_overlap(None, [], 0)

            # Assert: No processing occurred
            mock_overlap.assert_not_called()
            mock_run_async.assert_not_called()
            app_data.songs.updated.emit.assert_not_called()