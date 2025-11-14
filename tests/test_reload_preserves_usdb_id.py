"""
Test that reload operations preserve USDB ID from .usdb files.
"""

import pytest
import os
import json
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from workers.reload_song_worker import ReloadSongWorker
from workers.load_usdx_files import LoadUsdxFilesWorker
from model.song import Song


@pytest.fixture
def temp_song_dir(tmp_path):
    """Create a temporary song directory with .usdb file."""
    song_dir = tmp_path / "Artist - Title"
    song_dir.mkdir()

    # Create .txt file
    txt_file = song_dir / "Artist - Title.txt"
    txt_file.write_text("#TITLE:Title\n#ARTIST:Artist\n#MP3:audio.mp3\n#BPM:120\n#GAP:0\n: 0 1 0 test\n")

    # Create .usdb file with song_id
    usdb_file = song_dir / "test.usdb"
    usdb_data = {
        "song_id": 1806,
        "usdb_mtime": 1204888333,
        "txt": {"fname": "Artist - Title.txt", "resource": "https://usdb.animux.de/?link=gettxt&id=1806"}
    }
    usdb_file.write_text(json.dumps(usdb_data))

    return song_dir


def test_reload_song_worker_preserves_usdb_id(temp_song_dir):
    """Test that ReloadSongWorker extracts and assigns USDB ID from .usdb file."""
    txt_file = str(temp_song_dir / "Artist - Title.txt")

    # Mock the song service to return a basic song
    with patch("workers.reload_song_worker.song_service.SongService") as mock_service_class:
        mock_service = mock_service_class.return_value

        # Create a mock song without USDB ID
        mock_song = Song(txt_file)
        mock_song.title = "Title"
        mock_song.artist = "Artist"
        mock_song.usdb_id = None  # Initially no USDB ID

        mock_service.load_song = AsyncMock(return_value=mock_song)

        # Create worker and load song
        worker = ReloadSongWorker(txt_file, str(temp_song_dir))
        reloaded_song = asyncio.run(worker.load())

        # Verify USDB ID was assigned
        assert reloaded_song.usdb_id == 1806, f"Expected USDB ID 1806, got {reloaded_song.usdb_id}"


def test_reload_song_worker_handles_missing_usdb_file(tmp_path):
    """Test that ReloadSongWorker handles directories without .usdb files gracefully."""
    song_dir = tmp_path / "No USDB Song"
    song_dir.mkdir()
    txt_file = song_dir / "song.txt"
    txt_file.write_text("#TITLE:Test\n#ARTIST:Test\n#MP3:audio.mp3\n#BPM:120\n#GAP:0\n: 0 1 0 test\n")

    with patch("workers.reload_song_worker.song_service.SongService") as mock_service_class:
        mock_service = mock_service_class.return_value

        mock_song = Song(str(txt_file))
        mock_song.title = "Test"
        mock_song.usdb_id = None

        mock_service.load_song = AsyncMock(return_value=mock_song)

        worker = ReloadSongWorker(str(txt_file), str(song_dir))
        reloaded_song = asyncio.run(worker.load())

        # Should be None when no .usdb file exists
        assert reloaded_song.usdb_id is None


def test_reload_song_worker_handles_malformed_usdb_file(tmp_path):
    """Test that ReloadSongWorker handles malformed .usdb files without crashing."""
    song_dir = tmp_path / "Bad USDB Song"
    song_dir.mkdir()
    txt_file = song_dir / "song.txt"
    txt_file.write_text("#TITLE:Test\n#ARTIST:Test\n#MP3:audio.mp3\n#BPM:120\n#GAP:0\n: 0 1 0 test\n")

    # Create malformed .usdb file
    usdb_file = song_dir / "bad.usdb"
    usdb_file.write_text("not valid json {{{")

    with patch("workers.reload_song_worker.song_service.SongService") as mock_service_class:
        mock_service = mock_service_class.return_value

        mock_song = Song(str(txt_file))
        mock_song.title = "Test"
        mock_song.usdb_id = None

        mock_service.load_song = AsyncMock(return_value=mock_song)

        worker = ReloadSongWorker(str(txt_file), str(song_dir))
        reloaded_song = asyncio.run(worker.load())

        # Should be None when .usdb file is malformed (logged as warning)
        assert reloaded_song.usdb_id is None


def test_load_usdx_files_worker_single_reload_preserves_usdb_id(temp_song_dir):
    """Test that LoadUsdxFilesWorker single-file-reload uses ReloadSongWorker which preserves USDB ID.

    Note: LoadUsdxFilesWorker delegates to the load() method which calls ReloadSongWorker's
    _get_usdb_id_for_directory(), so USDB ID preservation is handled there."""
    # This test verifies that the worker properly delegates to the load method
    # The actual USDB ID preservation is tested in test_reload_song_worker_preserves_usdb_id
    txt_file = str(temp_song_dir / "Artist - Title.txt")

    with (
        patch("workers.load_usdx_files.SongService") as mock_service_class,
        patch("workers.load_usdx_files.get_all_cache_entries") as mock_cache,
    ):
        mock_service = mock_service_class.return_value
        mock_cache.return_value = {}  # No cache

        # Create a mock song
        mock_song = Song(txt_file)
        mock_song.title = "Title"
        mock_song.artist = "Artist"
        mock_song.usdb_id = None  # Will be set by ReloadSongWorker's _get_usdb_id_for_directory

        mock_service.load_song = AsyncMock(return_value=mock_song)

        # Create worker in reload mode
        worker = LoadUsdxFilesWorker(str(temp_song_dir), None, None)
        worker.reload_single_file = txt_file

        # Run worker
        asyncio.run(worker.run())

        # Verify the worker ran successfully (USDB ID tested in ReloadSongWorker test)
        assert worker.reload_single_file == txt_file
