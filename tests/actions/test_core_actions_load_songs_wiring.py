"""
Tests for CoreActions song loading wiring.

Validates worker queue integration, signal handling, and batch loading behavior.
"""

import pytest
from unittest.mock import Mock, patch
from PySide6.QtCore import QObject, Signal
from actions.core_actions import CoreActions
from model.song import Song, SongStatus


class MockLoadWorkerSignals(QObject):
    """Mock signals for LoadUsdxFilesWorker."""

    songLoaded = Signal(Song)
    songsLoadedBatch = Signal(list)
    finished = Signal()
    error = Signal(str)


@pytest.fixture
def mock_app_data(tmp_path):
    """Mock AppData with full setup for load testing."""
    data = Mock()
    data.directory = str(tmp_path / "songs")
    data.tmp_path = tmp_path
    data.is_loading_songs = False

    data.config = Mock()
    data.songs = Mock()
    data.songs.clear = Mock()
    data.songs.add = Mock()
    data.songs.add_batch = Mock()

    data.worker_queue = Mock()
    data.worker_queue.add_task = Mock()

    return data


@pytest.fixture
def mock_worker():
    """Mock LoadUsdxFilesWorker with signals."""
    worker = Mock()
    worker.signals = MockLoadWorkerSignals()
    return worker


@pytest.fixture
def core_actions(mock_app_data):
    """Create CoreActions instance."""
    return CoreActions(mock_app_data)


class TestLoadSongsWorkerEnqueue:
    """Test _load_songs worker queue integration."""

    @patch("actions.core_actions.LoadUsdxFilesWorker")
    def test_load_songs_creates_worker_with_correct_params(
        self, mock_worker_class, core_actions, mock_app_data, tmp_path
    ):
        """_load_songs creates LoadUsdxFilesWorker with directory and tmp_path."""
        test_dir = tmp_path / "songs"
        test_dir.mkdir()
        mock_app_data.directory = str(test_dir)

        mock_worker = Mock()
        mock_worker.signals = MockLoadWorkerSignals()
        mock_worker_class.return_value = mock_worker

        core_actions._load_songs()

        mock_worker_class.assert_called_once_with(str(test_dir), tmp_path, mock_app_data.config)

    @patch("actions.core_actions.LoadUsdxFilesWorker")
    def test_load_songs_enqueues_worker_with_start_now_true(self, mock_worker_class, core_actions, mock_app_data):
        """_load_songs enqueues worker with start_now=True."""
        mock_worker = Mock()
        mock_worker.signals = MockLoadWorkerSignals()
        mock_worker_class.return_value = mock_worker

        core_actions._load_songs()

        mock_app_data.worker_queue.add_task.assert_called_once_with(mock_worker, True)

    @patch("actions.core_actions.LoadUsdxFilesWorker")
    def test_load_songs_connects_signals(self, mock_worker_class, core_actions):
        """_load_songs connects all worker signals to handlers."""
        mock_worker = Mock()
        mock_signals = Mock()
        mock_signals.songLoaded = Mock()
        mock_signals.songsLoadedBatch = Mock()
        mock_signals.error = Mock()
        mock_signals.finished = Mock()
        mock_worker.signals = mock_signals
        mock_worker_class.return_value = mock_worker

        core_actions._load_songs()

        # Verify signal connections by checking connect was called
        mock_signals.songLoaded.connect.assert_called_once()
        mock_signals.songsLoadedBatch.connect.assert_called_once()
        mock_signals.error.connect.assert_called_once()
        mock_signals.finished.connect.assert_called_once()


class TestSongsBatchLoadedHandler:
    """Test _on_songs_batch_loaded signal handler."""

    def test_batch_loaded_sets_original_gap_for_not_processed_songs(self, core_actions, mock_app_data, song_factory):
        """_on_songs_batch_loaded sets original_gap for NOT_PROCESSED songs."""
        song1 = song_factory(gap=1000)
        song2 = song_factory(gap=2000)
        song1.status = SongStatus.NOT_PROCESSED
        song2.status = SongStatus.NOT_PROCESSED
        songs = [song1, song2]

        core_actions._on_songs_batch_loaded(songs)

        assert song1.gap_info.original_gap == 1000
        assert song2.gap_info.original_gap == 2000

    def test_batch_loaded_skips_original_gap_for_processed_songs(self, core_actions, song_factory):
        """_on_songs_batch_loaded skips original_gap for already processed songs."""
        song = song_factory(gap=1000)
        song.status = SongStatus.MATCH
        song.gap_info.original_gap = 500  # Already set

        core_actions._on_songs_batch_loaded([song])

        # Should not overwrite existing original_gap
        assert song.gap_info.original_gap == 500

    def test_batch_loaded_calls_songs_add_batch(self, core_actions, mock_app_data, song_factory):
        """_on_songs_batch_loaded uses add_batch for performance."""
        songs = [song_factory(), song_factory(), song_factory()]

        core_actions._on_songs_batch_loaded(songs)

        mock_app_data.songs.add_batch.assert_called_once_with(songs)

    def test_batch_loaded_handles_empty_list(self, core_actions, mock_app_data):
        """_on_songs_batch_loaded handles empty list gracefully."""
        core_actions._on_songs_batch_loaded([])

        mock_app_data.songs.add_batch.assert_called_once_with([])


