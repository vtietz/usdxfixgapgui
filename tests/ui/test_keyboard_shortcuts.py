"""
Tests for KeyboardShortcuts handler.
"""

import pytest
from unittest.mock import Mock
from PySide6.QtWidgets import QApplication
from ui.components.keyboard_shortcuts import KeyboardShortcuts


@pytest.fixture(scope="session")
def qapp():
    """Create QApplication instance for Qt tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def shortcuts(qapp):
    """Create KeyboardShortcuts handler."""
    return KeyboardShortcuts()


def test_shortcuts_initialization(shortcuts):
    """Test KeyboardShortcuts initializes enabled."""
    assert shortcuts.is_enabled()


def test_space_emits_play_pause(shortcuts):
    """Test Space key emits play_pause_requested."""
    callback = Mock()
    shortcuts.play_pause_requested.connect(callback)

    # Trigger shortcut directly
    shortcuts._shortcuts[0].activated.emit()

    callback.assert_called_once()


def test_g_emits_jump_to_current(shortcuts):
    """Test G key emits jump_to_current_requested."""
    callback = Mock()
    shortcuts.jump_to_current_requested.connect(callback)

    # Trigger shortcut directly
    shortcuts._shortcuts[1].activated.emit()

    callback.assert_called_once()


def test_d_emits_jump_to_detected(shortcuts):
    """Test D key emits jump_to_detected_requested."""
    callback = Mock()
    shortcuts.jump_to_detected_requested.connect(callback)

    # Trigger shortcut directly
    shortcuts._shortcuts[2].activated.emit()

    callback.assert_called_once()


def test_a_emits_apply_detected(shortcuts):
    """Test A key emits apply_detected_requested."""
    callback = Mock()
    shortcuts.apply_detected_requested.connect(callback)

    # Trigger shortcut directly
    shortcuts._shortcuts[3].activated.emit()

    callback.assert_called_once()


def test_r_emits_revert(shortcuts):
    """Test R key emits revert_requested."""
    callback = Mock()
    shortcuts.revert_requested.connect(callback)

    # Trigger shortcut directly
    shortcuts._shortcuts[4].activated.emit()

    callback.assert_called_once()


def test_s_emits_save(shortcuts):
    """Test S key emits save_requested."""
    callback = Mock()
    shortcuts.save_requested.connect(callback)

    # Trigger shortcut directly
    shortcuts._shortcuts[5].activated.emit()

    callback.assert_called_once()


def test_set_enabled_false_disables_shortcuts(shortcuts):
    """Test disabling shortcuts prevents emission."""
    callback = Mock()
    shortcuts.play_pause_requested.connect(callback)

    shortcuts.set_enabled(False)
    shortcuts._shortcuts[0].activated.emit()

    callback.assert_not_called()
    assert not shortcuts.is_enabled()


def test_set_enabled_true_reenables_shortcuts(shortcuts):
    """Test re-enabling shortcuts allows emission."""
    callback = Mock()
    shortcuts.play_pause_requested.connect(callback)

    shortcuts.set_enabled(False)
    shortcuts.set_enabled(True)
    shortcuts._shortcuts[0].activated.emit()

    callback.assert_called_once()
    assert shortcuts.is_enabled()


def test_all_shortcuts_disabled_together(shortcuts):
    """Test disabling affects all shortcuts."""
    callbacks = {"space": Mock(), "g": Mock(), "d": Mock(), "a": Mock(), "r": Mock(), "s": Mock()}

    shortcuts.play_pause_requested.connect(callbacks["space"])
    shortcuts.jump_to_current_requested.connect(callbacks["g"])
    shortcuts.jump_to_detected_requested.connect(callbacks["d"])
    shortcuts.apply_detected_requested.connect(callbacks["a"])
    shortcuts.revert_requested.connect(callbacks["r"])
    shortcuts.save_requested.connect(callbacks["s"])

    shortcuts.set_enabled(False)

    # Trigger all shortcuts
    for shortcut in shortcuts._shortcuts:
        shortcut.activated.emit()

    for callback in callbacks.values():
        callback.assert_not_called()


def test_shortcuts_count(shortcuts):
    """Test correct number of shortcuts registered."""
    assert len(shortcuts._shortcuts) == 6


def test_shortcut_sequences(shortcuts):
    """Test shortcuts have correct key sequences."""
    assert shortcuts._shortcuts[0].key().toString() == "Space"
    assert shortcuts._shortcuts[1].key().toString() == "G"
    assert shortcuts._shortcuts[2].key().toString() == "D"
    assert shortcuts._shortcuts[3].key().toString() == "A"
    assert shortcuts._shortcuts[4].key().toString() == "R"
    assert shortcuts._shortcuts[5].key().toString() == "S"
