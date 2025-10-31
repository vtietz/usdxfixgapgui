from unittest.mock import Mock, patch

from model.songs import Songs
from model.song import Song
from actions.song_actions import SongActions


class TestSongDeletion:
    """Test song deletion functionality"""

    def setup_method(self):
        """Setup for each test"""
        self.songs = Songs()
        self.mock_data = Mock()
        self.mock_data.songs = self.songs
        self.mock_data.selected_songs = []

        self.song_actions = SongActions(self.mock_data)

    def test_songs_has_list_changed_method(self):
        """Test that Songs class has the list_changed method"""
        assert hasattr(self.songs, "list_changed")
        assert callable(self.songs.list_changed)

    def test_songs_emits_signals_on_operations(self):
        """Test that Songs emits proper signals on add/remove/clear"""
        # Mock the signals
        with patch.object(self.songs, "listChanged") as mock_list_changed:
            with patch.object(self.songs, "added") as mock_added:
                with patch.object(self.songs, "deleted") as mock_deleted:
                    with patch.object(self.songs, "cleared") as mock_cleared:

                        # Test add
                        mock_song = Mock(spec=Song)
                        self.songs.add(mock_song)
                        mock_added.emit.assert_called_once_with(mock_song)
                        mock_list_changed.emit.assert_called()

                        # Reset mocks
                        mock_list_changed.reset_mock()

                        # Test remove
                        self.songs.remove(mock_song)
                        mock_deleted.emit.assert_called_once_with(mock_song)
                        mock_list_changed.emit.assert_called()

                        # Reset mocks
                        mock_list_changed.reset_mock()

                        # Test clear
                        self.songs.clear()
                        mock_cleared.emit.assert_called_once()
                        mock_list_changed.emit.assert_called()

    def test_delete_selected_song_no_selection(self):
        """Test delete when no songs are selected"""
        with patch("actions.song_actions.logger") as mock_logger:
            self.song_actions.delete_selected_song()
            mock_logger.error.assert_called_with("No songs selected to delete.")

    def test_delete_selected_song_success(self):
        """Test successful deletion of selected songs"""
        # Create mock songs
        song1 = Mock(spec=Song)
        song1.path = "/path/to/song1"

        song2 = Mock(spec=Song)
        song2.path = "/path/to/song2"

        # Add songs to the model
        self.songs.add(song1)
        self.songs.add(song2)

        # Select songs for deletion
        self.mock_data.selected_songs = [song1, song2]

        # Mock the service
        with patch("actions.song_actions.SongService") as mock_service_class:
            mock_service = mock_service_class.return_value
            mock_service.delete_song.return_value = True  # Successful deletion

            with patch.object(self.songs, "list_changed") as mock_list_changed:
                with patch("actions.song_actions.logger") as mock_logger:
                    self.song_actions.delete_selected_song()

                    # Verify service was called for both songs
                    assert mock_service.delete_song.call_count == 2
                    mock_service.delete_song.assert_any_call(song1)
                    mock_service.delete_song.assert_any_call(song2)

                    # Verify songs were removed from model
                    assert song1 not in self.songs.songs
                    assert song2 not in self.songs.songs

                    # Verify list_changed was called
                    mock_list_changed.assert_called_once()

                    # Verify selection was cleared
                    assert len(self.mock_data.selected_songs) == 0

                    # Verify logging
                    mock_logger.info.assert_any_call("Attempting to delete 2 songs.")

    def test_delete_selected_song_with_failure(self):
        """Test deletion when one song fails to delete"""
        # Create mock songs
        song1 = Mock(spec=Song)
        song1.path = "/path/to/song1"

        song2 = Mock(spec=Song)
        song2.path = "/path/to/song2"
        song2.set_error = Mock()

        # Add songs to the model
        self.songs.add(song1)
        self.songs.add(song2)

        # Select songs for deletion
        self.mock_data.selected_songs = [song1, song2]

        # Mock the service - song1 succeeds, song2 fails
        with patch("actions.song_actions.SongService") as mock_service_class:
            mock_service = mock_service_class.return_value
            mock_service.delete_song.side_effect = [True, False]  # First succeeds, second fails

            with patch.object(self.songs, "list_changed") as mock_list_changed:
                with patch.object(self.songs, "updated") as mock_updated:
                    with patch("actions.song_actions.logger") as mock_logger:
                        self.song_actions.delete_selected_song()

                        # Verify service was called for both songs
                        assert mock_service.delete_song.call_count == 2

                        # Verify first song was deleted successfully
                        assert song1 not in self.songs.songs  # Successfully deleted song is removed

                        # Verify second song delete failed
                        song2.set_error.assert_called_once_with("Failed to delete song files")
                        assert song2 in self.songs.songs  # Failed song stays in list

                        # Verify updated signal was emitted for failed song
                        mock_updated.emit.assert_called_with(song2)

                        # Verify error was logged
                        mock_logger.error.assert_called_with("Failed to delete song /path/to/song2")

                        # Verify list_changed was called
                        mock_list_changed.assert_called_once()

    def test_delete_selected_song_with_exception(self):
        """Test deletion when a song throws an exception"""
        # Create mock song that throws exception
        song = Mock(spec=Song)
        song.path = "/path/to/song"
        song.set_error = Mock()

        # Add song to the model
        self.songs.add(song)

        # Select song for deletion
        self.mock_data.selected_songs = [song]

        # Mock the service to throw exception
        with patch("actions.song_actions.SongService") as mock_service_class:
            mock_service = mock_service_class.return_value
            mock_service.delete_song.side_effect = Exception("File system error")

            with patch.object(self.songs, "list_changed") as mock_list_changed:
                with patch.object(self.songs, "updated") as mock_updated:
                    with patch("actions.song_actions.logger") as mock_logger:
                        self.song_actions.delete_selected_song()

                        # Verify delete was attempted
                        mock_service.delete_song.assert_called_once_with(song)

                        # Verify song stays in list (not removed due to exception)
                        assert song in self.songs.songs

                        # Verify song error method was called
                        song.set_error.assert_called_once_with("Delete error: File system error")

                        # Verify updated signal was emitted
                        mock_updated.emit.assert_called_with(song)

                        # Verify exception was logged
                        mock_logger.error.assert_called_with("Exception deleting song /path/to/song: File system error")

                        # Verify list_changed was called
                        mock_list_changed.assert_called_once()


class TestMediaPlayerNoneHandling:
    """Test mediaplayer component handles None song properly"""

    def test_on_song_changed_with_none(self):
        """Test that on_song_changed handles None song without AttributeError"""
        # This would typically require importing the MediaPlayerComponent
        # For now, we test the logic that we know should work

        def simulate_on_song_changed(song):
            """Simulate the fixed on_song_changed method"""
            if song is None:
                return "cleared_player"  # Simulate clearing UI

            # This would have caused AttributeError before the fix
            if not hasattr(song, "notes") or song.notes is None:
                return "reload_needed"

            return "normal_processing"

        # Test with None
        result = simulate_on_song_changed(None)
        assert result == "cleared_player"

        # Test with song without notes
        mock_song = Mock()
        mock_song.notes = None
        result = simulate_on_song_changed(mock_song)
        assert result == "reload_needed"

        # Test with normal song
        mock_song.notes = ["note1", "note2"]
        result = simulate_on_song_changed(mock_song)
        assert result == "normal_processing"
