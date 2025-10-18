"""
Tests for reload_song_light() - metadata-only reload without status changes.
Validates the fix for PermissionError bug (passing directory instead of txt_file).
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from actions.song_actions import SongActions
from model.song import Song
from app.app_data import AppData
from model.songs import Songs


@pytest.fixture
def mock_app_data():
    """Create AppData with mocked dependencies."""
    data = MagicMock(spec=AppData)
    data.songs = MagicMock(spec=Songs)
    data.selected_songs = MagicMock()
    data.config = MagicMock()
    data.worker_queue = MagicMock()
    return data


@pytest.fixture
def song_actions(mock_app_data):
    """Create SongActions instance for testing."""
    return SongActions(mock_app_data)


def test_reload_song_light_uses_txt_file_not_path(song_actions, fake_run_async):
    """
    Test that reload_song_light() passes song.txt_file (not song.path) to service.
    This validates the fix for the PermissionError bug.
    """
    # Create a song with known path values
    test_song = Song("Z:/Songs/Artist/Title.txt")
    test_song.title = "Test Song"
    test_song.artist = "Test Artist"

    # Mock the service to verify the parameter it receives
    with patch('actions.song_actions.SongService') as mock_service_class, \
         patch('actions.song_actions.run_async') as mock_run_async:
        mock_service = mock_service_class.return_value

        # Mock load_song_metadata_only to return a reloaded song
        reloaded = Song("Z:/Songs/Artist/Title.txt")
        reloaded.title = "Reloaded Song"
        reloaded.artist = "Reloaded Artist"
        mock_service.load_song_metadata_only = AsyncMock(return_value=reloaded)

        # Use centralized async executor fixture
        mock_run_async.side_effect = fake_run_async

        # Call reload_song_light
        song_actions.reload_song_light(specific_song=test_song)

        # Verify that service was called with txt_file, NOT path (directory)
        mock_service.load_song_metadata_only.assert_called_once()
        call_args = mock_service.load_song_metadata_only.call_args[0]

        # The first argument should be txt_file (full file path)
        assert call_args[0] == test_song.txt_file, \
            f"Expected txt_file '{test_song.txt_file}', got '{call_args[0]}'"

        # It should NOT be the directory path
        assert call_args[0] != test_song.path, \
            f"Service should receive txt_file, not path (directory)"


def test_reload_song_light_does_not_change_status(song_actions, mock_app_data, fake_run_async):
    """
    Test that reload_song_light() does not change song.status.
    This is the core requirement for viewport lazy-loading.
    """
    from model.gap_info import GapInfo

    test_song = Song("Z:/Songs/Artist/Title.txt")
    # Set status by assigning gap_info with detected status
    gap_info = GapInfo("/test/path")
    gap_info.owner = test_song
    from model.gap_info import GapInfoStatus
    gap_info.status = GapInfoStatus.MATCH
    test_song._gap_info = gap_info
    test_song._gap_info_updated()  # This sets status to MATCH

    initial_status = test_song.status

    with patch('actions.song_actions.SongService') as mock_service_class, \
         patch('actions.song_actions.run_async') as mock_run_async:
        mock_service = mock_service_class.return_value

        # Mock reloaded song - metadata only, no status change
        reloaded = Song("Z:/Songs/Artist/Title.txt")
        reloaded.title = "Reloaded"
        mock_service.load_song_metadata_only = AsyncMock(return_value=reloaded)

        # Use centralized async executor fixture
        mock_run_async.side_effect = fake_run_async

        # Call reload
        song_actions.reload_song_light(specific_song=test_song)

        # Verify status was preserved
        assert test_song.status == initial_status, \
            f"Status should remain {initial_status}, got {test_song.status}"


def test_reload_song_light_with_error_handling(song_actions, fake_run_async):
    """
    Test that reload_song_light() handles service errors gracefully.
    Now async - uses QTimer to wait for callback completion.
    """
    from PySide6.QtCore import QCoreApplication

    test_song = Song("Z:/Songs/NonExistent/Title.txt")

    with patch('actions.song_actions.SongService') as mock_service_class, \
         patch('actions.song_actions.run_async') as mock_run_async:
        mock_service = mock_service_class.return_value

        # Mock service to return a song with error
        error_song = Song("Z:/Songs/NonExistent/Title.txt")
        error_song.set_error("File not found: Z:/Songs/NonExistent/Title.txt")
        mock_service.load_song_metadata_only = AsyncMock(return_value=error_song)

        # Use centralized async executor fixture
        mock_run_async.side_effect = fake_run_async

        # Should not raise exception
        song_actions.reload_song_light(specific_song=test_song)

        # Process events to allow callback to execute
        QCoreApplication.processEvents()

        # Verify error was propagated
        assert test_song.status_text == "File not found: Z:/Songs/NonExistent/Title.txt"


def test_metadata_only_validates_path_is_file():
    """
    Test that load_song_metadata_only() validates that the path is a file, not a directory.
    This prevents the PermissionError when opening directories.
    """
    from services.song_service import SongService
    import os

    # Create a real directory path
    test_dir = os.path.dirname(__file__)  # tests/ directory

    service = SongService()

    # Import asyncio to run async function
    import asyncio

    # Attempt to load a directory as a song file
    song = asyncio.run(service.load_song_metadata_only(test_dir))

    # Should return a song with error, not raise PermissionError
    assert song.status_text is not None and len(song.status_text) > 0
    assert "invalid path" in song.status_text.lower() or "expected file" in song.status_text.lower()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
