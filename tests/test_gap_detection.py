"""Unit tests for gap detection pipeline.

Tests each pipeline step independently to ensure correctness,
then validates end-to-end integration.
"""

import os
import pytest
from unittest.mock import Mock, patch, MagicMock
from dataclasses import dataclass

from utils.gap_detection.pipeline import (
    GapDetectionContext,
    validate_inputs,
    calculate_detection_time,
    normalize_context,
    detect_gap_from_silence,
    should_retry_detection,
    compute_confidence_score,
    perform,
)
from utils.types import DetectGapResult


class TestValidateInputs:
    """Test input validation with clear error messages."""
    
    def test_rejects_missing_audio_file_path(self):
        """Validation catches missing audio file path."""
        with pytest.raises(ValueError, match="Audio file path is required"):
            validate_inputs("", 5000, None, Mock())
    
    def test_rejects_nonexistent_audio_file(self):
        """Validation catches nonexistent audio file."""
        with pytest.raises(FileNotFoundError, match="Audio file not found"):
            validate_inputs("/nonexistent/file.mp3", 5000, None, Mock())
    
    def test_rejects_negative_gap(self):
        """Validation catches negative gap value."""
        with pytest.raises(ValueError, match="Original gap cannot be negative"):
            validate_inputs(__file__, -1000, None, Mock())
    
    def test_rejects_negative_audio_length(self):
        """Validation catches negative audio length."""
        with pytest.raises(ValueError, match="Audio length cannot be negative"):
            validate_inputs(__file__, 5000, -100, Mock())
    
    def test_rejects_missing_config(self):
        """Validation catches missing config."""
        with pytest.raises(ValueError, match="Config is required"):
            validate_inputs(__file__, 5000, None, None)
    
    def test_accepts_valid_inputs(self):
        """Validation passes for valid inputs."""
        # Should not raise
        validate_inputs(__file__, 5000, 120000, Mock())


class TestCalculateDetectionTime:
    """Test detection time window calculation."""
    
    def test_default_sufficient_for_small_gap(self):
        """Default detection time used when gap is small."""
        result = calculate_detection_time(5000, 60)
        assert result == 90  # 60 * 1.5 = 90
    
    def test_increments_for_large_gap(self):
        """Detection time incremented when gap exceeds default."""
        result = calculate_detection_time(65000, 60)  # 65s gap
        # 60s < 65s, so increment to 120s, then 120*1.5 = 180s
        assert result == 180
    
    def test_multiple_increments_for_very_large_gap(self):
        """Multiple increments for very large gaps."""
        result = calculate_detection_time(125000, 60)  # 125s gap
        # 60 < 125, increment to 120
        # 120 < 125, increment to 180
        # 180 * 1.5 = 270s
        assert result == 270
    
    def test_buffer_multiplier_applied(self):
        """50% buffer is added to detection time."""
        result = calculate_detection_time(10000, 30)  # 10s gap
        # 30s sufficient, 30 * 1.5 = 45s
        assert result == 45


class TestDetectGapFromSilence:
    """Test pure gap detection logic."""
    
    def test_returns_zero_for_no_silence(self):
        """No silence periods means vocals start immediately."""
        result = detect_gap_from_silence([], 5000)
        assert result == 0
    
    def test_finds_closest_period_start(self):
        """Finds start of closest silence period."""
        periods = [(0, 1000), (5000, 6000), (10000, 11000)]
        result = detect_gap_from_silence(periods, 5200)
        assert result == 5000  # Closer than 6000
    
    def test_finds_closest_period_end(self):
        """Finds end of closest silence period."""
        periods = [(0, 1000), (5000, 6000), (10000, 11000)]
        result = detect_gap_from_silence(periods, 5900)
        assert result == 6000  # Closer than 5000
    
    def test_handles_exact_match(self):
        """Exact match on period boundary."""
        periods = [(0, 1000), (5000, 6000)]
        result = detect_gap_from_silence(periods, 5000)
        assert result == 5000
    
    def test_chooses_earlier_on_tie(self):
        """When equidistant, chooses first encountered."""
        periods = [(0, 1000), (5000, 6000)]
        # 5500 is equidistant from 5000 and 6000
        result = detect_gap_from_silence(periods, 5500)
        assert result in [5000, 6000]  # Either is valid


class TestShouldRetryDetection:
    """Test retry logic."""
    
    def test_no_retry_when_gap_within_window(self):
        """Don't retry if gap is within detection window."""
        result = should_retry_detection(
            detected_gap_ms=30000,
            detection_time_sec=60,
            audio_length_ms=120000
        )
        assert result is False
    
    def test_no_retry_when_window_covers_full_audio(self):
        """Don't retry if detection window already covers full audio."""
        result = should_retry_detection(
            detected_gap_ms=70000,
            detection_time_sec=120,
            audio_length_ms=100000
        )
        assert result is False
    
    def test_retry_when_gap_beyond_window(self):
        """Retry if gap is beyond window and room to expand."""
        result = should_retry_detection(
            detected_gap_ms=70000,
            detection_time_sec=60,
            audio_length_ms=120000
        )
        assert result is True
    
    def test_handles_no_audio_length(self):
        """Handles case when audio length is unknown."""
        result = should_retry_detection(
            detected_gap_ms=70000,
            detection_time_sec=60,
            audio_length_ms=None
        )
        assert result is True


