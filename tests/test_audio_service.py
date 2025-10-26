"""
Tests for AudioService facade.
"""

import pytest
from unittest.mock import Mock, MagicMock, PropertyMock
from src.services.audio_service import AudioService, AudioSource


@pytest.fixture
def mock_player():
    """Create a mock PlayerController."""
    player = Mock()
    player.media_player = Mock()
    player.position_changed = Mock()
    player.is_playing_changed = Mock()
    player.position_changed.connect = Mock()
    player.is_playing_changed.connect = Mock()
    return player


@pytest.fixture
def audio_service(mock_player):
    """Create AudioService with mock player."""
    return AudioService(mock_player)


def test_audio_service_initialization(audio_service, mock_player):
    """Test AudioService initializes with default values."""
    assert audio_service.source == AudioSource.ORIGINAL
    assert audio_service.is_playing is False
    assert audio_service.position_ms == 0

    # Should connect to player signals
    mock_player.position_changed.connect.assert_called_once()
    mock_player.is_playing_changed.connect.assert_called_once()


def test_set_source_original(audio_service, mock_player):
    """Test setting source to ORIGINAL."""
    audio_service.set_source(AudioSource.ORIGINAL)

    assert audio_service.source == AudioSource.ORIGINAL


def test_set_source_extracted(audio_service, mock_player):
    """Test setting source to EXTRACTED."""
    mock_song = Mock()
    mock_song.vocals_file = "/path/to/vocals.mp3"
    audio_service._current_song = mock_song

    audio_service.set_source(AudioSource.EXTRACTED)

    assert audio_service.source == AudioSource.EXTRACTED
    mock_player.vocals_mode.assert_called_once()


def test_set_source_both_falls_back_to_original(audio_service):
    """Test BOTH source falls back to ORIGINAL (not implemented)."""
    audio_service.set_source(AudioSource.BOTH)

    assert audio_service.source == AudioSource.ORIGINAL


def test_set_source_same_does_nothing(audio_service, mock_player):
    """Test setting same source doesn't reload."""
    audio_service.set_source(AudioSource.ORIGINAL)
    mock_player.audio_mode.reset_mock()

    audio_service.set_source(AudioSource.ORIGINAL)

    mock_player.audio_mode.assert_not_called()


def test_play(audio_service, mock_player):
    """Test play delegates to player."""
    audio_service.play()

    mock_player.play.assert_called_once()


def test_pause(audio_service, mock_player):
    """Test pause when playing."""
    audio_service._is_playing = True

    audio_service.pause()

    mock_player.play.assert_called_once()  # Toggle


def test_pause_when_not_playing(audio_service, mock_player):
    """Test pause when not playing does nothing."""
    audio_service._is_playing = False

    audio_service.pause()

    mock_player.play.assert_not_called()


def test_stop(audio_service, mock_player):
    """Test stop delegates to player."""
    audio_service.stop()

    mock_player.stop.assert_called_once()


def test_seek_ms(audio_service, mock_player):
    """Test seeking to position."""
    audio_service.seek_ms(5000)

    mock_player.media_player.setPosition.assert_called_once_with(5000)


def test_jump_to_current_gap(audio_service, mock_player):
    """Test jumping to current gap."""
    audio_service.jump_to_current_gap(8125)

    mock_player.media_player.setPosition.assert_called_once_with(8125)


def test_jump_to_detected_gap(audio_service, mock_player):
    """Test jumping to detected gap."""
    audio_service.jump_to_detected_gap(8105)

    mock_player.media_player.setPosition.assert_called_once_with(8105)


def test_preload_song(audio_service, mock_player):
    """Test preloading song with original source."""
    mock_song = Mock()
    mock_song.audio_file = "/path/to/audio.mp3"
    mock_song.name = "Test Song"

    audio_service.preload(mock_song)

    assert audio_service._current_song == mock_song
    mock_player.audio_mode.assert_called_once()
    mock_player.load_media.assert_called_once_with("/path/to/audio.mp3")


