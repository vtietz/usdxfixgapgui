"""Tests for Song model error handling semantics."""

from model.song import Song, SongStatus
from model.gap_info import GapInfo, GapInfoStatus


class TestSongErrorHandling:
    """Test Song.set_error() and Song.clear_error() semantics."""

    def test_set_error_sets_status_and_message(self):
        """set_error should set status to ERROR and store the message."""
        song = Song()
        error_msg = "Test error message"

        song.set_error(error_msg)

        assert song.status == SongStatus.ERROR
        assert song.error_message == error_msg

    def test_clear_error_resets_to_not_processed(self):
        """clear_error should set status to NOT_PROCESSED and clear message."""
        song = Song()
        song.set_error("Some error")

        song.clear_error()

        assert song.status == SongStatus.NOT_PROCESSED
        assert song.error_message is None

    def test_clear_error_from_not_processed_state(self):
        """clear_error should work even if not in ERROR state."""
        song = Song()
        assert song.status == SongStatus.NOT_PROCESSED

        song.clear_error()

        assert song.status == SongStatus.NOT_PROCESSED
        assert song.error_message is None

    def test_multiple_set_error_calls(self):
        """Multiple set_error calls should update the message."""
        song = Song()

        song.set_error("First error")
        assert song.error_message == "First error"

        song.set_error("Second error")
        assert song.error_message == "Second error"
        assert song.status == SongStatus.ERROR

    def test_clear_error_after_processing(self):
        """clear_error after successful processing should reset state."""
        song = Song()
        song.status = SongStatus.PROCESSING
        song.set_error("Processing failed")

        # Simulate successful recovery
        song.clear_error()

        assert song.status == SongStatus.NOT_PROCESSED
        assert song.error_message is None


class TestGapInfoStatusMapping:
    """Test that GapInfo-driven status mapping is unaffected by clear_error."""

    def test_gap_info_status_match_overrides_clear_error(self):
        """Setting gap_info with MATCH status should override NOT_PROCESSED."""
        song = Song()
        song.clear_error()
        assert song.status == SongStatus.NOT_PROCESSED

        gap_info = GapInfo()
        gap_info.status = GapInfoStatus.MATCH
        song.gap_info = gap_info

        assert song.status == SongStatus.MATCH

    def test_gap_info_status_mismatch(self):
        """Setting gap_info with MISMATCH status should set song status."""
        song = Song()

        gap_info = GapInfo()
        gap_info.status = GapInfoStatus.MISMATCH
        song.gap_info = gap_info

        assert song.status == SongStatus.MISMATCH

    def test_gap_info_status_error(self):
        """Setting gap_info with ERROR status should set song status."""
        song = Song()

        gap_info = GapInfo()
        gap_info.status = GapInfoStatus.ERROR
        song.gap_info = gap_info

        assert song.status == SongStatus.ERROR

    def test_gap_info_status_updated(self):
        """Setting gap_info with UPDATED status should set song status."""
        song = Song()

        gap_info = GapInfo()
        gap_info.status = GapInfoStatus.UPDATED
        song.gap_info = gap_info

        assert song.status == SongStatus.UPDATED

    def test_gap_info_status_solved(self):
        """Setting gap_info with SOLVED status should set song status."""
        song = Song()

        gap_info = GapInfo()
        gap_info.status = GapInfoStatus.SOLVED
        song.gap_info = gap_info

        assert song.status == SongStatus.SOLVED

    def test_gap_info_none_resets_to_not_processed(self):
        """Setting gap_info to None should reset status to NOT_PROCESSED."""
        song = Song()
        gap_info = GapInfo()
        gap_info.status = GapInfoStatus.MATCH
        song.gap_info = gap_info
        assert song.status == SongStatus.MATCH

        song.gap_info = None

        assert song.status == SongStatus.NOT_PROCESSED

    def test_clear_error_does_not_affect_gap_info_mapping(self):
        """clear_error should not interfere with gap_info status mapping."""
        song = Song()
        song.set_error("Test error")

        # Clear error, then set gap_info
        song.clear_error()

        gap_info = GapInfo()
        gap_info.status = GapInfoStatus.MATCH
        song.gap_info = gap_info

        # Should be MATCH from gap_info, not NOT_PROCESSED from clear_error
        assert song.status == SongStatus.MATCH


