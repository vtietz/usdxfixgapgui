import os
import sys
import pytest
from unittest.mock import Mock

# Ensure src directory is importable
PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
SRC_DIR = os.path.join(PROJECT_ROOT, 'src')
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

# Add tests directory to path for test utilities
TESTS_DIR = os.path.join(PROJECT_ROOT, 'tests')
if TESTS_DIR not in sys.path:
    sys.path.append(TESTS_DIR)

from model.song import Song
from model.gap_info import GapInfo
from test_utils.note_factory import create_basic_notes


@pytest.fixture
def app_data(tmp_path):
    """
    Create a mock AppData object with standard test configuration.
    
    Provides:
        - songs.updated.emit mock
        - worker_queue.add_task mock
        - config object with spleeter=True, auto_normalize=False
        - tmp_path attribute for filesystem operations
    """
    data = Mock()
    
    # Songs collection with signal mocks
    data.songs = Mock()
    data.songs.updated = Mock()
    data.songs.updated.emit = Mock()
    
    # Worker queue mock
    data.worker_queue = Mock()
    data.worker_queue.add_task = Mock()
    
    # Configuration
    data.config = Mock()
    data.config.spleeter = True
    data.config.auto_normalize = False
    
    # Filesystem access
    data.tmp_path = tmp_path
    
    return data


@pytest.fixture
def song_factory(tmp_path):
    """
    Factory fixture for creating Song objects with sensible defaults.
    
    Usage:
        song = song_factory(title="Test Song", gap=1000)
    
    Returns:
        A callable that creates Song objects
    """
    def _create_song(
        txt_file: str = None,
        title: str = "Test Song",
        artist: str = "Test Artist",
        gap: int = 1000,
        bpm: int = 120,
        is_relative: bool = False,
        audio_file: str = None,
        with_notes: bool = True
    ) -> Song:
        """
        Create a Song object with specified parameters.
        
        Args:
            txt_file: Path to .txt file (default: temp file in tmp_path)
            title: Song title
            artist: Artist name
            gap: Gap value in milliseconds
            bpm: Beats per minute
            is_relative: Whether timing is relative
            audio_file: Path to audio file (default: None)
            with_notes: Whether to populate notes (default: True)
        
        Returns:
            A Song object with gap_info and owner hook configured
        """
        if txt_file is None:
            txt_file = str(tmp_path / f"{title}.txt")
        
        song = Song(txt_file=txt_file)
        song.title = title
        song.artist = artist
        song.gap = gap
        song.bpm = bpm
        song.is_relative = is_relative
        song.audio_file = audio_file or ""
        
        # Attach gap_info with owner hook
        gap_info = GapInfo()
        song.gap_info = gap_info  # This triggers the owner hook setter
        
        # Add notes if requested
        if with_notes:
            song.notes = create_basic_notes()
        
        return song
    
    return _create_song