def test_preload_with_extracted_source(audio_service, mock_player):
    """Test preloading song with extracted source."""
    mock_song = Mock()
    mock_song.vocals_file = "/path/to/vocals.mp3"
    mock_song.name = "Test Song"

    audio_service.set_source(AudioSource.EXTRACTED)
    audio_service.preload(mock_song)

    mock_player.vocals_mode.assert_called()
    mock_player.load_media.assert_called_with("/path/to/vocals.mp3")


def test_preload_extracted_falls_back_when_no_vocals(audio_service, mock_player):
    """Test preloading falls back to original when vocals missing."""
    mock_song = Mock()
    mock_song.audio_file = "/path/to/audio.mp3"
    mock_song.vocals_file = None
    mock_song.name = "Test Song"

    audio_service.set_source(AudioSource.EXTRACTED)
    audio_service.preload(mock_song)

    # Should fall back to original
    assert audio_service.source == AudioSource.ORIGINAL
    mock_player.audio_mode.assert_called()
    mock_player.load_media.assert_called_with("/path/to/audio.mp3")


def test_preload_with_next_song(audio_service):
    """Test preloading with next song queued."""
    mock_song = Mock()
    mock_song.audio_file = "/path/to/audio.mp3"
    mock_next_song = Mock()
    mock_next_song.name = "Next Song"

    audio_service.preload(mock_song, mock_next_song)

    assert audio_service._next_song == mock_next_song


def test_subscribe_on_playback_change(audio_service):
    """Test subscribing to playback changes."""
    callback = Mock()

    audio_service.subscribe_on_playback_change(callback)

    assert callback in audio_service._playback_change_callbacks


def test_playback_change_callback_triggered(audio_service):
    """Test callback triggered on playback state change."""
    callback_count = [0]

    def callback():
        callback_count[0] += 1

    audio_service.subscribe_on_playback_change(callback)

    # Simulate playing state change
    audio_service._on_playing_changed(True)

    assert callback_count[0] == 1


def test_unsubscribe_on_playback_change(audio_service):
    """Test unsubscribing from playback changes."""
    callback = Mock()

    audio_service.subscribe_on_playback_change(callback)
    audio_service.unsubscribe_on_playback_change(callback)

    assert callback not in audio_service._playback_change_callbacks


def test_position_changed_updates_position(audio_service):
    """Test position update from player."""
    audio_service._on_position_changed(5000)

    assert audio_service.position_ms == 5000


def test_position_changed_doesnt_trigger_callback(audio_service):
    """Test position changes don't trigger callbacks (too frequent)."""
    callback = Mock()
    audio_service.subscribe_on_playback_change(callback)

    audio_service._on_position_changed(5000)

    callback.assert_not_called()


def test_playing_changed_triggers_callback(audio_service):
    """Test playing state change triggers callback."""
    callback = Mock()
    audio_service.subscribe_on_playback_change(callback)

    audio_service._on_playing_changed(True)

    assert audio_service.is_playing is True
    callback.assert_called_once()


def test_callback_error_doesnt_crash(audio_service):
    """Test callback errors don't crash the service."""
    def bad_callback():
        raise ValueError("Test error")

    good_callback = Mock()

    audio_service.subscribe_on_playback_change(bad_callback)
    audio_service.subscribe_on_playback_change(good_callback)

    # Should not raise
    audio_service._on_playing_changed(True)

    # Good callback should still be called
    good_callback.assert_called_once()


def test_source_change_triggers_callback(audio_service, mock_player):
    """Test source change triggers playback change callback."""
    mock_song = Mock()
    mock_song.vocals_file = "/path/to/vocals.mp3"
    audio_service._current_song = mock_song

    callback = Mock()
    audio_service.subscribe_on_playback_change(callback)

    audio_service.set_source(AudioSource.EXTRACTED)

    callback.assert_called_once()