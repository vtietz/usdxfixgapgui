"""
Tests for MenuBar UI interactions and action call-throughs.

Validates that MenuBar buttons correctly invoke Actions methods and
update enabled/disabled state based on song selection.
"""
import pytest
import sys
import os
from unittest.mock import Mock, patch, MagicMock
from PySide6.QtWidgets import QApplication

# Ensure Qt application exists for widget tests
@pytest.fixture(scope="module", autouse=True)
def qapp():
    """Provide QApplication instance for Qt widget tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


@pytest.fixture
def mock_actions():
    """Mock Actions object with all methods used by MenuBar."""
    actions = Mock()
    actions.detect_gap = Mock()
    actions.reload_song = Mock()
    actions.normalize_song = Mock()
    actions.open_folder = Mock()
    actions.open_usdx = Mock()
    actions.set_directory = Mock()
    actions.delete_selected_song = Mock()
    
    # Mock data attribute with songs model
    actions.data = Mock()
    actions.data.songs = Mock()
    actions.data.songs.filter = []
    actions.data.songs.filter_text = ""
    actions.data.selected_songs_changed = Mock()
    actions.data.selected_songs_changed.connect = Mock()
    
    return actions


@pytest.fixture
def mock_app_data(tmp_path):
    """Mock AppData with config and songs model."""
    data = Mock()
    data.directory = str(tmp_path)
    data.config = Mock()
    data.config.last_directory = str(tmp_path)
    data.config.config_path = str(tmp_path / "config.ini")
    data.songs = Mock()
    data.songs.filter = []
    data.selected_songs_changed = Mock()
    data.selected_songs_changed.connect = Mock()
    return data


@pytest.fixture
def menu_bar(mock_actions, mock_app_data):
    """Create MenuBar instance with mocked dependencies."""
    from ui.menu_bar import MenuBar
    return MenuBar(mock_actions, mock_app_data)


@pytest.fixture
def song_with_audio(song_factory, tmp_path):
    """Create a song with audio_file set."""
    audio_path = tmp_path / "test.mp3"
    audio_path.touch()
    return song_factory(audio_file=str(audio_path))


@pytest.fixture
def song_with_usdb_id(song_factory):
    """Create a song with valid usdb_id."""
    song = song_factory(title="USDB Song")
    song.usdb_id = "12345"
    return song


class TestDetectButton:
    """Test Detect button behavior and call-through to Actions."""
    
    def test_detect_button_calls_actions_detect_gap_with_overwrite_true(
        self, menu_bar, mock_actions, song_with_audio
    ):
        """Detect button calls Actions.detect_gap(overwrite=True) when selected song has audio."""
        # Simulate selection
        menu_bar.onSelectedSongsChanged([song_with_audio])
        
        # Click Detect button
        menu_bar.detectButton.click()
        
        # Assert Actions.detect_gap called with overwrite=True
        mock_actions.detect_gap.assert_called_once_with(overwrite=True)
    
    def test_detect_button_enabled_when_selection_has_audio(
        self, menu_bar, song_with_audio
    ):
        """Detect button enabled when at least one selected song has audio_file."""
        menu_bar.onSelectedSongsChanged([song_with_audio])
        assert menu_bar.detectButton.isEnabled()
    
    def test_detect_button_disabled_when_no_selection(self, menu_bar):
        """Detect button disabled when no songs selected."""
        menu_bar.onSelectedSongsChanged([])
        assert not menu_bar.detectButton.isEnabled()
    
    def test_detect_button_disabled_when_selection_has_no_audio(
        self, menu_bar, song_factory
    ):
        """Detect button disabled when selected songs have no audio_file."""
        song_no_audio = song_factory(audio_file="")
        menu_bar.onSelectedSongsChanged([song_no_audio])
        assert not menu_bar.detectButton.isEnabled()


class TestReloadButton:
    """Test Reload button behavior."""
    
    def test_reload_button_calls_actions_reload_song(
        self, menu_bar, mock_actions, song_factory
    ):
        """Reload button calls Actions.reload_song."""
        song = song_factory()
        menu_bar.onSelectedSongsChanged([song])
        
        menu_bar.reload_button.click()
        
        mock_actions.reload_song.assert_called_once()
    
    def test_reload_button_enabled_when_songs_selected(
        self, menu_bar, song_factory
    ):
        """Reload button enabled when songs are selected."""
        song = song_factory()
        menu_bar.onSelectedSongsChanged([song])
        assert menu_bar.reload_button.isEnabled()
    
    def test_reload_button_disabled_when_no_selection(self, menu_bar):
        """Reload button disabled when no songs selected."""
        menu_bar.onSelectedSongsChanged([])
        assert not menu_bar.reload_button.isEnabled()


class TestNormalizeButton:
    """Test Normalize button behavior."""
    
    def test_normalize_button_calls_actions_normalize_song(
        self, menu_bar, mock_actions, song_with_audio
    ):
        """Normalize button calls Actions.normalize_song."""
        menu_bar.onSelectedSongsChanged([song_with_audio])
        
        menu_bar.normalize_button.click()
        
        mock_actions.normalize_song.assert_called_once()
    
    def test_normalize_button_enabled_when_selection_has_audio(
        self, menu_bar, song_with_audio
    ):
        """Normalize button enabled when selected songs have audio_file."""
        menu_bar.onSelectedSongsChanged([song_with_audio])
        assert menu_bar.normalize_button.isEnabled()
    
    def test_normalize_button_disabled_when_no_audio(
        self, menu_bar, song_factory
    ):
        """Normalize button disabled when selected songs have no audio_file."""
        song_no_audio = song_factory(audio_file="")
        menu_bar.onSelectedSongsChanged([song_no_audio])
        assert not menu_bar.normalize_button.isEnabled()


class TestOpenFolderButton:
    """Test Open Folder button behavior."""
    
    def test_open_folder_button_calls_actions_open_folder(
        self, menu_bar, mock_actions, song_factory
    ):
        """Open Folder button calls Actions.open_folder."""
        song = song_factory()
        menu_bar.onSelectedSongsChanged([song])
        
        menu_bar.openFolderButton.click()
        
        mock_actions.open_folder.assert_called_once()
    
    def test_open_folder_button_enabled_when_songs_selected(
        self, menu_bar, song_factory
    ):
        """Open Folder button enabled when songs selected."""
        song = song_factory()
        menu_bar.onSelectedSongsChanged([song])
        assert menu_bar.openFolderButton.isEnabled()
    
    def test_open_folder_button_disabled_when_no_selection(self, menu_bar):
        """Open Folder button disabled when no songs selected."""
        menu_bar.onSelectedSongsChanged([])
        assert not menu_bar.openFolderButton.isEnabled()


class TestOpenUSDBButton:
    """Test Open in USDB button behavior."""
    
    def test_open_usdb_button_calls_actions_open_usdx(
        self, menu_bar, mock_actions, song_with_usdb_id
    ):
        """Open in USDB button calls Actions.open_usdx."""
        menu_bar.onSelectedSongsChanged([song_with_usdb_id])
        
        menu_bar.open_usdx_button.click()
        
        mock_actions.open_usdx.assert_called_once()
    
    def test_open_usdb_button_enabled_only_for_single_song_with_usdb_id(
        self, menu_bar, song_with_usdb_id
    ):
        """Open in USDB button enabled only when exactly one song with usdb_id selected."""
        menu_bar.onSelectedSongsChanged([song_with_usdb_id])
        assert menu_bar.open_usdx_button.isEnabled()
    
    def test_open_usdb_button_disabled_when_no_selection(self, menu_bar):
        """Open in USDB button disabled when no songs selected."""
        menu_bar.onSelectedSongsChanged([])
        assert not menu_bar.open_usdx_button.isEnabled()
    
    def test_open_usdb_button_disabled_when_multiple_songs_selected(
        self, menu_bar, song_with_usdb_id, song_factory
    ):
        """Open in USDB button disabled when multiple songs selected."""
        song2 = song_factory()
        song2.usdb_id = "67890"
        menu_bar.onSelectedSongsChanged([song_with_usdb_id, song2])
        assert not menu_bar.open_usdx_button.isEnabled()
    
    def test_open_usdb_button_disabled_when_song_has_no_usdb_id(
        self, menu_bar, song_factory
    ):
        """Open in USDB button disabled when song has no usdb_id."""
        song = song_factory()
        song.usdb_id = None
        menu_bar.onSelectedSongsChanged([song])
        assert not menu_bar.open_usdx_button.isEnabled()
    
    def test_open_usdb_button_disabled_when_song_has_empty_usdb_id(
        self, menu_bar, song_factory
    ):
        """Open in USDB button disabled when song has empty usdb_id."""
        song = song_factory()
        song.usdb_id = ""
        menu_bar.onSelectedSongsChanged([song])
        assert not menu_bar.open_usdx_button.isEnabled()
    
    def test_open_usdb_button_disabled_when_song_has_zero_usdb_id(
        self, menu_bar, song_factory
    ):
        """Open in USDB button disabled when song has '0' as usdb_id."""
        song = song_factory()
        song.usdb_id = "0"
        menu_bar.onSelectedSongsChanged([song])
        assert not menu_bar.open_usdx_button.isEnabled()


class TestDeleteButton:
    """Test Delete button behavior."""
    
    def test_delete_button_enabled_when_songs_selected(
        self, menu_bar, song_factory
    ):
        """Delete button enabled when songs selected."""
        song = song_factory()
        menu_bar.onSelectedSongsChanged([song])
        assert menu_bar.delete_button.isEnabled()
    
    def test_delete_button_disabled_when_no_selection(self, menu_bar):
        """Delete button disabled when no songs selected."""
        menu_bar.onSelectedSongsChanged([])
        assert not menu_bar.delete_button.isEnabled()
    
    @patch('ui.menu_bar.QMessageBox')
    def test_delete_button_shows_confirmation_and_calls_action_on_ok(
        self, mock_messagebox, menu_bar, mock_actions, song_factory
    ):
        """Delete button shows confirmation dialog and calls action on OK."""
        song = song_factory()
        menu_bar.onSelectedSongsChanged([song])
        
        # Mock QMessageBox to return OK
        mock_box = MagicMock()
        mock_box.exec.return_value = 1024  # QMessageBox.StandardButton.Ok
        mock_messagebox.return_value = mock_box
        mock_messagebox.StandardButton.Ok = 1024
        
        menu_bar.onDeleteButtonClicked()
        
        # Assert confirmation dialog was shown
        mock_box.exec.assert_called_once()
        
        # Assert delete action was called
        mock_actions.delete_selected_song.assert_called_once()
    
    @patch('ui.menu_bar.QMessageBox')
    def test_delete_button_does_not_call_action_on_cancel(
        self, mock_messagebox, menu_bar, mock_actions, song_factory
    ):
        """Delete button does not call action when user cancels."""
        song = song_factory()
        menu_bar.onSelectedSongsChanged([song])
        
        # Mock QMessageBox to return Cancel
        mock_box = MagicMock()
        mock_box.exec.return_value = 4194304  # QMessageBox.StandardButton.Cancel
        mock_messagebox.return_value = mock_box
        mock_messagebox.StandardButton.Ok = 1024
        
        menu_bar.onDeleteButtonClicked()
        
        # Assert delete action was NOT called
        mock_actions.delete_selected_song.assert_not_called()


class TestDirectorySelection:
    """Test directory selection and forwarding to Actions."""
    
    def test_on_directory_selected_calls_actions_set_directory(
        self, menu_bar, mock_actions, tmp_path
    ):
        """on_directory_selected forwards to Actions.set_directory."""
        test_dir = str(tmp_path / "test_songs")
        os.makedirs(test_dir, exist_ok=True)
        
        menu_bar.on_directory_selected(test_dir)
        
        mock_actions.set_directory.assert_called_once_with(test_dir)
    
    @patch('ui.menu_bar.QFileDialog.getExistingDirectory')
    def test_choose_directory_calls_on_directory_selected_when_user_selects(
        self, mock_dialog, menu_bar, mock_actions, tmp_path
    ):
        """choose_directory calls on_directory_selected when user selects directory."""
        test_dir = str(tmp_path / "selected_dir")
        os.makedirs(test_dir, exist_ok=True)
        mock_dialog.return_value = test_dir
        
        menu_bar.choose_directory()
        
        mock_actions.set_directory.assert_called_once_with(test_dir)
    
    @patch('ui.menu_bar.QFileDialog.getExistingDirectory')
    def test_choose_directory_does_nothing_when_user_cancels(
        self, mock_dialog, menu_bar, mock_actions
    ):
        """choose_directory does nothing when user cancels dialog."""
        mock_dialog.return_value = ""  # Empty string = canceled
        
        menu_bar.choose_directory()
        
        mock_actions.set_directory.assert_not_called()


class TestOpenConfigFile:
    """Test open_config_file cross-platform behavior."""
    
    @patch('ui.menu_bar.os.path.exists')
    @patch('ui.menu_bar.os.startfile')
    @patch('ui.menu_bar.sys.platform', 'win32')
    def test_open_config_file_windows_uses_startfile(
        self, mock_startfile, mock_exists, menu_bar, tmp_path
    ):
        """open_config_file uses os.startfile on Windows."""
        config_path = tmp_path / "config.ini"
        config_path.touch()
        menu_bar.config.config_path = str(config_path)
        mock_exists.return_value = True
        
        menu_bar.open_config_file()
        
        mock_startfile.assert_called_once_with(str(config_path))
    
    @patch('ui.menu_bar.os.path.exists')
    @patch('ui.menu_bar.subprocess.run')
    @patch('ui.menu_bar.sys.platform', 'darwin')
    def test_open_config_file_macos_uses_open_command(
        self, mock_run, mock_exists, menu_bar, tmp_path
    ):
        """open_config_file uses 'open' command on macOS."""
        config_path = tmp_path / "config.ini"
        config_path.touch()
        menu_bar.config.config_path = str(config_path)
        mock_exists.return_value = True
        
        menu_bar.open_config_file()
        
        mock_run.assert_called_once_with(['open', str(config_path)], check=True)
    
    @patch('ui.menu_bar.os.path.exists')
    @patch('ui.menu_bar.subprocess.run')
    @patch('ui.menu_bar.sys.platform', 'linux')
    def test_open_config_file_linux_uses_xdg_open(
        self, mock_run, mock_exists, menu_bar, tmp_path
    ):
        """open_config_file uses 'xdg-open' command on Linux."""
        config_path = tmp_path / "config.ini"
        config_path.touch()
        menu_bar.config.config_path = str(config_path)
        mock_exists.return_value = True
        
        menu_bar.open_config_file()
        
        mock_run.assert_called_once_with(['xdg-open', str(config_path)], check=True)
    
    @patch('ui.menu_bar.os.path.exists')
    @patch('ui.menu_bar.QMessageBox.warning')
    def test_open_config_file_shows_warning_when_file_missing(
        self, mock_warning, mock_exists, menu_bar
    ):
        """open_config_file shows warning when config file doesn't exist."""
        mock_exists.return_value = False
        
        menu_bar.open_config_file()
        
        mock_warning.assert_called_once()
    
    @patch('ui.menu_bar.os.path.exists')
    @patch('ui.menu_bar.os.startfile')
    @patch('ui.menu_bar.QMessageBox.warning')
    @patch('ui.menu_bar.sys.platform', 'win32')
    def test_open_config_file_shows_warning_on_error(
        self, mock_warning, mock_startfile, mock_exists, menu_bar, tmp_path
    ):
        """open_config_file shows warning when opening fails."""
        config_path = tmp_path / "config.ini"
        config_path.touch()
        menu_bar.config.config_path = str(config_path)
        mock_exists.return_value = True
        mock_startfile.side_effect = OSError("Cannot open file")
        
        menu_bar.open_config_file()
        
        mock_warning.assert_called_once()


