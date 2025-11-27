"""
Unit tests for media backend implementations.

Tests VLC and Qt backend adapters for the unified MediaBackend protocol.
"""

import pytest
from unittest.mock import Mock, patch


class TestVlcBackendAdapter:
    """Test VLC backend adapter."""

    @pytest.fixture
    def mock_vlc(self):
        """Mock VLC module."""
        with patch("services.media.vlc_backend.vlc") as mock:
            # Mock VLC state enum
            mock.State.Playing = 3
            mock.State.Paused = 4
            mock.State.Stopped = 5
            mock.State.Ended = 6

            # Mock instance and player
            mock_instance = Mock()
            mock_player = Mock()
            mock_instance.media_player_new.return_value = mock_player
            mock.Instance.return_value = mock_instance
            mock.libvlc_get_version.return_value = b"3.0.21"

            yield mock

    @pytest.fixture
    def vlc_backend(self, mock_vlc):
        """Create VLC backend adapter with mocked VLC."""
        with patch("services.media.vlc_backend.VLC_AVAILABLE", True):
            from services.media.vlc_backend import VlcBackendAdapter
            from services.media.backend import PlaybackState, MediaStatus

            backend = VlcBackendAdapter()
            # Attach enums for test access
            backend._test_PS = PlaybackState
            backend._test_MS = MediaStatus
            return backend

    def test_initialization(self, vlc_backend):
        """Test VLC backend initializes with correct state."""
        PS = vlc_backend._test_PS
        MS = vlc_backend._test_MS

        assert vlc_backend.get_playback_state() == PS.STOPPED
        assert vlc_backend.get_media_status() == MS.NO_MEDIA
        assert not vlc_backend.is_playing()

    def test_load_media(self, vlc_backend):
        """Test loading media file."""
        test_file = "C:/test/song.mp3"
        vlc_backend.load(test_file)

        assert vlc_backend.get_current_file() == test_file
        assert vlc_backend._current_media is not None

    def test_playback_control(self, vlc_backend):
        """Test play, pause, stop methods."""
        PS = vlc_backend._test_PS
        vlc_backend.load("C:/test/song.mp3")

        # Test play
        vlc_backend.play()
        vlc_backend._player.play.assert_called_once()

        # Test pause
        vlc_backend._playback_state = PS.PLAYING
        vlc_backend.pause()
        vlc_backend._player.pause.assert_called_once()

        # Test stop
        vlc_backend.stop()
        vlc_backend._player.stop.assert_called_once()

    def test_volume_control(self, vlc_backend):
        """Test volume control."""
        vlc_backend.set_volume(75)
        vlc_backend._player.audio_set_volume.assert_called_once_with(75)

        vlc_backend._player.audio_get_volume.return_value = 75
        assert vlc_backend.get_volume() == 75

    def test_backend_info(self, vlc_backend):
        """Test backend name and version."""
        assert vlc_backend.get_backend_name() == "VLC"
        assert "3.0" in vlc_backend.get_backend_version()


class TestQtBackendAdapter:
    """Test Qt backend adapter."""

    @pytest.fixture
    def qt_backend(self):
        """Create Qt backend adapter."""
        from services.media.qt_backend import QtBackendAdapter
        from services.media.backend import PlaybackState, MediaStatus

        backend = QtBackendAdapter()
        backend._test_PS = PlaybackState
        backend._test_MS = MediaStatus
        return backend

    def test_initialization(self, qt_backend):
        """Test Qt backend initializes correctly."""
        PS = qt_backend._test_PS
        MS = qt_backend._test_MS

        assert qt_backend.get_playback_state() == PS.STOPPED
        assert qt_backend.get_media_status() == MS.NO_MEDIA

    def test_volume_control(self, qt_backend):
        """Test volume control."""
        qt_backend.set_volume(80)
        assert abs(qt_backend._audio_output.volume() - 0.8) < 0.01

    def test_backend_detection(self, qt_backend):
        """Test Qt backend detection."""
        backend_name = qt_backend.get_backend_name()
        assert "Qt/" in backend_name


class TestProtocolCompliance:
    """Test backend protocol compliance."""

    def test_vlc_backend_has_required_methods(self):
        """Test VLC backend implements protocol."""
        from services.media.vlc_backend import VlcBackendAdapter

        required = [
            "load",
            "unload",
            "play",
            "pause",
            "stop",
            "seek",
            "get_position",
            "get_duration",
            "is_playing",
            "set_volume",
            "get_volume",
        ]

        for method in required:
            assert hasattr(VlcBackendAdapter, method)

    def test_qt_backend_has_required_methods(self):
        """Test Qt backend implements protocol."""
        from services.media.qt_backend import QtBackendAdapter

        required = [
            "load",
            "unload",
            "play",
            "pause",
            "stop",
            "seek",
            "get_position",
            "get_duration",
            "is_playing",
            "set_volume",
            "get_volume",
        ]

        for method in required:
            assert hasattr(QtBackendAdapter, method)
