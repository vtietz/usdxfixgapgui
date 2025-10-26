"""
Tests for CoreActions directory management.

Validates directory setting, config persistence, and auto-load behavior.
"""
import pytest
import os
from unittest.mock import Mock, patch, call
from actions.core_actions import CoreActions


@pytest.fixture
def mock_app_data(tmp_path):
    """Mock AppData with config, songs, and worker_queue."""
    data = Mock()
    data.directory = ""
    data.tmp_path = tmp_path
    data.is_loading_songs = False

    # Config mock
    data.config = Mock()
    data.config.last_directory = ""
    data.config.save = Mock()

    # Songs model mock
    data.songs = Mock()
    data.songs.clear = Mock()
    data.songs.add = Mock()
    data.songs.add_batch = Mock()

    # Worker queue mock
    data.worker_queue = Mock()
    data.worker_queue.add_task = Mock()

    return data


@pytest.fixture
def core_actions(mock_app_data):
    """Create CoreActions instance with mocked dependencies."""
    return CoreActions(mock_app_data)


class TestSetDirectory:
    """Test set_directory validation and state management."""

    def test_set_directory_valid_path_sets_data_directory(
        self, core_actions, mock_app_data, tmp_path
    ):
        """set_directory with valid path sets data.directory."""
        test_dir = tmp_path / "valid_songs"
        test_dir.mkdir()

        core_actions.set_directory(str(test_dir))

        assert mock_app_data.directory == str(test_dir)

    def test_set_directory_persists_to_config(
        self, core_actions, mock_app_data, tmp_path
    ):
        """set_directory persists directory to config.last_directory."""
        test_dir = tmp_path / "valid_songs"
        test_dir.mkdir()

        core_actions.set_directory(str(test_dir))

        assert mock_app_data.config.last_directory == str(test_dir)
        mock_app_data.config.save.assert_called_once()

    @patch('actions.core_actions.CoreActions._load_songs')
    @patch('actions.core_actions.CoreActions._clear_songs')
    def test_set_directory_clears_and_loads_songs(
        self, mock_clear, mock_load, core_actions, tmp_path
    ):
        """set_directory clears existing songs and triggers load."""
        test_dir = tmp_path / "valid_songs"
        test_dir.mkdir()

        core_actions.set_directory(str(test_dir))

        mock_clear.assert_called_once()
        mock_load.assert_called_once()

    def test_set_directory_invalid_path_returns_early(
        self, core_actions, mock_app_data
    ):
        """set_directory with invalid path returns early without changes."""
        original_directory = mock_app_data.directory

        core_actions.set_directory("/nonexistent/path")

        # Assert no state changes
        assert mock_app_data.directory == original_directory
        mock_app_data.config.save.assert_not_called()
        mock_app_data.songs.clear.assert_not_called()

    def test_set_directory_empty_string_returns_early(
        self, core_actions, mock_app_data
    ):
        """set_directory with empty string returns early."""
        original_directory = mock_app_data.directory

        core_actions.set_directory("")

        assert mock_app_data.directory == original_directory
        mock_app_data.config.save.assert_not_called()

    def test_set_directory_none_returns_early(
        self, core_actions, mock_app_data
    ):
        """set_directory with None returns early."""
        original_directory = mock_app_data.directory

        core_actions.set_directory(None)

        assert mock_app_data.directory == original_directory
        mock_app_data.config.save.assert_not_called()


class TestAutoLoadLastDirectory:
    """Test auto_load_last_directory behavior."""

    @patch('actions.core_actions.CoreActions._load_songs')
    @patch('actions.core_actions.CoreActions._clear_songs')
    def test_auto_load_valid_directory_returns_true_and_loads(
        self, mock_clear, mock_load, core_actions, mock_app_data, tmp_path
    ):
        """auto_load_last_directory with valid path returns True and triggers load."""
        test_dir = tmp_path / "last_songs"
        test_dir.mkdir()
        mock_app_data.config.last_directory = str(test_dir)

        result = core_actions.auto_load_last_directory()

        assert result is True
        assert mock_app_data.directory == str(test_dir)
        mock_clear.assert_called_once()
        mock_load.assert_called_once()

    def test_auto_load_invalid_directory_returns_false(
        self, core_actions, mock_app_data
    ):
        """auto_load_last_directory with invalid path returns False without loading."""
        mock_app_data.config.last_directory = "/nonexistent/path"

        result = core_actions.auto_load_last_directory()

        assert result is False
        mock_app_data.songs.clear.assert_not_called()

    def test_auto_load_empty_directory_returns_false(
        self, core_actions, mock_app_data
    ):
        """auto_load_last_directory with empty config returns False."""
        mock_app_data.config.last_directory = ""

        result = core_actions.auto_load_last_directory()

        assert result is False
        mock_app_data.songs.clear.assert_not_called()

    def test_auto_load_none_directory_returns_false(
        self, core_actions, mock_app_data
    ):
        """auto_load_last_directory with None config returns False."""
        mock_app_data.config.last_directory = None

        result = core_actions.auto_load_last_directory()

        assert result is False
        mock_app_data.songs.clear.assert_not_called()

    @patch('actions.core_actions.CoreActions._load_songs')
    @patch('actions.core_actions.CoreActions._clear_songs')
    def test_auto_load_sets_data_directory_before_loading(
        self, mock_clear, mock_load, core_actions, mock_app_data, tmp_path
    ):
        """auto_load_last_directory sets data.directory before loading songs."""
        test_dir = tmp_path / "last_songs"
        test_dir.mkdir()
        mock_app_data.config.last_directory = str(test_dir)

        core_actions.auto_load_last_directory()

        # Verify directory was set before _load_songs was called
        assert mock_app_data.directory == str(test_dir)
        # Verify call order: clear, then load
        assert mock_clear.call_count == 1
        assert mock_load.call_count == 1


class TestClearSongs:
    """Test _clear_songs functionality."""

    def test_clear_songs_calls_songs_clear(
        self, core_actions, mock_app_data
    ):
        """_clear_songs calls data.songs.clear()."""
        core_actions._clear_songs()

        mock_app_data.songs.clear.assert_called_once()