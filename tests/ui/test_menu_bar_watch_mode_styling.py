"""Tests for watch mode button visual feedback (orange styling and logging)."""

import pytest
from unittest.mock import Mock, patch
from PySide6.QtWidgets import QApplication

from ui.menu_bar import MenuBar
from actions import Actions
from app.app_data import AppData


@pytest.fixture
def app():
    """Create QApplication instance for tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def menu_bar(app):
    """Create MenuBar instance for testing."""
    data = AppData()
    actions = Actions(data)
    menu_bar = MenuBar(actions, data)
    return menu_bar


class TestWatchModeButtonStyling:
    """Tests for watch mode button visual feedback"""

    def test_button_turns_orange_when_enabled(self, menu_bar):
        """Test: Button gets orange background when watch mode is enabled"""
        # Initially no style
        assert menu_bar.watch_mode_button.styleSheet() == ""

        # Simulate watch mode enabled
        menu_bar.onWatchModeEnabledChanged(True)

        # Check button is checked
        assert menu_bar.watch_mode_button.isChecked()

        # Check button has orange styling
        style = menu_bar.watch_mode_button.styleSheet()
        assert "#FF8C00" in style  # Orange color
        assert "background-color" in style.lower()

    def test_button_returns_to_default_when_disabled(self, menu_bar):
        """Test: Button returns to default style when watch mode is disabled"""
        # First enable it (orange)
        menu_bar.onWatchModeEnabledChanged(True)
        assert "#FF8C00" in menu_bar.watch_mode_button.styleSheet()

        # Now disable it
        menu_bar.onWatchModeEnabledChanged(False)

        # Check button is unchecked
        assert not menu_bar.watch_mode_button.isChecked()

        # Check button style is reset to default (empty)
        assert menu_bar.watch_mode_button.styleSheet() == ""

    def test_toggle_logs_user_action(self, menu_bar, caplog):
        """Test: Toggling the button logs the user action"""
        import logging
        caplog.set_level(logging.INFO)

        # Mock the actions to prevent actual watch mode start
        with patch.object(menu_bar._actions, 'start_watch_mode', return_value=True):
            # Simulate user clicking to enable
            menu_bar.onWatchModeToggled(True)

            # Check log contains toggle message
            assert any(
                "User toggled watch mode button: ON" in record.message
                for record in caplog.records
            )

        caplog.clear()

        # Simulate user clicking to disable
        menu_bar.onWatchModeToggled(False)

        # Check log contains toggle message
        assert any(
            "User toggled watch mode button: OFF" in record.message
            for record in caplog.records
        )

    def test_enabled_state_logs_activation(self, menu_bar, caplog):
        """Test: Watch mode enabled state change logs activation message"""
        import logging
        caplog.set_level(logging.INFO)

        # Enable watch mode
        menu_bar.onWatchModeEnabledChanged(True)

        # Check log contains ENABLED message
        assert any(
            "Watch mode ENABLED - monitoring directory for changes" in record.message
            for record in caplog.records
        )

        caplog.clear()

        # Disable watch mode
        menu_bar.onWatchModeEnabledChanged(False)

        # Check log contains DISABLED message
        assert any(
            "Watch mode DISABLED - stopped monitoring directory" in record.message
            for record in caplog.records
        )

    def test_toggle_logs_start_attempt(self, menu_bar, caplog):
        """Test: Toggle logs when attempting to start watch mode"""
        import logging
        caplog.set_level(logging.INFO)

        with patch.object(menu_bar._actions, 'start_watch_mode', return_value=True):
            menu_bar.onWatchModeToggled(True)

            # Check log shows attempt to start
            assert any(
                "Attempting to start watch mode" in record.message
                for record in caplog.records
            )

    def test_toggle_logs_stop_attempt(self, menu_bar, caplog):
        """Test: Toggle logs when attempting to stop watch mode"""
        import logging
        caplog.set_level(logging.INFO)

        menu_bar.onWatchModeToggled(False)

        # Check log shows attempt to stop
        assert any(
            "Attempting to stop watch mode" in record.message
            for record in caplog.records
        )

    def test_failed_start_reverts_button_state(self, menu_bar):
        """Test: Failed start unchecks button and shows no orange styling"""
        # Mock failed start
        with patch.object(menu_bar._actions, 'start_watch_mode', return_value=False), \
             patch('ui.menu_bar.QMessageBox.warning'):  # Suppress warning dialog

            # Try to enable (will fail)
            menu_bar.onWatchModeToggled(True)

            # Button should be unchecked
            assert not menu_bar.watch_mode_button.isChecked()

            # No orange styling should be applied
            # (onWatchModeEnabledChanged is only called on success)
            assert menu_bar.watch_mode_button.styleSheet() == ""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])