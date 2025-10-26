"""
Integration-light happy path smoke tests.

Validates high-level workflows from GUI interaction to action orchestration
without heavy Qt event simulation or OS dependencies.
"""
import pytest
import sys
import os
from unittest.mock import Mock, patch, MagicMock
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
    """Mock Actions object."""
    actions = Mock()
    actions.set_directory = Mock()
    actions.detect_gap = Mock()
    actions.reload_song = Mock()
    actions.normalize_song = Mock()
    actions.open_folder = Mock()
    actions.data = Mock()
    actions.data.songs = Mock()
    actions.data.songs.filter = []
    actions.data.selected_songs_changed = Mock()
    actions.data.selected_songs_changed.connect = Mock()
    return actions


@pytest.fixture
def mock_app_data(tmp_path):
    """Mock AppData."""
    data = Mock()
    data.directory = ""
    data.tmp_path = tmp_path
    data.config = Mock()
    data.config.last_directory = ""
    data.config.config_path = str(tmp_path / "config.ini")
    data.songs = Mock()
    data.selected_songs_changed = Mock()
    data.selected_songs_changed.connect = Mock()
    return data


@pytest.fixture
def menu_bar(mock_actions, mock_app_data):
    """Create MenuBar."""
    from ui.menu_bar import MenuBar
    return MenuBar(mock_actions, mock_app_data)


@pytest.fixture
def core_actions(mock_app_data):
    """Create CoreActions."""
    from actions.core_actions import CoreActions
    return CoreActions(mock_app_data)


@pytest.fixture
def songs_directory(tmp_path):
    """Create a test songs directory with some .txt files."""
    songs_dir = tmp_path / "test_songs"
    songs_dir.mkdir()

    # Create dummy song files
    (songs_dir / "song1.txt").write_text("#TITLE:Test Song 1\n#ARTIST:Test Artist\n#GAP:1000\n")
    (songs_dir / "song2.txt").write_text("#TITLE:Test Song 2\n#ARTIST:Test Artist\n#GAP:2000\n")

    return songs_dir


class TestDirectorySelectionToLoad:
    """Test directory selection workflow leading to song loading."""

    @patch('ui.menu_bar.QFileDialog.getExistingDirectory')
    def test_choose_directory_calls_set_directory_action(
        self, mock_dialog, menu_bar, mock_actions, songs_directory
    ):
        """Choosing directory via dialog calls Actions.set_directory."""
        mock_dialog.return_value = str(songs_directory)

        menu_bar.choose_directory()

        mock_actions.set_directory.assert_called_once_with(str(songs_directory))

    @patch('actions.core_actions.CoreActions._load_songs')
    @patch('actions.core_actions.CoreActions._clear_songs')
    def test_set_directory_triggers_clear_and_load(
        self, mock_clear, mock_load, core_actions, mock_app_data, songs_directory
    ):
        """CoreActions.set_directory clears songs and triggers load."""
        core_actions.set_directory(str(songs_directory))

        # Verify directory was set
        assert mock_app_data.directory == str(songs_directory)

        # Verify clear and load were called
        mock_clear.assert_called_once()
        mock_load.assert_called_once()

    @patch('actions.core_actions.LoadUsdxFilesWorker')
    def test_load_songs_enqueues_worker(
        self, mock_worker_class, core_actions, mock_app_data, songs_directory
    ):
        """_load_songs creates and enqueues LoadUsdxFilesWorker."""
        mock_worker = Mock()
        mock_worker.signals = Mock()
        mock_worker.signals.songLoaded = Mock()
        mock_worker.signals.songLoaded.connect = Mock()
        mock_worker.signals.songsLoadedBatch = Mock()
        mock_worker.signals.songsLoadedBatch.connect = Mock()
        mock_worker.signals.finished = Mock()
        mock_worker.signals.finished.connect = Mock()
        mock_worker.signals.error = Mock()
        mock_worker.signals.error.connect = Mock()
        mock_worker_class.return_value = mock_worker

        mock_app_data.directory = str(songs_directory)

        core_actions._load_songs()

        # Verify worker was created
        mock_worker_class.assert_called_once_with(
            str(songs_directory),
            mock_app_data.tmp_path
        )

        # Verify worker was enqueued
        mock_app_data.worker_queue.add_task.assert_called_once_with(
            mock_worker, True
        )


