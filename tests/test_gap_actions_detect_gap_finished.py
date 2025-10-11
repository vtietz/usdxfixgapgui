"""Integration-light tests for GapActions._on_detect_gap_finished completion handler."""

import pytest
from unittest.mock import Mock, patch

from actions.gap_actions import GapActions
from model.gap_info import GapInfoStatus
from model.song import SongStatus
from test_utils.result_factory import create_match_result, create_mismatch_result


class TestDetectGapFinished:
    """Integration-light tests for gap detection completion handler"""
    
    def test_updates_gap_info_and_orchestrates_followups(self, app_data, song_factory, tmp_path):
        """Test: Updates gap_info fields and orchestrates waveforms/normalization"""
        # Setup: Create song with initial gap_info
        audio_file = tmp_path / "test_audio.mp3"
        audio_file.write_text("audio data")
        
        song = song_factory(
            title="Test Song",
            gap=1000,
            audio_file=str(audio_file),
            with_notes=True
        )
        
        # Create detection result with MATCH status
        result = create_match_result(
            song_file_path=song.txt_file,
            detected_gap=1000
        )
        result.notes_overlap = 50
        result.silence_periods = [(0, 500), (1000, 1500)]
        result.duration_ms = 180000
        
        # Enable auto_normalize in config
        app_data.config.auto_normalize = True
        
        with patch('actions.gap_actions.run_async') as mock_run_async, \
             patch('actions.gap_actions.GapInfoService') as mock_gap_service, \
             patch('actions.gap_actions.AudioActions') as mock_audio_actions_class:
            
            # Mock AudioActions instance
            mock_audio_actions = Mock()
            mock_audio_actions_class.return_value = mock_audio_actions
            
            # Create GapActions
            gap_actions = GapActions(app_data)
            
            # Action: Call _on_detect_gap_finished
            gap_actions._on_detect_gap_finished(song, result)
            
            # Assert: gap_info fields were updated
            assert song.gap_info.detected_gap == 1000
            assert song.gap_info.diff == 0
            assert song.gap_info.notes_overlap == 50
            assert song.gap_info.silence_periods == [(0, 500), (1000, 1500)]
            assert song.gap_info.duration == 180000
            assert song.gap_info.status == GapInfoStatus.MATCH
            
            # Assert: Song status was mapped via _gap_info_updated owner hook
            assert song.status == SongStatus.MATCH
            
            # Assert: GapInfoService.save was scheduled
            mock_run_async.assert_called_once()
            mock_gap_service.save.assert_called_once_with(song.gap_info)
            
            # Assert: _create_waveforms was invoked with overwrite=True
            mock_audio_actions._create_waveforms.assert_called_once_with(song, True)
            
            # Assert: _normalize_song was scheduled (auto_normalize=True)
            mock_audio_actions._normalize_song.assert_called_once_with(song, start_now=False)
            
            # Assert: songs.updated.emit was called
            app_data.songs.updated.emit.assert_called_once_with(song)
    
    def test_mismatch_status_mapped_correctly(self, app_data, song_factory):
        """Test: MISMATCH status is correctly mapped to song"""
        song = song_factory(title="Mismatch Song", gap=1000)
        
        # Create mismatch result
        result = create_mismatch_result(
            song_file_path=song.txt_file,
            detected_gap=1200,
            gap_diff=200
        )
        result.notes_overlap = 100
        result.silence_periods = []
        result.duration_ms = 150000
        
        with patch('actions.gap_actions.run_async'), \
             patch('actions.gap_actions.GapInfoService'), \
             patch('actions.gap_actions.AudioActions'):
            
            gap_actions = GapActions(app_data)
            gap_actions._on_detect_gap_finished(song, result)
            
            # Assert: Status mapping
            assert song.gap_info.status == GapInfoStatus.MISMATCH
            assert song.status == SongStatus.MISMATCH
            assert song.gap_info.detected_gap == 1200
            assert song.gap_info.diff == 200
    
    def test_no_normalization_when_auto_normalize_disabled(self, app_data, song_factory, tmp_path):
        """Test: Normalization is NOT scheduled when auto_normalize=False"""
        audio_file = tmp_path / "audio.mp3"
        audio_file.write_text("audio")
        
        song = song_factory(title="No Norm", audio_file=str(audio_file))
        result = create_match_result(song.txt_file)
        
        # Disable auto_normalize
        app_data.config.auto_normalize = False
        
        with patch('actions.gap_actions.run_async'), \
             patch('actions.gap_actions.GapInfoService'), \
             patch('actions.gap_actions.AudioActions') as mock_audio_class:
            
            mock_audio = Mock()
            mock_audio_class.return_value = mock_audio
            
            gap_actions = GapActions(app_data)
            gap_actions._on_detect_gap_finished(song, result)
            
            # Assert: Waveforms created
            mock_audio._create_waveforms.assert_called_once()
            
            # Assert: Normalization NOT called
            mock_audio._normalize_song.assert_not_called()
    
    def test_no_normalization_when_no_audio_file(self, app_data, song_factory):
        """Test: Normalization skipped when song has no audio_file"""
        song = song_factory(title="No Audio", audio_file="")
        result = create_match_result(song.txt_file)
        
        # Enable auto_normalize but song has no audio
        app_data.config.auto_normalize = True
        
        with patch('actions.gap_actions.run_async'), \
             patch('actions.gap_actions.GapInfoService'), \
             patch('actions.gap_actions.AudioActions') as mock_audio_class:
            
            mock_audio = Mock()
            mock_audio_class.return_value = mock_audio
            
            gap_actions = GapActions(app_data)
            gap_actions._on_detect_gap_finished(song, result)
            
            # Assert: Normalization NOT called (no audio_file)
            mock_audio._normalize_song.assert_not_called()
    
    def test_early_return_on_file_path_mismatch(self, app_data, song_factory):
        """Test: Returns early when result.song_file_path doesn't match song.txt_file"""
        song = song_factory(title="Song A", txt_file="/path/to/songA.txt")
        result = create_match_result(song_file_path="/path/to/songB.txt")
        
        with patch('actions.gap_actions.run_async') as mock_run_async, \
             patch('actions.gap_actions.AudioActions') as mock_audio_class:
            
            gap_actions = GapActions(app_data)
            gap_actions._on_detect_gap_finished(song, result)
            
            # Assert: No processing occurred
            mock_run_async.assert_not_called()
            mock_audio_class.assert_not_called()
            app_data.songs.updated.emit.assert_not_called()
            
            # Assert: gap_info was NOT modified
            # (gap_info should still have default/initial values)
            assert song.gap_info.detected_gap is None or song.gap_info.detected_gap == 0
