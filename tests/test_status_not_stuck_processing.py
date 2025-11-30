"""Test that song status doesn't get stuck in PROCESSING after gap detection completes."""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from model.song import Song, SongStatus
from model.gap_info import GapInfo, GapInfoStatus
from actions.gap_actions import GapActions
from workers.detect_gap import GapDetectionResult


@pytest.fixture
def song_with_audio(tmp_path):
    """Create a song with audio file"""
    audio_file = tmp_path / "test.mp3"
    audio_file.write_text("fake audio")

    txt_file = tmp_path / "test.txt"
    txt_file.write_text("#TITLE:Test\n#ARTIST:Test\n#MP3:test.mp3\n#GAP:1000\n")

    song = Song(str(txt_file))
    song.audio_file = str(audio_file)
    song.title = "Test Song"
    song.artist = "Test Artist"
    song.gap = 1000
    song.duration_ms = 180000

    # Create gap_info and set owner
    song.gap_info = GapInfo(str(tmp_path / "usdxfixgap.info"), "test.txt")
    song.gap_info.owner = song

    return song


def test_status_remains_match_after_gap_detection_with_waveform_creation(app_data, song_with_audio):
    """Test that status stays MATCH after gap detection even when waveforms are created."""
    song = song_with_audio

    # Create result indicating a MATCH
    result = GapDetectionResult(song.txt_file)
    result.detected_gap = 1100
    result.gap_diff = 100
    result.silence_periods = [(0.0, 1100.0)]
    result.duration_ms = 180000
    result.status = GapInfoStatus.MATCH

    with (
        patch("actions.gap_actions.run_async"),
        patch("actions.gap_actions.GapInfoService.save", new_callable=AsyncMock),
        patch("actions.gap_actions.AudioActions") as mock_audio_class,
    ):
        # Mock AudioActions to prevent actual waveform creation
        mock_audio = Mock()
        mock_audio_class.return_value = mock_audio

        # Call the finished handler
        gap_actions = GapActions(app_data)
        gap_actions._on_detect_gap_finished(song, result)

        # Verify status is MATCH
        assert song.status == SongStatus.MATCH, f"Expected MATCH but got {song.status}"
        assert song.gap_info.status == GapInfoStatus.MATCH

        # Simulate waveform workers calling songs.updated.emit()
        # (which would trigger _on_song_updated in mediaplayer)
        app_data.songs.updated.emit(song)

        # Status should STILL be MATCH, not PROCESSING
        assert song.status == SongStatus.MATCH, f"Status changed to {song.status} after update signal"


def test_status_not_overridden_by_late_binding_lambda(app_data, song_with_audio, fake_run_async):
    """Test that late-binding lambda bug doesn't cause wrong song to get PROCESSING status."""
    from unittest.mock import patch

    with patch("actions.gap_actions.run_async") as mock_run_async:
        # Use centralized async executor fixture to prevent unawaited coroutines
        mock_run_async.side_effect = fake_run_async

        song1 = song_with_audio
        song2 = Song(str(song_with_audio.txt_file).replace("test.txt", "test2.txt"))
        song2.audio_file = str(song_with_audio.audio_file).replace("test.mp3", "test2.mp3")
        song2.title = "Song 2"
        song2.gap_info = GapInfo()
        song2.gap_info.owner = song2

        # Song 1 finishes detection with MATCH
        song1.gap_info.status = GapInfoStatus.MATCH
        assert song1.status == SongStatus.MATCH

        # Song 2 starts detection (should set Song 2 to PROCESSING, not Song 1)
        song2.status = SongStatus.PROCESSING

        # Song 1 should STILL be MATCH
        assert song1.status == SongStatus.MATCH, f"Song1 status incorrectly changed to {song1.status}"
        assert song2.status == SongStatus.PROCESSING


def test_restore_status_from_gap_info_preserves_match(app_data, song_with_audio, fake_run_async):
    """Test that _restore_status_from_gap_info() correctly restores MATCH status."""
    from actions.base_actions import BaseActions
    from unittest.mock import patch

    with patch("actions.gap_actions.run_async") as mock_run_async:
        # Use centralized async executor fixture to prevent unawaited coroutines
        mock_run_async.side_effect = fake_run_async

        song = song_with_audio
        song.gap_info.status = GapInfoStatus.MATCH
        song.status = SongStatus.PROCESSING  # Simulate worker setting this

        base_actions = BaseActions(app_data)
        base_actions._restore_status_from_gap_info(song)

        # Should restore to MATCH based on gap_info
        assert song.status == SongStatus.MATCH, f"Expected MATCH but got {song.status}"


def test_gap_info_status_setter_immediately_updates_song_status(song_with_audio):
    """Test that setting gap_info.status immediately updates song.status."""
    song = song_with_audio

    # Set initial state
    song.status = SongStatus.PROCESSING
    assert song.status == SongStatus.PROCESSING

    # Set gap_info.status which should trigger owner update
    song.gap_info.status = GapInfoStatus.MATCH

    # Status should be MATCH immediately after setter returns
    assert song.status == SongStatus.MATCH, f"Expected MATCH but got {song.status} after setting gap_info.status"

    # Try reading it again to make sure it didn't somehow revert
    status_after = song.status
    assert status_after == SongStatus.MATCH, f"Status reverted to {status_after} after reading"