class TestSongLoadedHandler:
    """Test _on_song_loaded signal handler."""

    def test_song_loaded_adds_song_to_collection(self, core_actions, mock_app_data, song_factory):
        """_on_song_loaded adds song to songs collection."""
        song = song_factory()

        core_actions._on_song_loaded(song)

        mock_app_data.songs.add.assert_called_once_with(song)

    def test_song_loaded_sets_original_gap_for_not_processed(self, core_actions, song_factory):
        """_on_song_loaded sets original_gap for NOT_PROCESSED songs."""
        song = song_factory(gap=1500)
        song.status = SongStatus.NOT_PROCESSED

        core_actions._on_song_loaded(song)

        assert song.gap_info.original_gap == 1500

    def test_song_loaded_does_not_set_original_gap_for_processed(self, core_actions, song_factory):
        """_on_song_loaded does not set original_gap for processed songs."""
        song = song_factory(gap=1500)
        song.status = SongStatus.MATCH
        song.gap_info.original_gap = 1000  # Already set

        core_actions._on_song_loaded(song)

        assert song.gap_info.original_gap == 1000


class TestLoadingFinishedHandler:
    """Test _on_loading_songs_finished signal handler."""

    def test_loading_finished_sets_is_loading_songs_false(self, core_actions, mock_app_data):
        """_on_loading_songs_finished sets is_loading_songs to False."""
        mock_app_data.is_loading_songs = True

        core_actions._on_loading_songs_finished()

        assert mock_app_data.is_loading_songs is False


class TestErrorHandler:
    """Test error signal handler."""

    @patch("actions.core_actions.logger")
    @patch("actions.core_actions.LoadUsdxFilesWorker")
    def test_error_handler_logs_error(self, mock_worker_class, mock_logger, core_actions):
        """Error signal handler logs errors."""
        mock_worker = Mock()
        mock_signals = Mock()
        mock_signals.songLoaded = Mock()
        mock_signals.songsLoadedBatch = Mock()
        mock_signals.error = Mock()
        mock_signals.finished = Mock()
        mock_worker.signals = mock_signals
        mock_worker_class.return_value = mock_worker

        # Trigger _load_songs to set up signal connections
        core_actions._load_songs()

        # Get the error handler callback
        error_callback = mock_signals.error.connect.call_args[0][0]

        # Simulate error
        test_error = "Failed to load file.txt"
        error_callback(test_error)

        # Verify logger was called
        mock_logger.error.assert_called_once()
        assert test_error in str(mock_logger.error.call_args)


class TestIntegratedSignalFlow:
    """Test integrated signal flow simulation."""

    @patch("actions.core_actions.LoadUsdxFilesWorker")
    def test_full_batch_load_flow(self, mock_worker_class, core_actions, mock_app_data, song_factory):
        """Simulate full batch load flow: enqueue → batch → finished."""
        # Setup mock worker
        mock_worker = Mock()
        mock_worker.signals = MockLoadWorkerSignals()
        mock_worker_class.return_value = mock_worker

        # Start load
        core_actions._load_songs()

        # Simulate batch loaded
        songs = [song_factory(gap=1000), song_factory(gap=2000)]
        for song in songs:
            song.status = SongStatus.NOT_PROCESSED

        mock_worker.signals.songsLoadedBatch.emit(songs)

        # Verify batch was processed
        assert songs[0].gap_info.original_gap == 1000
        assert songs[1].gap_info.original_gap == 2000
        mock_app_data.songs.add_batch.assert_called_once_with(songs)

        # Simulate finished
        mock_app_data.is_loading_songs = True
        mock_worker.signals.finished.emit()

        # Verify finished handler was called
        assert mock_app_data.is_loading_songs is False

    @patch("actions.core_actions.LoadUsdxFilesWorker")
    def test_individual_song_load_flow(self, mock_worker_class, core_actions, mock_app_data, song_factory):
        """Simulate individual song load flow for single file reload."""
        mock_worker = Mock()
        mock_worker.signals = MockLoadWorkerSignals()
        mock_worker_class.return_value = mock_worker

        core_actions._load_songs()

        # Simulate individual song loaded
        song = song_factory(gap=1500)
        song.status = SongStatus.NOT_PROCESSED
        mock_worker.signals.songLoaded.emit(song)

        # Verify song was added and original_gap set
        mock_app_data.songs.add.assert_called_once_with(song)
        assert song.gap_info.original_gap == 1500
