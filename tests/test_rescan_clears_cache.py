"""Test that re-scan functionality clears cache properly"""

import pytest
from unittest.mock import Mock, patch
from actions.core_actions import CoreActions


@pytest.fixture
def mock_app_data(tmp_path):
    """Mock AppData with directory set"""
    data = Mock()
    data.directory = str(tmp_path)  # Use real temp directory
    data.tmp_path = str(tmp_path / "tmp")
    data.is_loading_songs = False
    data.config = Mock()
    data.config.last_directory = ""
    data.config.default_directory = ""
    data.config.save = Mock()
    data.songs = Mock()
    data.songs.clear = Mock()
    data.worker_queue = Mock()
    data.worker_queue.add_task = Mock()
    return data


@pytest.fixture
def core_actions(mock_app_data):
    """CoreActions instance with mocked dependencies"""
    return CoreActions(data=mock_app_data)


class TestRescanDirectory:
    """Tests for rescan_directory functionality"""

    @patch("actions.core_actions.clear_cache")
    def test_rescan_clears_cache(self, mock_clear_cache, core_actions, mock_app_data):
        """rescan_directory should clear cache before reloading"""
        core_actions.rescan_directory()

        # Verify cache was cleared
        mock_clear_cache.assert_called_once()

        # Verify songs were cleared
        mock_app_data.songs.clear.assert_called_once()

        # Verify worker was queued to reload songs
        mock_app_data.worker_queue.add_task.assert_called_once()

    @patch("actions.core_actions.clear_cache")
    def test_rescan_without_directory_logs_error(self, mock_clear_cache, core_actions, mock_app_data):
        """rescan_directory with no directory should not clear cache or reload"""
        mock_app_data.directory = ""

        core_actions.rescan_directory()

        # Should not clear cache or songs
        mock_clear_cache.assert_not_called()
        mock_app_data.songs.clear.assert_not_called()
        mock_app_data.worker_queue.add_task.assert_not_called()

    @patch("actions.core_actions.clear_cache")
    def test_set_directory_does_not_clear_cache(self, mock_clear_cache, core_actions, mock_app_data, tmp_path):
        """set_directory should NOT clear cache (different from rescan)"""
        new_dir = tmp_path / "songs"
        new_dir.mkdir()

        core_actions.set_directory(str(new_dir))

        # Should not clear cache
        mock_clear_cache.assert_not_called()

        # But should still clear songs and reload
        mock_app_data.songs.clear.assert_called_once()
        mock_app_data.worker_queue.add_task.assert_called_once()
