"""Unit tests for separate_audio wrapper function."""

import sys
import pytest
from unittest.mock import patch


from utils.separate import separate_audio


class TestSeparateAudio:
    """Unit tests for audio separation wrapper"""

    def test_skip_when_outputs_exist(self, tmp_path):
        """Test A: Skip separation when output files already exist"""
        # Setup: Create audio file and pre-existing output files
        audio_file = tmp_path / "test_song.mp3"
        audio_file.write_text("fake audio data")

        output_path = tmp_path / "output"
        song_basename = audio_file.stem  # "test_song"
        vocals_path = output_path / song_basename / "vocals.wav"
        accompaniment_path = output_path / song_basename / "accompaniment.wav"

        # Create pre-existing output files
        vocals_path.parent.mkdir(parents=True)
        vocals_path.write_text("fake vocals")
        accompaniment_path.write_text("fake accompaniment")

        # Mock run_cancellable_process to verify it's NOT called
        with patch('utils.separate.run_cancellable_process') as mock_process:
            # Action: Call separate_audio with overwrite=False
            result_vocals, result_accompaniment = separate_audio(
                audio_file=str(audio_file),
                duration=180,
                output_path=str(output_path),
                overvrite=False
            )

            # Assert: Returns existing paths without calling subprocess
            assert result_vocals == str(vocals_path)
            assert result_accompaniment == str(accompaniment_path)
            mock_process.assert_not_called()

    def test_invoke_spleeter_and_return_paths(self, tmp_path):
        """Test B: Invoke Spleeter command and return generated paths"""
        # Setup: Create audio file without pre-existing outputs
        audio_file = tmp_path / "test_song.mp3"
        audio_file.write_text("fake audio data")

        output_path = tmp_path / "output"
        song_basename = audio_file.stem
        vocals_path = output_path / song_basename / "vocals.wav"
        accompaniment_path = output_path / song_basename / "accompaniment.wav"

        # Mock run_cancellable_process to simulate successful separation
        def mock_process_success(command, check_cancellation=None):
            # Create the expected output files
            vocals_path.parent.mkdir(parents=True, exist_ok=True)
            vocals_path.write_text("generated vocals")
            accompaniment_path.write_text("generated accompaniment")
            return (0, "Success", "")  # returncode, stdout, stderr

        with patch('utils.separate.run_cancellable_process', side_effect=mock_process_success) as mock_process:
            # Action: Call separate_audio
            result_vocals, result_accompaniment = separate_audio(
                audio_file=str(audio_file),
                duration=180,
                output_path=str(output_path),
                overvrite=False
            )

            # Assert: Returns expected paths
            assert result_vocals == str(vocals_path)
            assert result_accompaniment == str(accompaniment_path)

            # Assert: Subprocess was called once
            mock_process.assert_called_once()

            # Assert: Command structure is correct
            call_args = mock_process.call_args[0][0]  # First positional arg
            assert call_args[0] == sys.executable
            assert call_args[1:3] == ["-m", "spleeter"]
            assert call_args[3] == "separate"
            assert "-o" in call_args
            assert str(output_path) in call_args
            assert "-p" in call_args
            assert "spleeter:2stems" in call_args
            assert "-d" in call_args
            assert "180" in call_args
            assert str(audio_file) in call_args

    def test_overwrite_flag_forces_separation(self, tmp_path):
        """Test: overwrite=True forces separation even when files exist"""
        # Setup: Create audio file and pre-existing output files
        audio_file = tmp_path / "test_song.mp3"
        audio_file.write_text("fake audio data")

        output_path = tmp_path / "output"
        song_basename = audio_file.stem
        vocals_path = output_path / song_basename / "vocals.wav"
        accompaniment_path = output_path / song_basename / "accompaniment.wav"

        # Create pre-existing output files
        vocals_path.parent.mkdir(parents=True)
        vocals_path.write_text("old vocals")
        accompaniment_path.write_text("old accompaniment")

        # Mock run_cancellable_process
        def mock_process_success(command, check_cancellation=None):
            vocals_path.write_text("new vocals")
            accompaniment_path.write_text("new accompaniment")
            return (0, "Success", "")

        with patch('utils.separate.run_cancellable_process', side_effect=mock_process_success) as mock_process:
            # Action: Call with overvrite=True (note the typo in the original code)
            result_vocals, result_accompaniment = separate_audio(
                audio_file=str(audio_file),
                duration=180,
                output_path=str(output_path),
                overvrite=True  # Forces re-separation
            )

            # Assert: Subprocess WAS called despite existing files
            mock_process.assert_called_once()
            assert vocals_path.read_text() == "new vocals"
            assert accompaniment_path.read_text() == "new accompaniment"

    def test_missing_audio_file_raises_exception(self, tmp_path):
        """Test: Missing audio file raises exception"""
        output_path = tmp_path / "output"

        with pytest.raises(Exception, match="Audio file not found"):
            separate_audio(
                audio_file="/nonexistent/file.mp3",
                duration=180,
                output_path=str(output_path),
                overvrite=False
            )

    def test_failed_separation_raises_exception(self, tmp_path):
        """Test: Failed separation (missing output files) raises exception"""
        audio_file = tmp_path / "test_song.mp3"
        audio_file.write_text("fake audio data")
        output_path = tmp_path / "output"

        # Mock run_cancellable_process to succeed but NOT create files
        with patch('utils.separate.run_cancellable_process', return_value=(0, "Success", "")):
            with pytest.raises(Exception, match="Failed to separate audio"):
                separate_audio(
                    audio_file=str(audio_file),
                    duration=180,
                    output_path=str(output_path),
                    overvrite=False
                )
