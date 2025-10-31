import os
from model.song import Song
from utils import files


class WaveformPathService:
    """Service for managing waveform file paths"""

    @staticmethod
    def get_paths(song: Song, tmp_root: str | None = None):
        """
        Get all waveform-related paths for a song

        Args:
            song: The song object
            tmp_root: Optional tmp_root directory (if not using song's tmp_root)

        Returns:
            Dictionary containing all relevant paths
        """
        if not song or not song.audio_file:
            return None

        tmp_path = files.get_tmp_path(tmp_root, song.audio_file)

        return {
            "tmp_path": tmp_path,
            "audio_file": song.audio_file,
            "vocals_file": files.get_vocals_path(tmp_path),
            "audio_waveform_file": files.get_waveform_path(tmp_path, "audio"),
            "vocals_waveform_file": files.get_waveform_path(tmp_path, "vocals"),
        }

    @staticmethod
    def get_audio_waveform_path(song: Song, tmp_root: str | None = None):
        """Get the audio waveform file path for a song"""
        paths = WaveformPathService.get_paths(song, tmp_root)
        return paths["audio_waveform_file"] if paths else None

    @staticmethod
    def get_vocals_waveform_path(song: Song, tmp_root: str | None = None):
        """Get the vocals waveform file path for a song"""
        paths = WaveformPathService.get_paths(song, tmp_root)
        return paths["vocals_waveform_file"] if paths else None

    @staticmethod
    def get_vocals_file_path(song: Song, tmp_root: str | None = None):
        """Get the vocals file path for a song"""
        paths = WaveformPathService.get_paths(song, tmp_root)
        return paths["vocals_file"] if paths else None

    @staticmethod
    def waveforms_exists(song: Song, tmp_root: str | None = None):
        """Check if waveforms exist for a song"""
        # First check if the song has an audio file before proceeding
        if not song or not hasattr(song, "audio_file") or not song.audio_file:
            return False

        paths = WaveformPathService.get_paths(song, tmp_root)
        if not paths:
            return False

        audio_waveform_exists = os.path.exists(paths["audio_waveform_file"])

        return audio_waveform_exists
