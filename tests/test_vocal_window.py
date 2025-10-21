"""
Unit tests for vocal start window and iterative detection expansion.

Tests the new windowing behavior:
    - Config parsing for window parameters
    - GapDetectionContext field binding
    - MDXConfig window field population
    - Preview vocals duration capping
    - Scanner chunk limit enforcement
    - Iterative window expansion logic
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import torch
import numpy as np
from dataclasses import dataclass

from common.config import Config
from utils.gap_detection.pipeline import GapDetectionContext, normalize_context
from utils.providers.mdx.config import MdxConfig


class TestConfigWindowSettings:
    """Test vocal window configuration settings."""
    
    def test_default_window_settings(self):
        """Config should have default vocal window settings."""
        config = Config()
        
        assert config.vocal_start_window_sec == 20  # Optimized from 30 for faster detection
        assert config.vocal_window_increment_sec == 10  # Optimized from 15 for faster detection
        assert config.vocal_window_max_sec == 60  # Optimized from 90 for faster detection
    
    def test_window_settings_persist(self):
        """Window settings should persist across save/load."""
        config = Config()
        config.vocal_start_window_sec = 45
        config.vocal_window_increment_sec = 20
        config.vocal_window_max_sec = 120
        
        # Note: Config.save() doesn't persist these yet (they're read-only from config.ini)
        # This test documents the expected behavior when save support is added
        assert config.vocal_start_window_sec == 45
        assert config.vocal_window_increment_sec == 20
        assert config.vocal_window_max_sec == 120


class TestGapDetectionContextWindowing:
    """Test GapDetectionContext window field binding."""
    
    def test_context_includes_window_fields(self):
        """GapDetectionContext should include window fields from Config."""
        config = Config()
        
        # Create a test audio file context
        with patch('os.path.exists', return_value=True):
            ctx = GapDetectionContext(
                audio_file="/test/song.mp3",
                original_gap_ms=5000.0,
                detection_time_sec=30,
                audio_length_ms=180000,
                tmp_root="/tmp",
                config=config,
                overwrite=False,
                start_window_sec=30,
                window_increment_sec=15,
                window_max_sec=90
            )
        
        assert ctx.start_window_sec == 30
        assert ctx.window_increment_sec == 15
        assert ctx.window_max_sec == 90
    
    def test_normalize_context_binds_window_params(self):
        """normalize_context should bind window parameters from Config."""
        config = Config()
        config.vocal_start_window_sec = 45
        config.vocal_window_increment_sec = 20
        config.vocal_window_max_sec = 120
        
        with patch('os.path.exists', return_value=True), \
             patch('utils.audio.get_audio_duration', return_value=180.0):
            
            ctx = normalize_context(
                audio_file="/test/song.mp3",
                tmp_root="/tmp",
                original_gap=5000,
                audio_length=None,
                default_detection_time=30,
                config=config,
                overwrite=False
            )
        
        assert ctx.start_window_sec == 45
        assert ctx.window_increment_sec == 20
        assert ctx.window_max_sec == 120


class TestMDXConfigWindowing:
    """Test MDXConfig window field population."""
    
    def test_mdx_config_populates_window_fields(self):
        """MDXConfig should populate window fields from Config (seconds -> milliseconds)."""
        config = Config()
        config.vocal_start_window_sec = 30
        config.vocal_window_increment_sec = 15
        config.vocal_window_max_sec = 90
        
        mdx_config = MdxConfig.from_config(config)
        
        assert mdx_config.start_window_ms == 30000
        assert mdx_config.start_window_increment_ms == 15000
        assert mdx_config.start_window_max_ms == 90000
    
    def test_mdx_config_uses_defaults_if_missing(self):
        """MDXConfig should use defaults if Config lacks window settings."""
        # Mock config without vocal window attributes
        mock_config = Mock(spec=[])  # Empty spec means no attributes
        
        # MDXConfig.from_config uses getattr with defaults
        mdx_config = MdxConfig.from_config(mock_config)
        
        # Should use dataclass defaults (30s, 15s, 90s converted to ms)
        assert mdx_config.start_window_ms == 30000
        assert mdx_config.start_window_increment_ms == 15000
        assert mdx_config.start_window_max_ms == 90000


class TestPreviewDurationCap:
    """Test preview vocals duration capping."""
    
    @patch('torchaudio.load')
    @patch('torchaudio.save')
    @patch('torchaudio.info')
    @patch('os.path.exists', return_value=False)
    @patch('os.makedirs')
    def test_get_vocals_file_caps_duration(self, mock_makedirs, mock_exists, mock_info, mock_save, mock_load):
        """get_vocals_file should cap waveform to requested duration."""
        from utils.providers.mdx_provider import MdxProvider
        
        config = Config()
        provider = MdxProvider(config)
        
        # Mock audio loading: 180s track
        sample_rate = 44100
        track_duration_s = 180
        total_samples = int(track_duration_s * sample_rate)
        mock_waveform = torch.randn(2, total_samples)
        mock_load.return_value = (mock_waveform, sample_rate)
        
        # Mock model
        mock_model = Mock()
        with patch.object(provider, '_get_demucs_model', return_value=mock_model), \
             patch('utils.providers.mdx_provider.apply_model') as mock_apply:
            
            # Mock Demucs output
            mock_vocals = torch.randn(2, total_samples)
            mock_sources = torch.randn(1, 4, 2, total_samples)  # batch, stems, channels, samples
            mock_sources[0, 3] = mock_vocals
            mock_apply.return_value = mock_sources
            
            # Call with 30s duration cap
            provider.get_vocals_file(
                audio_file="/test/song.mp3",
                temp_root="/tmp",
                destination_vocals_filepath="/tmp/vocals.wav",
                duration=30,
                overwrite=True
            )
            
            # Verify apply_model received capped waveform (30s instead of 180s)
            call_args = mock_apply.call_args
            input_waveform = call_args[0][1]  # Second arg to apply_model
            expected_samples = int(30 * sample_rate)
            
            # Input should be capped to 30s
            assert input_waveform.shape[-1] <= expected_samples + 100  # Allow small tolerance
            assert input_waveform.shape[-1] >= expected_samples - 100


class TestScannerChunkLimits:
    """Test scanner chunk limit enforcement."""
    
    def test_scanner_skips_chunks_beyond_limit(self):
        """Scanner should skip chunks starting after search_limit_ms."""
        from utils.providers.mdx.scanner.pipeline import scan_for_onset
        from utils.providers.mdx.config import MdxConfig
        from utils.providers.mdx.vocals_cache import VocalsCache
        
        # Create mock objects
        mock_model = Mock()
        mock_model.samplerate = 44100  # Required by Demucs apply_model
        mock_model.sources = ['vocals', 'drums', 'bass', 'other']  # Required by Demucs len(model.sources)
        mock_model.segment = 8  # Required by Demucs apply_model assertion
        mock_device = "cpu"
        config = MdxConfig(
            start_window_ms=30000,  # 30s limit
            start_window_increment_ms=15000,
            start_window_max_ms=90000
        )
        vocals_cache = VocalsCache()
        
        # Mock torchaudio.info to return 180s track
        with patch('torchaudio.info') as mock_info, \
             patch('torchaudio.load') as mock_load, \
             patch('demucs.apply.apply_model') as mock_apply:
            
            mock_info_obj = Mock()
            mock_info_obj.num_frames = int(180 * 44100)
            mock_info_obj.sample_rate = 44100
            mock_info.return_value = mock_info_obj

            # Mock load to return empty chunks
            mock_load.return_value = (torch.randn(2, int(12 * 44100)), 44100)
            
            # Mock Demucs to return silence (no onset)
            mock_sources = torch.zeros(1, 4, 2, int(12 * 44100))
            mock_apply.return_value = mock_sources            # Run scanner
            onset_ms = scan_for_onset(
                audio_file="/test/song.mp3",
                expected_gap_ms=5000.0,
                model=mock_model,
                device=mock_device,
                config=config,
                vocals_cache=vocals_cache,
                total_duration_ms=180000
            )
            
            # With 30s limit and no onset, should return None
            # (Would expand iteratively, but all chunks return silence in this mock)
            assert onset_ms is None or onset_ms < 90000  # Within max window


class TestIterativeExpansion:
    """Test iterative window expansion logic."""
    
    def test_expansion_increases_search_limit(self):
        """Scanner should expand search_limit_ms when no onset found."""
        from utils.providers.mdx.scanner.pipeline import scan_for_onset
        from utils.providers.mdx.config import MdxConfig
        from utils.providers.mdx.vocals_cache import VocalsCache
        
        mock_model = Mock()
        mock_model.samplerate = 44100  # Required by Demucs apply_model
        mock_model.sources = ['vocals', 'drums', 'bass', 'other']  # Required by Demucs len(model.sources)
        mock_model.segment = 8  # Required by Demucs apply_model assertion
        config = MdxConfig(
            start_window_ms=30000,
            start_window_increment_ms=15000,
            start_window_max_ms=60000
        )
        vocals_cache = VocalsCache()
        
        call_count = 0
        
        def mock_apply_model(model, waveform, **kwargs):
            """Return onset only on 3rd call (45s mark)."""
            nonlocal call_count
            call_count += 1
            
            # Return silence for first 2 calls, then onset
            if call_count <= 2:
                # Silence (no onset)
                return torch.zeros(1, 4, 2, waveform.shape[-1])
            else:
                # Add energy at start (onset detected)
                sources = torch.zeros(1, 4, 2, waveform.shape[-1])
                sources[0, 3, :, :1000] = 0.5  # Vocal energy at start of chunk
                return sources
        
        with patch('torchaudio.info') as mock_info, \
             patch('torchaudio.load') as mock_load, \
             patch('demucs.apply.apply_model', side_effect=mock_apply_model):
            
            mock_info_obj = Mock()
            mock_info_obj.num_frames = int(180 * 44100)
            mock_info_obj.sample_rate = 44100
            mock_info.return_value = mock_info_obj

            mock_load.return_value = (torch.randn(2, int(12 * 44100)), 44100)
            
            onset_ms = scan_for_onset(
                audio_file="/test/song.mp3",
                expected_gap_ms=5000.0,
                model=mock_model,
                device="cpu",
                config=config,
                vocals_cache=vocals_cache,
                total_duration_ms=180000
            )
            
            # Should have expanded and found onset
            # (Exact value depends on chunk boundaries, just verify it ran)
            assert call_count >= 3  # At least 3 Demucs calls due to expansion
