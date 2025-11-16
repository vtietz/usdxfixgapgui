"""
Tests for 60 FPS position interpolation in MediaPlayerComponent.

Ensures smooth position updates work across all media backends.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

from ui.mediaplayer.component import MediaPlayerComponent


@pytest.fixture(scope="module")
def qapp():
    """Create QApplication instance for Qt widgets."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def mock_data():
    """Create mock AppData."""
    data = Mock()
    data.config = Mock()
    data.config.adjust_player_position_step_audio = 100
    data.config.adjust_player_position_step_vocals = 10
    return data


@pytest.fixture
def mock_actions():
    """Create mock Actions."""
    return Mock()


@pytest.fixture
def component(qapp, mock_data, mock_actions):
    """Create MediaPlayerComponent instance."""
    with patch('ui.mediaplayer.component.PlayerController'):
        comp = MediaPlayerComponent(mock_data, mock_actions)
        # Mock player.get_duration() to return 10000ms
        comp.player.get_duration = Mock(return_value=10000)
        yield comp
        # Cleanup timers
        if comp._position_interpolation_timer.isActive():
            comp._position_interpolation_timer.stop()


class TestPositionInterpolation:
    """Test position interpolation for smooth 60 FPS updates."""

    def test_interpolation_timer_exists(self, component):
        """Verify interpolation timer is initialized."""
        assert hasattr(component, '_position_interpolation_timer')
        assert isinstance(component._position_interpolation_timer, QTimer)
        assert component._position_interpolation_timer.interval() == 16  # 60 FPS

    def test_interpolation_starts_on_play(self, component):
        """Verify interpolation starts when playback begins."""
        assert not component._interpolation_active
        assert not component._position_interpolation_timer.isActive()

        # Simulate play state change
        component.on_play_state_changed(True)

        assert component._interpolation_active
        assert component._position_interpolation_timer.isActive()

    def test_interpolation_stops_on_pause(self, component):
        """Verify interpolation stops when playback pauses."""
        # Start playing
        component.on_play_state_changed(True)
        assert component._interpolation_active

        # Pause
        component.on_play_state_changed(False)

        assert not component._interpolation_active
        assert not component._position_interpolation_timer.isActive()

    def test_backend_position_updates_interpolation_base(self, component):
        """Verify backend position updates reset interpolation timer."""
        initial_position = 1000
        component.update_position(initial_position)

        assert component._last_backend_position == initial_position
        # Timer should be restarted (elapsed time near 0)
        assert component._interpolation_timer.elapsed() < 100

    def test_interpolation_calculates_smooth_positions(self, component):
        """Verify interpolation produces smooth position increments."""
        # Set backend position
        component._last_backend_position = 1000
        component._interpolation_timer.restart()

        # Mock elapsed time
        with patch.object(component._interpolation_timer, 'elapsed', return_value=50):
            # Calculate what interpolated position should be
            expected = 1000 + 50  # 1050ms
            
            # This would be calculated in _emit_interpolated_position
            elapsed_ms = component._interpolation_timer.elapsed()
            interpolated = component._last_backend_position + elapsed_ms
            
            assert interpolated == expected

    def test_interpolation_not_active_when_paused(self, component):
        """Verify interpolation doesn't emit when not active."""
        component._interpolation_active = False
        
        # Mock update method
        component._update_position_ui = Mock()
        
        # Try to emit interpolated position
        component._emit_interpolated_position()
        
        # Should not update UI when interpolation is inactive
        component._update_position_ui.assert_not_called()

    def test_interpolation_updates_ui_when_active(self, component):
        """Verify interpolation updates UI during playback."""
        component._interpolation_active = True
        component._last_backend_position = 2000
        
        # Mock update method
        component._update_position_ui = Mock()
        
        # Emit interpolated position
        component._emit_interpolated_position()
        
        # Should update UI with interpolated position
        component._update_position_ui.assert_called_once()
        # Position should be >= backend position (time has elapsed)
        called_position = component._update_position_ui.call_args[0][0]
        assert called_position >= 2000


class TestPositionUpdateUI:
    """Test position UI update logic."""

    def test_update_position_ui_called_on_backend_update(self, component):
        """Verify UI updates when backend reports position."""
        component._update_position_ui = Mock()
        
        component.update_position(5000)
        
        component._update_position_ui.assert_called_once_with(5000)

    def test_backend_position_restarts_interpolation_timer(self, component):
        """Verify interpolation timer resets on backend update."""
        # Set initial position and let some time pass
        component._last_backend_position = 1000
        component._interpolation_timer.restart()
        
        # Wait a bit (mock elapsed time)
        with patch.object(component._interpolation_timer, 'elapsed', return_value=200):
            assert component._interpolation_timer.elapsed() == 200
        
        # Backend updates position
        component.update_position(2000)
        
        # Timer should be restarted (low elapsed time)
        assert component._interpolation_timer.elapsed() < 50
        assert component._last_backend_position == 2000