class TestLoadThenDetectWorkflow:
    """Test workflow: load songs → select → detect."""

    @patch('ui.menu_bar.QFileDialog.getExistingDirectory')
    def test_directory_load_then_detect_workflow(
        self, mock_dialog, menu_bar, mock_actions, songs_directory, song_factory, tmp_path
    ):
        """Complete workflow: choose directory → select songs → detect."""
        # Step 1: Choose directory
        mock_dialog.return_value = str(songs_directory)
        menu_bar.choose_directory()
        mock_actions.set_directory.assert_called_once_with(str(songs_directory))

        # Step 2: Simulate songs loaded and selected
        audio_path = tmp_path / "test.mp3"
        audio_path.touch()
        songs = [
            song_factory(title="Song 1", audio_file=str(audio_path)),
            song_factory(title="Song 2", audio_file=str(audio_path)),
        ]
        menu_bar.onSelectedSongsChanged(songs)

        # Verify Detect is enabled
        assert menu_bar.detectButton.isEnabled()

        # Step 3: Click Detect
        menu_bar.detectButton.click()

        # Verify detect_gap was called
        mock_actions.detect_gap.assert_called_once_with(overwrite=True)

    def test_select_songs_then_multiple_operations(
        self, menu_bar, mock_actions, song_factory, tmp_path
    ):
        """Test multiple operations on selected songs."""
        audio_path = tmp_path / "test.mp3"
        audio_path.touch()
        songs = [song_factory(audio_file=str(audio_path))]

        menu_bar.onSelectedSongsChanged(songs)

        # All buttons should be enabled
        assert menu_bar.detectButton.isEnabled()
        assert menu_bar.normalize_button.isEnabled()
        assert menu_bar.reload_button.isEnabled()
        assert menu_bar.openFolderButton.isEnabled()

        # Trigger detect
        menu_bar.detectButton.click()
        mock_actions.detect_gap.assert_called_once_with(overwrite=True)

        # Trigger normalize
        menu_bar.normalize_button.click()
        mock_actions.normalize_song.assert_called_once()

        # Trigger reload
        menu_bar.reload_button.click()
        mock_actions.reload_song.assert_called_once()

        # Trigger open folder
        menu_bar.openFolderButton.click()
        mock_actions.open_folder.assert_called_once()


class TestAutoLoadOnStartup:
    """Test auto-load from last directory on startup."""

    @patch('actions.core_actions.CoreActions._load_songs')
    @patch('actions.core_actions.CoreActions._clear_songs')
    def test_auto_load_last_directory_on_startup(
        self, mock_clear, mock_load, core_actions, mock_app_data, songs_directory
    ):
        """auto_load_last_directory loads songs from config.last_directory."""
        mock_app_data.config.last_directory = str(songs_directory)

        result = core_actions.auto_load_last_directory()

        assert result is True
        assert mock_app_data.directory == str(songs_directory)
        mock_clear.assert_called_once()
        mock_load.assert_called_once()

    def test_auto_load_skipped_when_no_last_directory(
        self, core_actions, mock_app_data
    ):
        """auto_load_last_directory returns False when no last directory."""
        mock_app_data.config.last_directory = ""

        result = core_actions.auto_load_last_directory()

        assert result is False
        mock_app_data.songs.clear.assert_not_called()


class TestButtonStateCascade:
    """Test button state updates cascade correctly through selection changes."""

    def test_button_states_update_through_multiple_selections(
        self, menu_bar, song_factory, tmp_path
    ):
        """Button states update correctly through selection lifecycle."""
        # No selection - all disabled
        menu_bar.onSelectedSongsChanged([])
        assert not menu_bar.detectButton.isEnabled()
        assert not menu_bar.normalize_button.isEnabled()

        # Add selection with audio - buttons enabled
        audio_path = tmp_path / "test.mp3"
        audio_path.touch()
        song_with_audio = song_factory(audio_file=str(audio_path))
        menu_bar.onSelectedSongsChanged([song_with_audio])
        assert menu_bar.detectButton.isEnabled()
        assert menu_bar.normalize_button.isEnabled()

        # Change to selection without audio - buttons disabled
        song_no_audio = song_factory(audio_file="")
        menu_bar.onSelectedSongsChanged([song_no_audio])
        assert not menu_bar.detectButton.isEnabled()
        assert not menu_bar.normalize_button.isEnabled()

        # Back to selection with audio - buttons enabled again
        menu_bar.onSelectedSongsChanged([song_with_audio])
        assert menu_bar.detectButton.isEnabled()
        assert menu_bar.normalize_button.isEnabled()


class TestDirectoryPersistence:
    """Test directory persistence to config."""

    def test_set_directory_persists_to_config(
        self, core_actions, mock_app_data, songs_directory
    ):
        """set_directory saves directory to config.last_directory."""
        core_actions.set_directory(str(songs_directory))

        assert mock_app_data.config.last_directory == str(songs_directory)
        mock_app_data.config.save.assert_called_once()

    @patch('actions.core_actions.CoreActions._load_songs')
    @patch('actions.core_actions.CoreActions._clear_songs')
    def test_auto_load_uses_persisted_directory(
        self, mock_clear, mock_load, core_actions, mock_app_data, songs_directory
    ):
        """auto_load_last_directory uses persisted directory from config."""
        # First set directory (persists to config)
        core_actions.set_directory(str(songs_directory))

        # Reset to simulate app restart
        mock_app_data.directory = ""
        mock_clear.reset_mock()
        mock_load.reset_mock()

        # Auto-load should use persisted directory
        result = core_actions.auto_load_last_directory()

        assert result is True
        assert mock_app_data.directory == str(songs_directory)
        mock_load.assert_called_once()