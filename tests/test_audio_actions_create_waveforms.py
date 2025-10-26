"""Integration-light tests for AudioActions._create_waveforms orchestration."""

import pytest
from unittest.mock import Mock, patch

from actions.audio_actions import AudioActions


class TestCreateWaveforms:
    """Integration-light tests for waveform creation orchestration"""

    def test_enqueues_two_tasks_when_audio_present_and_outputs_missing(self, app_data, song_factory, tmp_path):
        """Test A: Enqueues two CreateWaveform tasks when audio exists and waveforms don't"""
        # Setup: Create song with audio_file
        audio_file = tmp_path / "test_song.mp3"
        audio_file.write_text("fake audio")

        song = song_factory(
            title="Test Song",
            audio_file=str(audio_file),
            with_notes=True
        )

        # Mock WaveformPathService.get_paths to return paths
        mock_paths = {
            "audio_file": str(tmp_path / "audio.mp3"),
            "vocals_file": str(tmp_path / "vocals.wav"),
            "audio_waveform_file": str(tmp_path / "audio_waveform.png"),
            "vocals_waveform_file": str(tmp_path / "vocals_waveform.png")
        }

        # Create the audio files but NOT the waveform files
        (tmp_path / "audio.mp3").write_text("audio data")
        (tmp_path / "vocals.wav").write_text("vocals data")

        with patch('actions.audio_actions.WaveformPathService.get_paths', return_value=mock_paths), \
             patch('actions.audio_actions.CreateWaveform') as mock_waveform_class:

            # Track created workers
            created_workers = []

            def create_worker(*args, **kwargs):
                worker = Mock()
                worker.signals = Mock()
                worker.signals.error = Mock()
                worker.signals.error.connect = Mock()
                worker.signals.finished = Mock()
                worker.signals.finished.connect = Mock()
                created_workers.append(worker)
                return worker

            mock_waveform_class.side_effect = create_worker

            # Create AudioActions
            audio_actions = AudioActions(app_data)

            # Action: Call _create_waveforms
            audio_actions._create_waveforms(song, overwrite=True)

            # Assert: Two CreateWaveform tasks were created
            assert len(created_workers) == 2
            assert mock_waveform_class.call_count == 2

            # Assert: Two tasks were queued
            assert app_data.worker_queue.add_task.call_count == 2

            # Assert: Both workers were queued
            for worker in created_workers:
                app_data.worker_queue.add_task.assert_any_call(worker, True)

    def test_missing_audio_triggers_reload(self, app_data, song_factory):
        """Test B: Missing audio file should return early without reload (to avoid infinite loops)"""
        # Setup: Song without audio_file
        song = song_factory(title="No Audio", audio_file="", with_notes=True)

        # Create AudioActions
        audio_actions = AudioActions(app_data)

        # Action: Call _create_waveforms
        audio_actions._create_waveforms(song, overwrite=False)

        # Assert: No tasks were queued (function returns early)
        app_data.worker_queue.add_task.assert_not_called()

    def test_nonexistent_audio_file_triggers_reload(self, app_data, song_factory):
        """Test: Audio file path exists in song but file doesn't exist on disk"""
        # Setup: Song with audio_file path that doesn't exist
        song = song_factory(
            title="Missing File",
            audio_file="/nonexistent/path/audio.mp3",
            with_notes=True
        )

        mock_paths = {
            "audio_file": "/nonexistent/path/audio.mp3",
            "vocals_file": "/nonexistent/path/vocals.wav",
            "audio_waveform_file": "/path/to/audio_waveform.png",
            "vocals_waveform_file": "/path/to/vocals_waveform.png"
        }

        with patch('actions.audio_actions.WaveformPathService.get_paths', return_value=mock_paths), \
             patch('actions.audio_actions.SongActions') as mock_song_actions_class, \
             patch('actions.audio_actions.CreateWaveform'):

            mock_song_actions = Mock()
            mock_song_actions_class.return_value = mock_song_actions

            audio_actions = AudioActions(app_data)

            # Action: Call _create_waveforms
            # The audio files don't exist, so _create_waveform will skip them
            audio_actions._create_waveforms(song, overwrite=False)

            # Assert: No tasks queued (audio files don't exist)
            app_data.worker_queue.add_task.assert_not_called()

    def test_existing_waveforms_not_overwritten_when_overwrite_false(self, app_data, song_factory, tmp_path):
        """Test: Existing waveform files are skipped when overwrite=False"""
        # Setup: Create all files including waveforms
        audio_file = tmp_path / "audio.mp3"
        audio_file.write_text("audio data")
        vocals_file = tmp_path / "vocals.wav"
        vocals_file.write_text("vocals data")
        audio_waveform = tmp_path / "audio_waveform.png"
        audio_waveform.write_text("existing waveform")
        vocals_waveform = tmp_path / "vocals_waveform.png"
        vocals_waveform.write_text("existing waveform")

        song = song_factory(
            title="Has Waveforms",
            audio_file=str(audio_file),
            with_notes=True
        )

        mock_paths = {
            "audio_file": str(audio_file),
            "vocals_file": str(vocals_file),
            "audio_waveform_file": str(audio_waveform),
            "vocals_waveform_file": str(vocals_waveform)
        }

        with patch('actions.audio_actions.WaveformPathService.get_paths', return_value=mock_paths), \
             patch('actions.audio_actions.CreateWaveform') as mock_waveform_class:

            audio_actions = AudioActions(app_data)

            # Action: Call with overwrite=False
            audio_actions._create_waveforms(song, overwrite=False)

            # Assert: No tasks created (waveforms already exist)
            mock_waveform_class.assert_not_called()
            app_data.worker_queue.add_task.assert_not_called()

    def test_no_song_raises_exception(self, app_data):
        """Test: Passing None as song raises exception"""
        audio_actions = AudioActions(app_data)

        with pytest.raises(Exception, match="No song given"):
            audio_actions._create_waveforms(None)