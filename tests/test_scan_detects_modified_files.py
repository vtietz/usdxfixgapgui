"""
Tests for LoadUsdxFilesWorker detecting modified files during scan.

This verifies the fix where scan_directory() now checks mtime for cached files
instead of blindly skipping them.
"""

import os
import pytest
import asyncio
import time
import datetime
from pathlib import Path
from workers.load_usdx_files import LoadUsdxFilesWorker
from common.database import set_cache_entry, get_cache_entry, clear_cache
from model.song import Song


@pytest.fixture
def sample_song_dir(tmp_path):
    """Create a temporary song directory with a .txt file."""
    song_dir = tmp_path / "Test Artist - Test Song"
    song_dir.mkdir()

    txt_file = song_dir / "Test Artist - Test Song.txt"
    txt_file.write_text(
        "#TITLE:Test Song\n"
        "#ARTIST:Test Artist\n"
        "#MP3:audio.mp3\n"
        "#BPM:120\n"
        "#GAP:1000\n"
        ": 0 4 0 Test\n"
    )

    # Create dummy audio file
    audio_file = song_dir / "audio.mp3"
    audio_file.write_bytes(b"fake audio data")

    return song_dir


@pytest.fixture(autouse=True)
def clear_cache_before_test():
    """Clear cache before each test."""
    clear_cache()
    yield
    clear_cache()


class TestModifiedFileDetection:
    """Tests for detecting modified files during scan."""

    def test_scan_detects_modified_txt_file(self, sample_song_dir, tmp_path):
        """Scan should detect when a cached .txt file has been modified."""
        txt_file = sample_song_dir / "Test Artist - Test Song.txt"

        # Step 1: Load the file initially (creates cache entry)
        worker1 = LoadUsdxFilesWorker(str(sample_song_dir.parent), str(tmp_path), None)
        asyncio.run(worker1.run())

        # Verify it was loaded
        assert len(worker1.loaded_paths) == 1

        # Step 2: Modify the .txt file (change GAP value)
        time.sleep(0.1)  # Ensure mtime difference
        txt_file.write_text(
            "#TITLE:Test Song\n"
            "#ARTIST:Test Artist\n"
            "#MP3:audio.mp3\n"
            "#BPM:120\n"
            "#GAP:2000\n"  # Changed from 1000
            ": 0 4 0 Test\n"
        )

        # Step 3: Scan again - should detect modification
        worker2 = LoadUsdxFilesWorker(str(sample_song_dir.parent), str(tmp_path), None)

        # Track if file was reloaded
        reloaded_files = []

        def on_batch_loaded(songs):
            for song in songs:
                reloaded_files.append(song.txt_file)

        worker2.signals.songsLoadedBatch.connect(on_batch_loaded)
        asyncio.run(worker2.run())

        # Verify the file was reloaded (appears in batch after cache load)
        # First batch is from cache, subsequent batches are from scan
        assert len(reloaded_files) > 1, "File should appear in both cache load and scan reload"

        # Verify the new GAP value is in cache
        mod_time = datetime.datetime.fromtimestamp(os.path.getmtime(str(txt_file)))
        cached_song = get_cache_entry(str(txt_file), mod_time)
        assert cached_song is not None, "Modified file should be in cache"
        assert cached_song.gap == 2000, "Cache should contain new GAP value"

    def test_scan_skips_unmodified_cached_files(self, sample_song_dir, tmp_path):
        """Scan should skip cached files that haven't been modified."""
        txt_file = sample_song_dir / "Test Artist - Test Song.txt"

        # Step 1: Load the file initially
        worker1 = LoadUsdxFilesWorker(str(sample_song_dir.parent), str(tmp_path), None)
        asyncio.run(worker1.run())

        initial_load_count = len(worker1.loaded_paths)

        # Step 2: Scan again WITHOUT modifying - should skip
        worker2 = LoadUsdxFilesWorker(str(sample_song_dir.parent), str(tmp_path), None)

        # Track loads during scan by counting batches
        batch_count = 0

        def on_batch_loaded(songs):
            nonlocal batch_count
            batch_count += 1

        worker2.signals.songsLoadedBatch.connect(on_batch_loaded)
        asyncio.run(worker2.run())

        # File should be loaded from cache (1st batch) but NOT during scan (no 2nd batch)
        assert batch_count == 1, "Unmodified file should only appear in cache load, not scan"

    def test_scan_loads_new_files_not_in_cache(self, sample_song_dir, tmp_path):
        """Scan should load new files that aren't in cache."""
        # Step 1: Load initial song
        worker1 = LoadUsdxFilesWorker(str(sample_song_dir.parent), str(tmp_path), None)
        asyncio.run(worker1.run())

        # Step 2: Add a new song
        new_song_dir = sample_song_dir.parent / "New Artist - New Song"
        new_song_dir.mkdir()

        new_txt_file = new_song_dir / "New Artist - New Song.txt"
        new_txt_file.write_text(
            "#TITLE:New Song\n"
            "#ARTIST:New Artist\n"
            "#MP3:new_audio.mp3\n"
            "#BPM:140\n"
            "#GAP:500\n"
            ": 0 4 0 New\n"
        )

        # Step 3: Scan again - should find new file
        worker2 = LoadUsdxFilesWorker(str(sample_song_dir.parent), str(tmp_path), None)
        asyncio.run(worker2.run())

        # Verify both songs are loaded
        assert len(worker2.loaded_paths) == 2, "Should have loaded both original and new song"

        # Verify new song is in cache
        mod_time = datetime.datetime.fromtimestamp(os.path.getmtime(str(new_txt_file)))
        cached_song = get_cache_entry(str(new_txt_file), mod_time)
        assert cached_song is not None, "New song should be cached"
        assert cached_song.title == "New Song"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
