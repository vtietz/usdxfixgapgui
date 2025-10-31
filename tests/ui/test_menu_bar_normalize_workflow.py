"""
Integration-light test for MenuBar Normalize workflow.

Validates that clicking Normalize button triggers Actions.normalize_song.
Relies on existing orchestration tests for downstream normalization logic.
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
    """Mock Actions with normalize_song method."""
    actions = Mock()
    actions.normalize_song = Mock()
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


class TestNormalizeWorkflowFromGUI:
    """Test normalize workflow triggered from MenuBar."""

    def test_normalize_button_click_triggers_actions_normalize_song(self, menu_bar, mock_actions, songs_with_audio):
        """Clicking Normalize button calls Actions.normalize_song()."""
        # Set up selection
        menu_bar.onSelectedSongsChanged(songs_with_audio)

        # Click Normalize button
        menu_bar.normalize_button.click()

        # Verify Actions.normalize_song was called
        mock_actions.normalize_song.assert_called_once()

    def test_normalize_workflow_not_triggered_without_audio(self, menu_bar, mock_actions, song_factory):
        """Normalize button disabled when songs have no audio_file."""
        song_no_audio = song_factory(audio_file="")
        menu_bar.onSelectedSongsChanged([song_no_audio])

        # Verify button is disabled
        assert not menu_bar.normalize_button.isEnabled()

        # Attempting to click should do nothing
        menu_bar.normalize_button.click()
        mock_actions.normalize_song.assert_not_called()

    def test_normalize_workflow_enabled_for_mixed_selection(
        self, menu_bar, mock_actions, songs_with_audio, song_factory
    ):
        """Normalize enabled when at least one song has audio_file."""
        song_no_audio = song_factory(audio_file="")
        mixed_selection = songs_with_audio + [song_no_audio]

        menu_bar.onSelectedSongsChanged(mixed_selection)

        # Verify button is enabled (at least one has audio)
        assert menu_bar.normalize_button.isEnabled()

        # Click should trigger normalize
        menu_bar.normalize_button.click()
        mock_actions.normalize_song.assert_called_once()

    def test_normalize_workflow_with_single_song(self, menu_bar, mock_actions, songs_with_audio):
        """Normalize works with single song selection."""
        menu_bar.onSelectedSongsChanged([songs_with_audio[0]])

        menu_bar.normalize_button.click()

        mock_actions.normalize_song.assert_called_once()

    def test_normalize_workflow_with_no_selection(self, menu_bar, mock_actions):
        """Normalize button disabled with no selection."""
        menu_bar.onSelectedSongsChanged([])

        assert not menu_bar.normalize_button.isEnabled()

        menu_bar.normalize_button.click()
        mock_actions.normalize_song.assert_not_called()


class TestNormalizeButtonStateTransitions:
    """Test Normalize button state changes based on selection."""

    def test_normalize_button_enables_when_valid_selection_set(self, menu_bar, songs_with_audio):
        """Normalize button enables when selection changes to valid songs."""
        # Start with no selection
        menu_bar.onSelectedSongsChanged([])
        assert not menu_bar.normalize_button.isEnabled()

        # Set valid selection
        menu_bar.onSelectedSongsChanged(songs_with_audio)
        assert menu_bar.normalize_button.isEnabled()

    def test_normalize_button_disables_when_selection_cleared(self, menu_bar, songs_with_audio):
        """Normalize button disables when selection is cleared."""
        # Start with valid selection
        menu_bar.onSelectedSongsChanged(songs_with_audio)
        assert menu_bar.normalize_button.isEnabled()

        # Clear selection
        menu_bar.onSelectedSongsChanged([])
        assert not menu_bar.normalize_button.isEnabled()

    def test_normalize_button_state_updated_on_each_selection_change(self, menu_bar, songs_with_audio, song_factory):
        """Normalize button state updates correctly on multiple selection changes."""
        # Valid selection
        menu_bar.onSelectedSongsChanged(songs_with_audio)
        assert menu_bar.normalize_button.isEnabled()

        # Invalid selection (no audio)
        song_no_audio = song_factory(audio_file="")
        menu_bar.onSelectedSongsChanged([song_no_audio])
        assert not menu_bar.normalize_button.isEnabled()

        # Valid again
        menu_bar.onSelectedSongsChanged(songs_with_audio)
        assert menu_bar.normalize_button.isEnabled()


class TestNormalizeAndDetectInteraction:
    """Test that Normalize and Detect buttons work independently."""

    def test_normalize_and_detect_both_enabled_with_audio(self, menu_bar, songs_with_audio):
        """Both Normalize and Detect enabled when songs have audio."""
        menu_bar.onSelectedSongsChanged(songs_with_audio)

        assert menu_bar.normalize_button.isEnabled()
        assert menu_bar.detectButton.isEnabled()

    def test_normalize_and_detect_both_disabled_without_audio(self, menu_bar, song_factory):
        """Both Normalize and Detect disabled when songs have no audio."""
        song_no_audio = song_factory(audio_file="")
        menu_bar.onSelectedSongsChanged([song_no_audio])

        assert not menu_bar.normalize_button.isEnabled()
        assert not menu_bar.detectButton.isEnabled()

    def test_can_click_normalize_and_detect_independently(self, menu_bar, mock_actions, songs_with_audio):
        """Can trigger Normalize and Detect independently."""
        menu_bar.onSelectedSongsChanged(songs_with_audio)

        # Click Normalize first
        menu_bar.normalize_button.click()
        mock_actions.normalize_song.assert_called_once()

        # Then click Detect
        menu_bar.detectButton.click()
        mock_actions.detect_gap.assert_called_once_with(overwrite=True)
