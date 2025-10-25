"""
Tests for TabStrip component.
"""

import pytest
from unittest.mock import Mock
from PySide6.QtWidgets import QApplication
from ui.components.tab_strip import TabStrip, AudioSourceTab


@pytest.fixture(scope="session")
def qapp():
    """Create QApplication instance for Qt tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def tab_strip(qapp):
    """Create TabStrip widget."""
    return TabStrip()


def test_tab_strip_initialization(tab_strip):
    """Test TabStrip initializes with Original selected."""
    assert tab_strip.get_current_source() == AudioSourceTab.ORIGINAL
    assert tab_strip.original_btn.isChecked()
    assert not tab_strip.extracted_btn.isChecked()
    assert not tab_strip.both_btn.isChecked()


def test_extracted_disabled_by_default(tab_strip):
    """Test Extracted tab is disabled by default."""
    assert not tab_strip.extracted_btn.isEnabled()


def test_both_disabled(tab_strip):
    """Test Both tab is disabled (future feature)."""
    assert not tab_strip.both_btn.isEnabled()


def test_click_original_emits_signal(tab_strip):
    """Test clicking Original emits source_changed."""
    callback = Mock()
    tab_strip.source_changed.connect(callback)

    # Switch to extracted first, then back to original
    tab_strip.set_extracted_enabled(True)
    tab_strip.extracted_btn.click()
    callback.reset_mock()

    tab_strip.original_btn.click()

    callback.assert_called_once_with(AudioSourceTab.ORIGINAL)
    assert tab_strip.get_current_source() == AudioSourceTab.ORIGINAL


def test_click_extracted_when_enabled(tab_strip):
    """Test clicking Extracted when enabled."""
    tab_strip.set_extracted_enabled(True)

    callback = Mock()
    tab_strip.source_changed.connect(callback)

    tab_strip.extracted_btn.click()

    callback.assert_called_once_with(AudioSourceTab.EXTRACTED)
    assert tab_strip.get_current_source() == AudioSourceTab.EXTRACTED
    assert tab_strip.extracted_btn.isChecked()


def test_click_extracted_when_disabled_does_nothing(tab_strip):
    """Test clicking disabled Extracted does nothing."""
    callback = Mock()
    tab_strip.source_changed.connect(callback)

    # Extracted is disabled by default
    tab_strip.extracted_btn.click()

    callback.assert_not_called()
    assert tab_strip.get_current_source() == AudioSourceTab.ORIGINAL


def test_set_extracted_enabled(tab_strip):
    """Test enabling extracted tab."""
    assert not tab_strip.extracted_btn.isEnabled()

    tab_strip.set_extracted_enabled(True)

    assert tab_strip.extracted_btn.isEnabled()


def test_set_extracted_disabled_falls_back_to_original(tab_strip):
    """Test disabling extracted falls back to original if active."""
    tab_strip.set_extracted_enabled(True)
    tab_strip.extracted_btn.click()
    assert tab_strip.get_current_source() == AudioSourceTab.EXTRACTED

    callback = Mock()
    tab_strip.source_changed.connect(callback)

    # Disable extracted
    tab_strip.set_extracted_enabled(False)

    # Should fall back to original
    assert tab_strip.get_current_source() == AudioSourceTab.ORIGINAL
    assert tab_strip.original_btn.isChecked()
    callback.assert_called_once_with(AudioSourceTab.ORIGINAL)


def test_set_current_source_programmatically(tab_strip):
    """Test setting source programmatically."""
    tab_strip.set_extracted_enabled(True)

    tab_strip.set_current_source(AudioSourceTab.EXTRACTED)

    assert tab_strip.get_current_source() == AudioSourceTab.EXTRACTED
    assert tab_strip.extracted_btn.isChecked()


def test_set_current_source_same_does_nothing(tab_strip):
    """Test setting same source doesn't trigger change."""
    callback = Mock()
    tab_strip.source_changed.connect(callback)

    tab_strip.set_current_source(AudioSourceTab.ORIGINAL)

    # No signal emitted (already original)
    callback.assert_not_called()


def test_set_current_source_extracted_when_disabled_ignored(tab_strip):
    """Test setting extracted source when disabled is ignored."""
    # Extracted is disabled by default
    current = tab_strip.get_current_source()

    tab_strip.set_current_source(AudioSourceTab.EXTRACTED)

    # Should remain unchanged
    assert tab_strip.get_current_source() == current


def test_clicking_same_tab_doesnt_emit_signal(tab_strip):
    """Test clicking already-selected tab doesn't emit signal."""
    callback = Mock()
    tab_strip.source_changed.connect(callback)

    # Original is already selected
    tab_strip.original_btn.click()

    callback.assert_not_called()


def test_mutual_exclusivity(tab_strip):
    """Test only one tab can be checked at a time."""
    tab_strip.set_extracted_enabled(True)

    assert tab_strip.original_btn.isChecked()

    tab_strip.extracted_btn.click()

    assert tab_strip.extracted_btn.isChecked()
    assert not tab_strip.original_btn.isChecked()

    tab_strip.original_btn.click()

    assert tab_strip.original_btn.isChecked()
    assert not tab_strip.extracted_btn.isChecked()


def test_button_group_setup(tab_strip):
    """Test button group is configured correctly."""
    assert tab_strip.button_group.exclusive()
    assert len(tab_strip.button_group.buttons()) == 3
