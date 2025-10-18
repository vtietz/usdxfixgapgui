"""
Unit tests for MDX scanner modules.

Tests cover:
    - ChunkIterator: Boundary generation, overlap, deduplication
    - ExpansionStrategy: Window calculation, expansion logic
    - OnsetDetectorPipeline: Mocked audio processing
    - scan_for_onset: Integration with mocks
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
import torch
import numpy as np

from utils.providers.mdx.scanner.chunk_iterator import ChunkIterator, ChunkBoundaries
from utils.providers.mdx.scanner.expansion_strategy import ExpansionStrategy, SearchWindow
from utils.providers.mdx.scanner.onset_detector import OnsetDetectorPipeline
from utils.providers.mdx.scanner.pipeline import (
    scan_for_onset,
    _find_closest_onset,
    _is_duplicate_onset
)


# ==============================================================================
# TestChunkIterator
# ==============================================================================

class TestChunkIterator:
    """Test chunk boundary generation and deduplication."""
    
    def test_generates_basic_chunks(self):
        """Generate chunks without overlap."""
        iterator = ChunkIterator(
            chunk_duration_ms=10000,
            chunk_overlap_ms=0,
            total_duration_ms=30000
        )
        
        chunks = list(iterator.generate_chunks(0, 30000))
        
        assert len(chunks) == 3
        assert chunks[0].start_ms == 0
        assert chunks[0].end_ms == 10000
        assert chunks[1].start_ms == 10000
        assert chunks[2].start_ms == 20000
    
    def test_generates_overlapping_chunks(self):
        """Generate chunks with 50% overlap."""
        iterator = ChunkIterator(
            chunk_duration_ms=10000,
            chunk_overlap_ms=5000,
            total_duration_ms=30000
        )
        
        chunks = list(iterator.generate_chunks(0, 30000))
        
        # With 50% overlap (hop=5000): 0-10k, 5k-15k, 10k-20k, 15k-25k, 20k-30k, 25k-30k (partial)
        assert len(chunks) == 6
        assert chunks[0].end_ms == 10000
        assert chunks[1].start_ms == 5000
    
    def test_respects_duration_boundary(self):
        """Chunks don't exceed total duration."""
        iterator = ChunkIterator(
            chunk_duration_ms=10000,
            chunk_overlap_ms=0,
            total_duration_ms=25000  # Not evenly divisible
        )
        
        chunks = list(iterator.generate_chunks(0, 30000))
        
        assert all(chunk.end_ms <= 25000 for chunk in chunks)
        assert chunks[-1].end_ms == 25000
    
    def test_deduplicates_chunks(self):
        """Already processed chunks are skipped."""
        iterator = ChunkIterator(
            chunk_duration_ms=10000,
            chunk_overlap_ms=0,
            total_duration_ms=30000
        )
        
        # First pass
        chunks1 = list(iterator.generate_chunks(0, 20000))
        assert len(chunks1) == 2
        
        # Second pass overlaps first
        chunks2 = list(iterator.generate_chunks(10000, 30000))
        # Should skip 10k-20k (already processed) and only return 20k-30k
        assert len(chunks2) == 1
        assert chunks2[0].start_ms == 20000
    
    def test_chunk_boundaries_equality(self):
        """ChunkBoundaries equality works for deduplication."""
        chunk1 = ChunkBoundaries(1000.0, 2000.0)
        chunk2 = ChunkBoundaries(1000.0, 2000.0)
        chunk3 = ChunkBoundaries(1000.5, 2000.5)  # Rounded to same int
        
        assert chunk1 == chunk2
        assert chunk1 == chunk3  # Should match after int rounding
    
    def test_reset_clears_history(self):
        """Reset allows reprocessing chunks."""
        iterator = ChunkIterator(
            chunk_duration_ms=10000,
            chunk_overlap_ms=0,
            total_duration_ms=30000
        )
        
        chunks1 = list(iterator.generate_chunks(0, 20000))
        assert len(chunks1) == 2
        
        iterator.reset()
        
        chunks2 = list(iterator.generate_chunks(0, 20000))
        assert len(chunks2) == 2  # Reprocessed


# ==============================================================================
# TestExpansionStrategy
# ==============================================================================

