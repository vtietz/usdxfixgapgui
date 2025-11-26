"""Integration-light tests for AudioActions._create_waveforms orchestration."""

import pytest
from unittest.mock import Mock

from actions.audio_actions import AudioActions


class TestCreateWaveforms:
    """Integration-light tests for waveform creation orchestration"""

    def test_forwards_arguments_to_waveform_manager(self, app_data, song_factory):
        song = song_factory(title="Delegate", audio_file="/tmp/song.mp3", with_notes=True)
        callback = Mock()
        audio_actions = AudioActions(app_data)

        audio_actions._create_waveforms(
            song,
            overwrite=True,
            use_queue=False,
            emit_on_finish=False,
            finished_callback=callback,
        )

        app_data.waveform_manager.ensure_waveforms.assert_called_once_with(
            song,
            overwrite=True,
            use_queue=False,
            emit_on_finish=False,
            finished_callback=callback,
            requester="audio-actions",
        )

    def test_no_song_raises_exception(self, app_data):
        audio_actions = AudioActions(app_data)

        with pytest.raises(Exception, match="No song given"):
            audio_actions._create_waveforms(None)

        app_data.waveform_manager.ensure_waveforms.assert_not_called()

    def test_logs_warning_when_manager_missing(self, app_data, song_factory, monkeypatch):
        song = song_factory(title="Fallback", audio_file="/tmp/song.mp3", with_notes=True)
        app_data.waveform_manager = None

        warning_spy = Mock()
        monkeypatch.setattr("actions.audio_actions.logger.warning", warning_spy)

        audio_actions = AudioActions(app_data)
        audio_actions._create_waveforms(song)

        warning_spy.assert_called_once()
