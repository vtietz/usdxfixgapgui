"""
Tests for GapState integration into song selection.
"""

import pytest
from model.song import Song
from model.gap_info import GapInfo, GapInfoStatus
from actions.song_actions import SongActions
from app.app_data import AppData


@pytest.fixture
def app_data():
    """Create test AppData."""
    return AppData()


@pytest.fixture
def song_actions(app_data):
    """Create SongActions with test data."""
    return SongActions(app_data)


@pytest.fixture
def song_with_gap():
    """Create a song with gap info."""
    song = Song(txt_file="/path/to/song.txt")
    song.title = "Test Song"
    song.artist = "Test Artist"
    song.gap_info = GapInfo()
    song.gap_info.original_gap = 8125
    song.gap_info.detected_gap = 8105
    song.gap_info.status = GapInfoStatus.MISMATCH
    return song


@pytest.fixture
def song_without_detection():
    """Create a song without gap detection."""
    song = Song(txt_file="/path/to/song2.txt")
    song.title = "Undetected Song"
    song.artist = "Test Artist"
    song.gap_info = GapInfo()
    song.gap_info.original_gap = 5000
    song.gap_info.status = GapInfoStatus.NOT_PROCESSED
    return song


def test_single_song_creates_gap_state(song_actions, app_data, song_with_gap):
    """Test selecting single song creates GapState."""
    song_actions.set_selected_songs([song_with_gap])

    assert app_data.gap_state is not None
    assert app_data.gap_state.current_gap_ms == 8125
    assert app_data.gap_state.detected_gap_ms == 8105
    assert app_data.gap_state.diff_ms == 20
    assert app_data.gap_state.is_dirty is False


def test_single_song_without_detection(song_actions, app_data, song_without_detection):
    """Test selecting song without detection creates GapState."""
    song_actions.set_selected_songs([song_without_detection])

    assert app_data.gap_state is not None
    assert app_data.gap_state.current_gap_ms == 5000
    # GapInfo.detected_gap defaults to 0, not None - so has_detected_gap is True
    assert app_data.gap_state.detected_gap_ms == 0
    assert app_data.gap_state.diff_ms == 5000  # current - detected
    assert app_data.gap_state.has_detected_gap is True  # 0 is a valid detected gap


def test_multi_selection_clears_gap_state(song_actions, app_data, song_with_gap, song_without_detection):
    """Test multi-selection clears GapState."""
    # First select single
    song_actions.set_selected_songs([song_with_gap])
    assert app_data.gap_state is not None

    # Now select multiple
    song_actions.set_selected_songs([song_with_gap, song_without_detection])
    assert app_data.gap_state is None


def test_empty_selection_clears_gap_state(song_actions, app_data, song_with_gap):
    """Test empty selection clears GapState."""
    # First select single
    song_actions.set_selected_songs([song_with_gap])
    assert app_data.gap_state is not None

    # Clear selection
    song_actions.set_selected_songs([])
    assert app_data.gap_state is None


def test_switching_songs_replaces_gap_state(song_actions, app_data, song_with_gap, song_without_detection):
    """Test switching between songs replaces GapState."""
    # Select first song
    song_actions.set_selected_songs([song_with_gap])
    first_state = app_data.gap_state
    assert first_state.current_gap_ms == 8125

    # Select second song
    song_actions.set_selected_songs([song_without_detection])
    second_state = app_data.gap_state
    assert second_state is not first_state  # Different instance
    assert second_state.current_gap_ms == 5000


def test_song_without_gap_info(song_actions, app_data):
    """Test selecting song without gap_info."""
    song = Song(txt_file="/path/to/bare.txt")
    song.title = "Bare Song"
    song.gap_info = None

    song_actions.set_selected_songs([song])

    assert app_data.gap_state is not None
    assert app_data.gap_state.current_gap_ms == 0
    assert app_data.gap_state.detected_gap_ms is None


def test_gap_state_reflects_mismatch(song_actions, app_data, song_with_gap):
    """Test GapState reflects mismatch severity."""
    song_actions.set_selected_songs([song_with_gap])

    # 20ms diff should be WARNING
    from services.gap_state import SeverityBand
    assert app_data.gap_state.severity_band() == SeverityBand.GOOD  # 20ms is within GOOD threshold
    assert app_data.gap_state.format_diff() == "+20ms"