class TestExpansionStrategy:
    """Test search window expansion logic."""
    
    def test_initial_window_centered(self):
        """Initial window is centered on expected gap."""
        strategy = ExpansionStrategy(
            initial_radius_ms=7500,
            radius_increment_ms=7500,
            max_expansions=2,
            total_duration_ms=180000
        )
        
        windows = strategy.generate_windows(expected_gap_ms=10000)
        
        assert windows[0].start_ms == 2500  # 10000 - 7500
        assert windows[0].end_ms == 17500  # 10000 + 7500
        assert windows[0].expansion_num == 0
    
    def test_window_expansion_sequence(self):
        """Windows expand by increment on each iteration."""
        strategy = ExpansionStrategy(
            initial_radius_ms=5000,
            radius_increment_ms=5000,
            max_expansions=2,
            total_duration_ms=180000
        )
        
        windows = strategy.generate_windows(expected_gap_ms=10000)
        
        assert len(windows) == 3  # Initial + 2 expansions
        assert windows[0].radius_ms == 5000
        assert windows[1].radius_ms == 10000
        assert windows[2].radius_ms == 15000
    
    def test_window_clamps_to_duration(self):
        """Windows don't exceed audio boundaries."""
        strategy = ExpansionStrategy(
            initial_radius_ms=10000,
            radius_increment_ms=10000,
            max_expansions=1,
            total_duration_ms=15000
        )
        
        windows = strategy.generate_windows(expected_gap_ms=5000)
        
        # First window would be -5000 to 15000, clamped to 0-15000
        assert windows[0].start_ms == 0
        assert windows[0].end_ms == 15000
    
    def test_should_continue_logic(self):
        """should_continue returns correct continuation decision."""
        strategy = ExpansionStrategy(
            initial_radius_ms=5000,
            radius_increment_ms=5000,
            max_expansions=2,
            total_duration_ms=180000
        )
        
        # Continue if no onset and not at max
        assert strategy.should_continue(0, found_onset=False) is True
        assert strategy.should_continue(1, found_onset=False) is True
        
        # Stop if onset found
        assert strategy.should_continue(0, found_onset=True) is False
        
        # Stop if at max expansions
        assert strategy.should_continue(2, found_onset=False) is False


# ==============================================================================
# TestOnsetDetectorPipeline
# ==============================================================================

class TestOnsetDetectorPipeline:
    """Test per-chunk onset detection pipeline."""
    
    @patch('utils.providers.mdx.scanner.onset_detector.torchaudio')
    @patch('utils.providers.mdx.scanner.onset_detector.separate_vocals_chunk')
    @patch('utils.providers.mdx.scanner.onset_detector.detect_onset_in_vocal_chunk')
    def test_successful_detection(self, mock_detect, mock_separate, mock_torchaudio):
        """Pipeline successfully detects onset in chunk."""
        # Setup mocks
        mock_info = Mock()
        mock_info.sample_rate = 44100
        mock_info.num_frames = 44100 * 60
        mock_torchaudio.info.return_value = mock_info
        
        mock_waveform = torch.randn(2, 44100 * 10)
        mock_torchaudio.load.return_value = (mock_waveform, 44100)
        
        mock_vocals = np.random.randn(2, 44100 * 10)
        mock_separate.return_value = mock_vocals
        
        mock_detect.return_value = 5000.0  # Detected onset at 5000ms
        
        # Create pipeline
        mock_config = Mock()
        mock_config.resample_hz = 0
        mock_config.use_fp16 = False
        
        mock_cache = Mock()
        
        pipeline = OnsetDetectorPipeline(
            audio_file="test.mp3",
            model=Mock(),
            device="cpu",
            config=mock_config,
            vocals_cache=mock_cache
        )
        
        # Process chunk
        chunk = ChunkBoundaries(0, 10000)
        onset_ms = pipeline.process_chunk(chunk)
        
        assert onset_ms == 5000.0
        mock_separate.assert_called_once()
        mock_detect.assert_called_once()
        mock_cache.put.assert_called_once()
    
    @patch('utils.providers.mdx.scanner.onset_detector.torchaudio')
    @patch('utils.providers.mdx.scanner.onset_detector.separate_vocals_chunk')
    @patch('utils.providers.mdx.scanner.onset_detector.detect_onset_in_vocal_chunk')
    def test_no_onset_found(self, mock_detect, mock_separate, mock_torchaudio):
        """Pipeline returns None when no onset found."""
        # Setup mocks
        mock_info = Mock()
        mock_info.sample_rate = 44100
        mock_info.num_frames = 44100 * 60
        mock_torchaudio.info.return_value = mock_info
        
        mock_waveform = torch.randn(2, 44100 * 10)
        mock_torchaudio.load.return_value = (mock_waveform, 44100)
        
        mock_vocals = np.random.randn(2, 44100 * 10)
        mock_separate.return_value = mock_vocals
        
        mock_detect.return_value = None  # No onset
        
        # Create pipeline
        mock_config = Mock()
        mock_config.resample_hz = 0
        mock_config.use_fp16 = False
        
        pipeline = OnsetDetectorPipeline(
            audio_file="test.mp3",
            model=Mock(),
            device="cpu",
            config=mock_config,
            vocals_cache=Mock()
        )
        
        # Process chunk
        chunk = ChunkBoundaries(0, 10000)
        onset_ms = pipeline.process_chunk(chunk)
        
        assert onset_ms is None
    
    @patch('utils.providers.mdx.scanner.onset_detector.torchaudio')
    def test_mono_to_stereo_conversion(self, mock_torchaudio):
        """Mono audio is converted to stereo."""
        # Setup mocks
        mock_info = Mock()
        mock_info.sample_rate = 44100
        mock_info.num_frames = 44100 * 60
        mock_torchaudio.info.return_value = mock_info
        
        mono_waveform = torch.randn(1, 44100 * 10)  # Mono
        mock_torchaudio.load.return_value = (mono_waveform, 44100)
        
        # Create pipeline
        mock_config = Mock()
        mock_config.resample_hz = 0
        
        pipeline = OnsetDetectorPipeline(
            audio_file="test.mp3",
            model=Mock(),
            device="cpu",
            config=mock_config,
            vocals_cache=Mock()
        )
        
        # Load chunk should convert to stereo
        chunk = ChunkBoundaries(0, 10000)
        waveform = pipeline._load_chunk(chunk)
        
        assert waveform.shape[0] == 2  # Stereo