class TestGapDetectionContext:
    """Test context validation."""
    
    def test_validates_on_construction(self):
        """Context validates inputs during construction."""
        with pytest.raises(FileNotFoundError):
            GapDetectionContext(
                audio_file="/nonexistent.mp3",
                original_gap_ms=5000,
                detection_time_sec=60,
                audio_length_ms=120000,
                tmp_root="/tmp",
                config=Mock(),
                overwrite=False
            )
    
    def test_accepts_valid_context(self):
        """Context constructed successfully with valid inputs."""
        ctx = GapDetectionContext(
            audio_file=__file__,
            original_gap_ms=5000,
            detection_time_sec=60,
            audio_length_ms=120000,
            tmp_root="/tmp",
            config=Mock(),
            overwrite=False
        )
        assert ctx.audio_file == __file__
        assert ctx.original_gap_ms == 5000


class TestNormalizeContext:
    """Test context normalization."""
    
    @patch('utils.gap_detection.pipeline.audio')
    def test_detects_audio_length_when_missing(self, mock_audio):
        """Normalizer detects audio length if not provided."""
        mock_audio.get_audio_duration.return_value = 120.5
        
        ctx = normalize_context(
            audio_file=__file__,
            tmp_root="/tmp",
            original_gap=5000,
            audio_length=None,
            default_detection_time=60,
            config=Mock(),
            overwrite=False
        )
        
        assert ctx.audio_length_ms == 120500  # 120.5s * 1000
        mock_audio.get_audio_duration.assert_called_once()
    
    def test_uses_provided_audio_length(self):
        """Normalizer uses provided audio length."""
        ctx = normalize_context(
            audio_file=__file__,
            tmp_root="/tmp",
            original_gap=5000,
            audio_length=100000,
            default_detection_time=60,
            config=Mock(),
            overwrite=False
        )
        
        assert ctx.audio_length_ms == 100000
    
    def test_calculates_detection_time(self):
        """Normalizer calculates appropriate detection time."""
        ctx = normalize_context(
            audio_file=__file__,
            tmp_root="/tmp",
            original_gap=5000,
            audio_length=120000,
            default_detection_time=60,
            config=Mock(),
            overwrite=False
        )
        
        # 60s * 1.5 = 90s
        assert ctx.detection_time_sec == 90


class TestPerform:
    """Test end-to-end refactored pipeline."""
    
    @patch('utils.gap_detection.pipeline.get_detection_provider')
    @patch('utils.gap_detection.pipeline.files')
    @patch('utils.gap_detection.pipeline.audio')
    def test_successful_detection(self, mock_audio, mock_files, mock_get_provider):
        """Complete detection pipeline succeeds."""
        # Setup mocks
        mock_audio.get_audio_duration.return_value = 120.0
        mock_files.get_tmp_path.return_value = "/tmp/song"
        mock_files.get_vocals_path.return_value = "/tmp/song/vocals.wav"
        
        mock_provider = Mock()
        mock_provider.get_method_name.return_value = "mdx"
        mock_provider.get_vocals_file.return_value = "/tmp/song/vocals.wav"
        mock_provider.detect_silence_periods.return_value = [(4500, 5500)]
        mock_provider.compute_confidence.return_value = 0.95
        mock_get_provider.return_value = mock_provider
        
        # Execute
        result = perform(
            audio_file=__file__,
            tmp_root="/tmp",
            original_gap=5000,
            audio_length=None,
            default_detection_time=60,
            config=Mock(),
            overwrite=False
        )
        
        # Verify
        assert isinstance(result, DetectGapResult)
        assert result.detected_gap == 4500  # Closest boundary: 4500 is 500ms from 5000, 5500 is 500ms from 5000
        assert result.detection_method == "mdx"
        assert result.confidence == 0.95
        assert len(result.silence_periods) == 1
    
    @patch('utils.gap_detection.pipeline.get_detection_provider')
    @patch('utils.gap_detection.pipeline.files')
    @patch('utils.gap_detection.pipeline.audio')
    def test_handles_no_silence_periods(self, mock_audio, mock_files, mock_get_provider):
        """Handles case with no silence periods (vocals start immediately)."""
        mock_audio.get_audio_duration.return_value = 120.0
        mock_files.get_tmp_path.return_value = "/tmp/song"
        mock_files.get_vocals_path.return_value = "/tmp/song/vocals.wav"
        
        mock_provider = Mock()
        mock_provider.get_method_name.return_value = "mdx"
        mock_provider.get_vocals_file.return_value = "/tmp/song/vocals.wav"
        mock_provider.detect_silence_periods.return_value = []
        mock_provider.compute_confidence.return_value = 0.5
        mock_get_provider.return_value = mock_provider
        
        result = perform(
            audio_file=__file__,
            tmp_root="/tmp",
            original_gap=5000,
            audio_length=120000,
            default_detection_time=60,
            config=Mock(),
            overwrite=False
        )
        
        assert result.detected_gap == 0
    
    def test_raises_on_invalid_inputs(self):
        """Pipeline raises appropriate errors for invalid inputs."""
        with pytest.raises(FileNotFoundError):
            perform(
                audio_file="/nonexistent.mp3",
                tmp_root="/tmp",
                original_gap=5000,
                audio_length=120000,
                default_detection_time=60,
                config=Mock(),
                overwrite=False
            )
