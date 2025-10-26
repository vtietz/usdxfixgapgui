"""
Tests for BottomActionBar component.
"""

import pytest
from unittest.mock import Mock
from PySide6.QtWidgets import QApplication
from ui.components.bottom_action_bar import BottomActionBar


@pytest.fixture(scope="session")
def qapp():
    """Create QApplication instance for Qt tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def action_bar(qapp):
    """Create BottomActionBar widget."""
    return BottomActionBar()


def test_action_bar_initialization(action_bar):
    """Test BottomActionBar initializes with default state."""
    assert action_bar.gap_spinbox.value() == 0
    assert not action_bar.play_pause_btn.isChecked()
    assert action_bar.play_pause_btn.text() == "Play"


def test_apply_detected_disabled_by_default(action_bar):
    """Test Apply Detected button is disabled when no detection."""
    assert not action_bar.apply_detected_btn.isEnabled()


def test_revert_disabled_by_default(action_bar):
    """Test Revert button is disabled when not dirty."""
    assert not action_bar.revert_btn.isEnabled()


def test_save_disabled_by_default(action_bar):
    """Test Save button is disabled when not dirty."""
    assert not action_bar.save_btn.isEnabled()


def test_jump_detected_disabled_by_default(action_bar):
    """Test Jump to Detected button is disabled when no detection."""
    assert not action_bar.jump_detected_btn.isEnabled()


def test_set_current_gap(action_bar):
    """Test setting current gap value."""
    action_bar.set_current_gap(8125)

    assert action_bar.gap_spinbox.value() == 8125


def test_set_current_gap_doesnt_emit_signal(action_bar):
    """Test programmatic gap change doesn't emit signal."""
    callback = Mock()
    action_bar.current_gap_changed.connect(callback)

    action_bar.set_current_gap(5000)

    callback.assert_not_called()


def test_gap_spinbox_change_emits_signal(action_bar):
    """Test user changing spinbox emits signal."""
    callback = Mock()
    action_bar.current_gap_changed.connect(callback)

    action_bar.gap_spinbox.setValue(8125)

    callback.assert_called_once_with(8125)


def test_set_has_detected_gap_enables_buttons(action_bar):
    """Test setting detected gap availability enables buttons."""
    action_bar.set_has_detected_gap(True)

    assert action_bar.apply_detected_btn.isEnabled()
    assert action_bar.jump_detected_btn.isEnabled()


def test_set_has_detected_gap_false_disables_buttons(action_bar):
    """Test clearing detected gap disables buttons."""
    action_bar.set_has_detected_gap(True)
    action_bar.set_has_detected_gap(False)

    assert not action_bar.apply_detected_btn.isEnabled()
    assert not action_bar.jump_detected_btn.isEnabled()


def test_set_is_dirty_enables_buttons(action_bar):
    """Test setting dirty state enables save/revert buttons."""
    action_bar.set_is_dirty(True)

    assert action_bar.revert_btn.isEnabled()
    assert action_bar.save_btn.isEnabled()


def test_set_is_dirty_false_disables_buttons(action_bar):
    """Test clearing dirty state disables save/revert buttons."""
    action_bar.set_is_dirty(True)
    action_bar.set_is_dirty(False)

    assert not action_bar.revert_btn.isEnabled()
    assert not action_bar.save_btn.isEnabled()


def test_set_is_playing_updates_button(action_bar):
    """Test setting playing state updates play/pause button."""
    action_bar.set_is_playing(True)

    assert action_bar.play_pause_btn.isChecked()
    assert action_bar.play_pause_btn.text() == "Pause"


def test_set_is_playing_false_updates_button(action_bar):
    """Test clearing playing state updates play/pause button."""
    action_bar.set_is_playing(True)
    action_bar.set_is_playing(False)

    assert not action_bar.play_pause_btn.isChecked()
    assert action_bar.play_pause_btn.text() == "Play"


def test_apply_detected_clicked_emits_signal(action_bar):
    """Test clicking Apply Detected emits signal."""
    action_bar.set_has_detected_gap(True)  # Enable button

    callback = Mock()
    action_bar.apply_detected_clicked.connect(callback)

    action_bar.apply_detected_btn.click()

    callback.assert_called_once()


def test_revert_clicked_emits_signal(action_bar):
    """Test clicking Revert emits signal."""
    action_bar.set_is_dirty(True)  # Enable button

    callback = Mock()
    action_bar.revert_clicked.connect(callback)

    action_bar.revert_btn.click()

    callback.assert_called_once()


def test_play_pause_clicked_emits_signal(action_bar):
    """Test clicking Play/Pause emits signal."""
    callback = Mock()
    action_bar.play_pause_clicked.connect(callback)

    action_bar.play_pause_btn.click()

    callback.assert_called_once()


def test_jump_current_clicked_emits_signal(action_bar):
    """Test clicking Jump to Current emits signal."""
    callback = Mock()
    action_bar.jump_to_current_clicked.connect(callback)

    action_bar.jump_current_btn.click()

    callback.assert_called_once()


def test_jump_detected_clicked_emits_signal(action_bar):
    """Test clicking Jump to Detected emits signal."""
    action_bar.set_has_detected_gap(True)  # Enable button

    callback = Mock()
    action_bar.jump_to_detected_clicked.connect(callback)

    action_bar.jump_detected_btn.click()

    callback.assert_called_once()


def test_save_clicked_emits_signal(action_bar):
    """Test clicking Save emits signal."""
    action_bar.set_is_dirty(True)  # Enable button

    callback = Mock()
    action_bar.save_clicked.connect(callback)

    action_bar.save_btn.click()

    callback.assert_called_once()


def test_keep_original_clicked_emits_signal(action_bar):
    """Test clicking Keep Original emits signal."""
    callback = Mock()
    action_bar.keep_original_clicked.connect(callback)

    action_bar.keep_original_btn.click()

    callback.assert_called_once()


def test_tooltips_set(action_bar):
    """Test all buttons have tooltips with shortcuts."""
    assert "(A)" in action_bar.apply_detected_btn.toolTip()
    assert "(R)" in action_bar.revert_btn.toolTip()
    assert "(Space)" in action_bar.play_pause_btn.toolTip()
    assert "(G)" in action_bar.jump_current_btn.toolTip()
    assert "(D)" in action_bar.jump_detected_btn.toolTip()
    assert "(S)" in action_bar.save_btn.toolTip()