# ==============================================================================
# TestHelperFunctions
# ==============================================================================

class TestHelperFunctions:
    """Test helper functions for onset processing."""
    
    def test_find_closest_onset(self):
        """Find onset closest to expected gap."""
        onsets = [2000.0, 5000.0, 8000.0]
        
        closest = _find_closest_onset(onsets, expected_gap_ms=4500.0)
        assert closest == 5000.0
        
        closest = _find_closest_onset(onsets, expected_gap_ms=7000.0)
        assert closest == 8000.0
    
    def test_is_duplicate_onset_true(self):
        """Duplicate detection identifies close onsets."""
        existing = [1000.0, 5000.0, 10000.0]
        
        # Within 1 second threshold
        assert _is_duplicate_onset(1500.0, existing, threshold_ms=1000) is True
        assert _is_duplicate_onset(5800.0, existing, threshold_ms=1000) is True
    
    def test_is_duplicate_onset_false(self):
        """Duplicate detection allows distant onsets."""
        existing = [1000.0, 5000.0, 10000.0]
        
        # Beyond threshold
        assert _is_duplicate_onset(2500.0, existing, threshold_ms=1000) is False
        assert _is_duplicate_onset(15000.0, existing, threshold_ms=1000) is False


# ==============================================================================
# TestScanForOnsetRefactored (Integration)
# ==============================================================================

