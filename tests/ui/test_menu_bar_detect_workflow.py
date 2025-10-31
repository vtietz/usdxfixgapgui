"""
Integration-light test for MenuBar Detect workflow.

Validates that clicking Detect button triggers Actions.detect_gap.
Relies on existing orchestration tests for downstream gap detection logic.
"""

import pytest
import sys
from unittest.mock import Mock
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module", autouse=True)
def qapp():
    """Provide QApplication instance for Qt widget tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


@pytest.fixture
def mock_actions():
    """Mock Actions with detect_gap method."""
    actions = Mock()
    actions.detect_gap = Mock()
    actions.data = Mock()
    actions.data.songs = Mock()
    actions.data.songs.filter = []
    actions.data.selected_songs_changed = Mock()
    actions.data.selected_songs_changed.connect = Mock()
    return actions


@pytest.fixture
def mock_app_data(tmp_path):
    """Mock AppData for MenuBar."""
    data = Mock()
    data.directory = str(tmp_path)
    data.config = Mock()
    data.config.last_directory = str(tmp_path)
    data.config.config_path = str(tmp_path / "config.ini")
    data.songs = Mock()
    data.selected_songs_changed = Mock()
    data.selected_songs_changed.connect = Mock()
    return data


@pytest.fixture
def menu_bar(mock_actions, mock_app_data):
    """Create MenuBar with mocked dependencies."""
    from ui.menu_bar import MenuBar

    return MenuBar(mock_actions, mock_app_data)


@pytest.fixture
def songs_with_audio(song_factory, tmp_path):
    """Create multiple songs with audio files."""
    songs = []
    for i in range(3):
        audio_path = tmp_path / f"song{i}.mp3"
        audio_path.touch()
        song = song_factory(title=f"Song {i}", audio_file=str(audio_path))
        songs.append(song)
    return songs


class TestDetectWorkflowFromGUI:
    """Test detect workflow triggered from MenuBar."""

    def test_detect_button_click_triggers_actions_detect_gap(self, menu_bar, mock_actions, songs_with_audio):
        """Clicking Detect button calls Actions.detect_gap(overwrite=True)."""
        # Set up selection
        menu_bar.onSelectedSongsChanged(songs_with_audio)

        # Click Detect button
        menu_bar.detectButton.click()

        # Verify Actions.detect_gap was called
        mock_actions.detect_gap.assert_called_once_with(overwrite=True)

    def test_detect_workflow_not_triggered_without_audio(self, menu_bar, mock_actions, song_factory):
        """Detect button disabled when songs have no audio_file."""
        song_no_audio = song_factory(audio_file="")
        menu_bar.onSelectedSongsChanged([song_no_audio])

        # Verify button is disabled
        assert not menu_bar.detectButton.isEnabled()

        # Attempting to click should do nothing
        menu_bar.detectButton.click()
        mock_actions.detect_gap.assert_not_called()

    def test_detect_workflow_enabled_for_mixed_selection(self, menu_bar, mock_actions, songs_with_audio, song_factory):
        """Detect enabled when at least one song has audio_file."""
        song_no_audio = song_factory(audio_file="")
        mixed_selection = songs_with_audio + [song_no_audio]

        menu_bar.onSelectedSongsChanged(mixed_selection)

        # Verify button is enabled (at least one has audio)
        assert menu_bar.detectButton.isEnabled()

        # Click should trigger detect
        menu_bar.detectButton.click()
        mock_actions.detect_gap.assert_called_once_with(overwrite=True)

    def test_detect_workflow_with_single_song(self, menu_bar, mock_actions, songs_with_audio):
        """Detect works with single song selection."""
        menu_bar.onSelectedSongsChanged([songs_with_audio[0]])

        menu_bar.detectButton.click()

        mock_actions.detect_gap.assert_called_once_with(overwrite=True)

    def test_detect_workflow_with_no_selection(self, menu_bar, mock_actions):
        """Detect button disabled with no selection."""
        menu_bar.onSelectedSongsChanged([])

        assert not menu_bar.detectButton.isEnabled()

        menu_bar.detectButton.click()
        mock_actions.detect_gap.assert_not_called()


class TestDetectButtonStateTransitions:
    """Test Detect button state changes based on selection."""

    def test_detect_button_enables_when_valid_selection_set(self, menu_bar, songs_with_audio):
        """Detect button enables when selection changes to valid songs."""
        # Start with no selection
        menu_bar.onSelectedSongsChanged([])
        assert not menu_bar.detectButton.isEnabled()

        # Set valid selection
        menu_bar.onSelectedSongsChanged(songs_with_audio)
        assert menu_bar.detectButton.isEnabled()

    def test_detect_button_disables_when_selection_cleared(self, menu_bar, songs_with_audio):
        """Detect button disables when selection is cleared."""
        # Start with valid selection
        menu_bar.onSelectedSongsChanged(songs_with_audio)
        assert menu_bar.detectButton.isEnabled()

        # Clear selection
        menu_bar.onSelectedSongsChanged([])
        assert not menu_bar.detectButton.isEnabled()

    def test_detect_button_state_updated_on_each_selection_change(self, menu_bar, songs_with_audio, song_factory):
        """Detect button state updates correctly on multiple selection changes."""
        # Valid selection
        menu_bar.onSelectedSongsChanged(songs_with_audio)
        assert menu_bar.detectButton.isEnabled()

        # Invalid selection (no audio)
        song_no_audio = song_factory(audio_file="")
        menu_bar.onSelectedSongsChanged([song_no_audio])
        assert not menu_bar.detectButton.isEnabled()

        # Valid again
        menu_bar.onSelectedSongsChanged(songs_with_audio)
        assert menu_bar.detectButton.isEnabled()