class TestInitialState:
    """Test Song initial state."""

    def test_initial_status_is_not_processed(self):
        """New Song should have NOT_PROCESSED status."""
        song = Song()
        assert song.status == SongStatus.NOT_PROCESSED

    def test_initial_error_message_is_empty(self):
        """New Song should have empty error message."""
        song = Song()
        assert song.error_message == ""


class TestSongStatusTimestamp:
    """Test that status timestamps are driven by gap_info, not transient status changes."""

    def test_gap_info_timestamp_takes_precedence(self):
        """When gap_info has processed_time, it should always be used for display/sorting."""
        from model.gap_info import GapInfo, GapInfoStatus

        song = Song()
        # Set a status change timestamp
        song.set_status_timestamp_from_string("2024-01-01 00:00:00")
        assert song.status_time_display == "2024-01-01 00:00:00"

        # Now assign gap_info with a different processed_time
        gap_info = GapInfo()
        gap_info.status = GapInfoStatus.MATCH
        gap_info.processed_time = "2025-05-05 05:05:05"
        song.gap_info = gap_info

        # Gap info timestamp should take precedence
        assert song.status_time_display == "2025-05-05 05:05:05"

        # Even if we change status (triggering _status_changed_str update), gap_info wins
        song.status = SongStatus.QUEUED
        assert song.status_time_display == "2025-05-05 05:05:05"

    def test_fallback_to_status_timestamp_when_no_gap_info(self):
        """When no gap_info exists, fall back to status change timestamp."""
        song = Song()
        song.set_status_timestamp_from_string("2024-01-01 00:00:00")

        assert song.status_time_display == "2024-01-01 00:00:00"
        assert song.status_time_sort_key == "2024-01-01 00:00:00"


class TestValidationErrorHandling:
    """Test that ValidationError (missing GAP/BPM/etc.) is handled gracefully."""

    def test_missing_gap_tag_defaults_to_zero(self, tmp_path):
        """Song with missing GAP tag should default to GAP=0, allowing gap detection."""
        import asyncio
        from services.song_service import SongService

        # Create a song file without GAP tag (like PS2 Singstar songs)
        song_file = tmp_path / "notes.txt"
        song_file.write_text(
            "#TITLE:Test Song\n"
            "#ARTIST:Test Artist\n"
            "#MP3:test.mp3\n"
            "#BPM:300\n"
            ": 0 4 0 Test\n"
            "E\n",
            encoding="utf-8"
        )

        # Create dummy audio file
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")

        service = SongService()
        song = asyncio.run(service.load_song(str(song_file)))

        # Should load successfully with GAP=0
        assert song.status == SongStatus.NOT_PROCESSED
        assert song.gap == 0
        assert song.title == "Test Song"
        assert song.artist == "Test Artist"

    def test_missing_bpm_tag_marks_song_as_error(self, tmp_path):
        """Song with missing BPM tag should be marked as ERROR (BPM is required for timing calculations)."""
        import asyncio
        from services.song_service import SongService

        song_file = tmp_path / "notes.txt"
        song_file.write_text(
            "#TITLE:Test Song\n"
            "#ARTIST:Test Artist\n"
            "#MP3:test.mp3\n"
            "#GAP:1000\n"
            ": 0 4 0 Test\n"
            "E\n",
            encoding="utf-8"
        )

        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")

        service = SongService()
        song = asyncio.run(service.load_song(str(song_file)))

        # BPM is truly required (can't calculate note timings without it)
        assert song.status == SongStatus.ERROR
        assert song.error_message is not None
        assert "BPM" in song.error_message