class TestButtonStateOnSelection:
    """Test comprehensive button state management based on selection."""
    
    def test_all_buttons_disabled_when_no_selection(self, menu_bar):
        """All action buttons disabled when no songs selected."""
        menu_bar.onSelectedSongsChanged([])
        
        assert not menu_bar.detectButton.isEnabled()
        assert not menu_bar.normalize_button.isEnabled()
        assert not menu_bar.openFolderButton.isEnabled()
        assert not menu_bar.open_usdx_button.isEnabled()
        assert not menu_bar.reload_button.isEnabled()
        assert not menu_bar.delete_button.isEnabled()
    
    def test_buttons_enabled_correctly_for_single_song_with_audio(
        self, menu_bar, song_with_audio
    ):
        """Buttons enabled correctly for single song with audio but no usdb_id."""
        song_with_audio.usdb_id = None
        menu_bar.onSelectedSongsChanged([song_with_audio])
        
        assert menu_bar.detectButton.isEnabled()
        assert menu_bar.normalize_button.isEnabled()
        assert menu_bar.openFolderButton.isEnabled()
        assert not menu_bar.open_usdx_button.isEnabled()  # No usdb_id
        assert menu_bar.reload_button.isEnabled()
        assert menu_bar.delete_button.isEnabled()
    
    def test_buttons_enabled_correctly_for_single_song_with_usdb_id(
        self, menu_bar, song_with_usdb_id, tmp_path
    ):
        """Buttons enabled correctly for single song with usdb_id and audio."""
        audio_path = tmp_path / "test.mp3"
        audio_path.touch()
        song_with_usdb_id.audio_file = str(audio_path)
        menu_bar.onSelectedSongsChanged([song_with_usdb_id])
        
        assert menu_bar.detectButton.isEnabled()
        assert menu_bar.normalize_button.isEnabled()
        assert menu_bar.openFolderButton.isEnabled()
        assert menu_bar.open_usdx_button.isEnabled()  # Has usdb_id
        assert menu_bar.reload_button.isEnabled()
        assert menu_bar.delete_button.isEnabled()
    
    def test_buttons_enabled_correctly_for_multiple_songs(
        self, menu_bar, song_with_audio, song_factory, tmp_path
    ):
        """Buttons enabled correctly for multiple songs selection."""
        song2_audio = tmp_path / "test2.mp3"
        song2_audio.touch()
        song2 = song_factory(audio_file=str(song2_audio))
        menu_bar.onSelectedSongsChanged([song_with_audio, song2])
        
        assert menu_bar.detectButton.isEnabled()
        assert menu_bar.normalize_button.isEnabled()
        assert menu_bar.openFolderButton.isEnabled()
        assert not menu_bar.open_usdx_button.isEnabled()  # Multiple songs
        assert menu_bar.reload_button.isEnabled()
        assert menu_bar.delete_button.isEnabled()