class TestScanForOnset:
    """Test full refactored scanning pipeline."""
    
    @patch('utils.providers.mdx.scanner.onset_detector.torchaudio')
    @patch('utils.providers.mdx.scanner.onset_detector.separate_vocals_chunk')
    @patch('utils.providers.mdx.scanner.onset_detector.detect_onset_in_vocal_chunk')
    def test_finds_onset_in_initial_window(self, mock_detect, mock_separate, mock_torchaudio):
        """Onset found in initial window without expansion."""
        # Setup audio info mock
        mock_info = Mock()
        mock_info.sample_rate = 44100
        mock_info.num_frames = 44100 * 60
        mock_torchaudio.info.return_value = mock_info
        
        # Setup audio loading mock
        mock_waveform = torch.randn(2, 44100 * 12)
        mock_torchaudio.load.return_value = (mock_waveform, 44100)
        
        # Setup separation mock
        mock_vocals = np.random.randn(2, 44100 * 12)
        mock_separate.return_value = mock_vocals
        
        # Setup detection mock - find onset on first chunk
        mock_detect.return_value = 5000.0
        
        # Create config
        mock_config = Mock()
        mock_config.chunk_duration_ms = 12000
        mock_config.chunk_overlap_ms = 6000
        mock_config.initial_radius_ms = 7500
        mock_config.radius_increment_ms = 7500
        mock_config.max_expansions = 2
        mock_config.resample_hz = 0
        mock_config.use_fp16 = False
        
        # Run scan
        onset_ms = scan_for_onset(
            audio_file="test.mp3",
            expected_gap_ms=5000.0,
            model=Mock(),
            device="cpu",
            config=mock_config,
            vocals_cache=Mock(),
            total_duration_ms=60000.0
        )
        
        assert onset_ms == 5000.0
        # Should only process 1-2 chunks in initial window
        assert mock_detect.call_count <= 3
    
    @patch('utils.providers.mdx.scanner.onset_detector.torchaudio')
    @patch('utils.providers.mdx.scanner.onset_detector.separate_vocals_chunk')
    @patch('utils.providers.mdx.scanner.onset_detector.detect_onset_in_vocal_chunk')
    def test_expands_window_when_not_found(self, mock_detect, mock_separate, mock_torchaudio):
        """Window expands when no onset found initially."""
        # Setup mocks
        mock_info = Mock()
        mock_info.sample_rate = 44100
        mock_info.num_frames = 44100 * 60
        mock_torchaudio.info.return_value = mock_info
        
        mock_waveform = torch.randn(2, 44100 * 12)
        mock_torchaudio.load.return_value = (mock_waveform, 44100)
        
        mock_vocals = np.random.randn(2, 44100 * 12)
        mock_separate.return_value = mock_vocals
        
        # First N calls return None, then find onset
        call_count = [0]
        def detect_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] >= 5:  # Find on 5th chunk (after expansion)
                return 20000.0
            return None
        
        mock_detect.side_effect = detect_side_effect
        
        # Create config
        mock_config = Mock()
        mock_config.chunk_duration_ms = 12000
        mock_config.chunk_overlap_ms = 6000
        mock_config.initial_radius_ms = 7500
        mock_config.radius_increment_ms = 7500
        mock_config.max_expansions = 2
        mock_config.resample_hz = 0
        mock_config.use_fp16 = False
        
        # Run scan
        onset_ms = scan_for_onset(
            audio_file="test.mp3",
            expected_gap_ms=5000.0,
            model=Mock(),
            device="cpu",
            config=mock_config,
            vocals_cache=Mock(),
            total_duration_ms=60000.0
        )
        
        assert onset_ms == 20000.0
        # Should have processed multiple chunks across expansions
        assert mock_detect.call_count >= 5
    
    @patch('utils.providers.mdx.scanner.onset_detector.torchaudio')
    @patch('utils.providers.mdx.scanner.onset_detector.separate_vocals_chunk')
    @patch('utils.providers.mdx.scanner.onset_detector.detect_onset_in_vocal_chunk')
    def test_returns_none_when_no_onset_found(self, mock_detect, mock_separate, mock_torchaudio):
        """Returns None after all expansions with no onset."""
        # Setup mocks
        mock_info = Mock()
        mock_info.sample_rate = 44100
        mock_info.num_frames = 44100 * 60
        mock_torchaudio.info.return_value = mock_info
        
        mock_waveform = torch.randn(2, 44100 * 12)
        mock_torchaudio.load.return_value = (mock_waveform, 44100)
        
        mock_vocals = np.random.randn(2, 44100 * 12)
        mock_separate.return_value = mock_vocals
        
        mock_detect.return_value = None  # Never find onset
        
        # Create config
        mock_config = Mock()
        mock_config.chunk_duration_ms = 12000
        mock_config.chunk_overlap_ms = 6000
        mock_config.initial_radius_ms = 7500
        mock_config.radius_increment_ms = 7500
        mock_config.max_expansions = 1  # Limited expansions
        mock_config.resample_hz = 0
        mock_config.use_fp16 = False
        
        # Run scan
        onset_ms = scan_for_onset(
            audio_file="test.mp3",
            expected_gap_ms=5000.0,
            model=Mock(),
            device="cpu",
            config=mock_config,
            vocals_cache=Mock(),
            total_duration_ms=60000.0
        )
        
        assert onset_ms is None
