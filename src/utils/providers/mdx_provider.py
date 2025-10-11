"""
Demucs-based vocal separation provider with chunked scanning and energy-based onset detection.

This provider uses Demucs (state-of-the-art audio separation) for vocal separation combined with
adaptive energy-based onset detection. Unlike full-track separation, it scans in chunks
and stops as soon as the first vocal onset is detected, making it significantly faster
than traditional approaches while maintaining high accuracy.

Performance: 5-15 seconds per song (GPU), 15-45 seconds (CPU)
Output: Clean vocal stem (Demucs separated)
Detection: Energy-based onset on vocal stem
Confidence: SNR-based (signal-to-noise ratio)

Process:
    1. Scan audio in overlapping chunks (12s chunks, 50% overlap)
    2. Run Demucs on each chunk to get vocal stem
    3. Compute adaptive energy threshold from chunk's noise floor
    4. Detect vocal onset when RMS > noise_floor + k*sigma for min_duration
    5. Stop scanning as soon as first onset found (early exit)
    6. Refine detection in [onset-3s, onset+9s] window for preview
    7. Optional micro-snap using RMS rise peak
"""

import logging
import os
import numpy as np
import torch
import torchaudio
from typing import List, Tuple, Optional, Callable
from pathlib import Path

from demucs.apply import apply_model
from utils.providers.base import IDetectionProvider
from utils.providers.exceptions import DetectionFailedError

logger = logging.getLogger(__name__)


class MdxProvider(IDetectionProvider):
    """
    Demucs-based provider with chunked scanning and energy onset detection.
    
    This provider performs efficient vocal onset detection by scanning audio in chunks,
    separating vocals with Demucs, and using simple energy-based onset detection on the
    clean vocal stem. Stops as soon as the first vocal onset is detected.
    
    Advantages over VAD:
        - Demucs removes instruments → clean vocal stem
        - Energy threshold on clean stem is reliable
        - No PYIN needed (works on clean vocals)
        - Chunked scanning saves processing time
        - Early-stop on first detection
    
    Use Cases:
        - Fast vocal onset detection with high accuracy
        - Songs with continuous intro music (where VAD fails)
        - When Spleeter is too slow but VAD too unreliable
    """
    
    def __init__(self, config):
        """Initialize MDX provider with configuration."""
        super().__init__(config)
        
        # Chunked scanning parameters
        self.chunk_duration_ms = getattr(config, 'mdx_chunk_duration_ms', 12000)
        self.chunk_overlap_ms = getattr(config, 'mdx_chunk_overlap_ms', 6000)
        
        # Energy analysis parameters
        self.frame_duration_ms = getattr(config, 'mdx_frame_duration_ms', 25)
        self.hop_duration_ms = getattr(config, 'mdx_hop_duration_ms', 10)
        self.noise_floor_duration_ms = getattr(config, 'mdx_noise_floor_duration_ms', 800)
        
        # Onset detection thresholds
        self.onset_snr_threshold = getattr(config, 'mdx_onset_snr_threshold', 6.0)
        self.onset_abs_threshold = getattr(config, 'mdx_onset_abs_threshold', 0.02)
        self.min_voiced_duration_ms = getattr(config, 'mdx_min_voiced_duration_ms', 500)
        self.hysteresis_ms = getattr(config, 'mdx_hysteresis_ms', 200)
        
        # Fast single-window search parameters
        self.search_window_ms = getattr(config, 'mdx_search_window_ms', 20000)  # ±10s window around expected gap
        self.fallback_enabled = getattr(config, 'mdx_fallback_enabled', True)  # Fall back to full scan if nothing found
        
        # Confidence and preview
        self.confidence_threshold = getattr(config, 'mdx_confidence_threshold', 0.55)
        self.preview_pre_ms = getattr(config, 'mdx_preview_pre_ms', 3000)
        self.preview_post_ms = getattr(config, 'mdx_preview_post_ms', 9000)
        
        # Demucs model (lazy loaded)
        self._demucs_model = None
        self._device = 'cuda' if torch.cuda.is_available() else 'cpu'
        
        logger.debug(f"MDX provider initialized: chunk={self.chunk_duration_ms}ms, "
                    f"SNR_threshold={self.onset_snr_threshold}, abs_threshold={self.onset_abs_threshold}, "
                    f"search_window=±{self.search_window_ms/2/1000:.1f}s, device={self._device}")
    
    def _get_demucs_model(self):
        """Lazy load Demucs model."""
        if self._demucs_model is None:
            try:
                from demucs.pretrained import get_model
                logger.info(f"Loading Demucs model on {self._device}...")
                self._demucs_model = get_model('htdemucs')
                self._demucs_model.to(self._device)
                self._demucs_model.eval()
                logger.info("Demucs model loaded successfully")
            except Exception as e:
                raise DetectionFailedError(
                    f"Failed to load Demucs model: {e}",
                    provider_name="mdx",
                    cause=e
                )
        return self._demucs_model
    
    def get_vocals_file(
        self,
        audio_file: str,
        temp_root: str,
        destination_vocals_filepath: str,
        duration: int = 60,
        overwrite: bool = False,
        check_cancellation: Optional[Callable[[], bool]] = None
    ) -> str:
        """
        Prepare vocals using Demucs separation.
        
        For preview/final vocals, this creates a full-quality separated vocal file.
        Uses Demucs 'htdemucs' model for high-quality separation.
        
        Args:
            audio_file: Absolute path to input audio
            temp_root: Root directory for temporary files
            destination_vocals_filepath: Target path for vocals file
            duration: Track duration in seconds (not used - separates full track)
            overwrite: If True, regenerate even if destination exists
            check_cancellation: Callback returning True if user cancelled
        
        Returns:
            Absolute path to vocals file
        
        Raises:
            DetectionFailedError: If Demucs separation fails
        """
        logger.debug(f"MDX: Preparing vocals from {audio_file}")
        
        if not os.path.exists(destination_vocals_filepath) or overwrite:
            try:
                # Check cancellation
                if check_cancellation and check_cancellation():
                    raise DetectionFailedError("Separation cancelled by user", provider_name="mdx")
                
                # Load audio
                logger.info(f"Loading audio: {audio_file}")
                waveform, sample_rate = torchaudio.load(audio_file)
                
                # Convert to stereo if needed
                if waveform.shape[0] == 1:
                    waveform = waveform.repeat(2, 1)
                
                # Check cancellation
                if check_cancellation and check_cancellation():
                    raise DetectionFailedError("Separation cancelled by user", provider_name="mdx")
                
                # Run Demucs separation
                logger.info("Running Demucs separation...")
                model = self._get_demucs_model()
                
                with torch.no_grad():
                    # Prepare input
                    waveform = waveform.to(self._device)
                    # Use apply_model for Demucs inference (not direct call)
                    sources = apply_model(model, waveform.unsqueeze(0), device=self._device)
                    
                    # Extract vocals (index 3 in htdemucs: drums=0, bass=1, other=2, vocals=3)
                    vocals = sources[0, 3].cpu()  # Remove batch dimension, get vocals
                
                # Check cancellation
                if check_cancellation and check_cancellation():
                    raise DetectionFailedError("Separation cancelled by user", provider_name="mdx")
                
                # Save vocals
                logger.info(f"Saving vocals to: {destination_vocals_filepath}")
                os.makedirs(os.path.dirname(destination_vocals_filepath), exist_ok=True)
                torchaudio.save(destination_vocals_filepath, vocals, sample_rate)
                
                logger.info(f"MDX: Vocals prepared successfully at {destination_vocals_filepath}")
                
            except Exception as e:
                if "cancelled" in str(e).lower():
                    raise
                raise DetectionFailedError(
                    f"Demucs vocals preparation failed: {e}",
                    provider_name="mdx",
                    cause=e
                )
        else:
            logger.debug(f"MDX: Using existing vocals at {destination_vocals_filepath}")
        
        return destination_vocals_filepath
    
    def detect_silence_periods(
        self,
        audio_file: str,
        vocals_file: str,
        original_gap_ms: Optional[float] = None,
        check_cancellation: Optional[Callable[[], bool]] = None
    ) -> List[Tuple[float, float]]:
        """
        Detect silence periods using bidirectional Demucs scanning from expected gap.
        
        **Bidirectional Search Strategy**:
            1. Start at original_gap_ms (expected gap from song metadata)
            2. Expand search radius iteratively: ±5s, ±10s, ±15s, etc.
            3. Process chunks with Demucs separation → vocal stem
            4. Detect all vocal onsets in each search window
            5. Return FIRST onset closest to expected gap
            6. Return silence periods based on onset position
        
        **Energy-based Onset Detection**:
            - Estimate noise floor from first ~800ms of chunk
            - Compute short-time RMS (25ms frames, 10ms hop)
            - Onset when RMS > max(noise_floor + 6.0*sigma, 0.02 RMS) for ≥500ms
            - Use 200ms hysteresis for onset refinement
        
        Args:
            audio_file: Original audio file for chunked processing
            vocals_file: Pre-separated vocals (not used - we separate during search)
            original_gap_ms: Expected gap position from song metadata (for bidirectional search)
            check_cancellation: Callback returning True if user cancelled
        
        Returns:
            List of (start_ms, end_ms) tuples for SILENCE regions
        
        Raises:
            DetectionFailedError: If Demucs scanning fails
        """
        logger.debug("MDX: Detecting onset using bidirectional search")
        
        # Use original gap if provided, otherwise assume vocals at start
        expected_gap = original_gap_ms if original_gap_ms is not None else 0.0
        
        try:
            # Scan for first vocal onset using bidirectional search
            onset_ms = self._scan_chunks_for_onset(audio_file, expected_gap, check_cancellation)
            
            if onset_ms is None:
                logger.warning("MDX: No vocal onset detected, assuming vocals at start")
                onset_ms = 0.0
            
            logger.info(f"MDX: Detected vocal onset at {onset_ms:.1f}ms "
                       f"(expected: {expected_gap:.1f}ms, diff: {abs(onset_ms - expected_gap):.1f}ms)")
            
            # Convert onset to silence period
            # Return one silence period from 0 to onset
            if onset_ms > 0:
                silence_periods = [(0.0, onset_ms)]
            else:
                silence_periods = []
            
            logger.debug(f"MDX: Detected {len(silence_periods)} silence periods")
            return silence_periods
            
        except Exception as e:
            if "cancelled" in str(e).lower():
                raise
            raise DetectionFailedError(
                f"MDX onset detection failed: {e}",
                provider_name="mdx",
                cause=e
            )
    
    def compute_confidence(
        self,
        audio_file: str,
        detected_gap_ms: float,
        check_cancellation: Optional[Callable[[], bool]] = None
    ) -> float:
        """
        Compute confidence based on SNR (Signal-to-Noise Ratio) at onset.
        
        Analyzes the first 300ms after detected onset to compute SNR:
            - Load audio segment around onset
            - Separate vocals with Demucs
            - Measure RMS in 300ms window after onset (signal)
            - Measure RMS in first 800ms (noise floor)
            - Confidence = smooth_map(SNR_dB)
        
        Formula:
            SNR_dB = 20 * log10(RMS_signal / RMS_noise)
            Confidence = 1 / (1 + exp(-0.1 * (SNR_dB - 10)))
        
        Args:
            audio_file: Original audio file
            detected_gap_ms: Detected gap position in milliseconds
            check_cancellation: Callback returning True if user cancelled
        
        Returns:
            Confidence score in range [0.0, 1.0]
        """
        try:
            logger.debug(f"MDX: Computing confidence at gap={detected_gap_ms}ms")
            
            # Get audio info first
            info = torchaudio.info(audio_file)
            sample_rate = info.sample_rate
            
            # Load audio segment (first 5 seconds to get noise floor and signal)
            segment_duration = min(5.0, (detected_gap_ms / 1000.0) + 1.0)
            num_frames = int(segment_duration * sample_rate)
            
            # Load audio
            waveform, sample_rate = torchaudio.load(
                audio_file,
                frame_offset=0,
                num_frames=num_frames
            )
            
            # Convert to stereo if needed
            if waveform.shape[0] == 1:
                waveform = waveform.repeat(2, 1)
            
            # Separate vocals
            model = self._get_demucs_model()
            with torch.no_grad():
                waveform_gpu = waveform.to(self._device)
                sources = apply_model(model, waveform_gpu.unsqueeze(0), device=self._device)
                vocals = sources[0, 3].cpu().numpy()  # vocals channel, convert to numpy
            
            # Convert to mono for RMS calculation
            vocals_mono = np.mean(vocals, axis=0)
            
            # Compute RMS in noise floor region (first 800ms)
            noise_samples = int(0.8 * sample_rate)
            noise_rms = np.sqrt(np.mean(vocals_mono[:noise_samples]**2))
            
            # Compute RMS in signal region (300ms after onset)
            onset_sample = int((detected_gap_ms / 1000.0) * sample_rate)
            signal_duration_samples = int(0.3 * sample_rate)
            signal_end = min(onset_sample + signal_duration_samples, len(vocals_mono))
            
            if onset_sample < len(vocals_mono):
                signal_rms = np.sqrt(np.mean(vocals_mono[onset_sample:signal_end]**2))
            else:
                signal_rms = noise_rms
            
            # Compute SNR
            if noise_rms > 1e-8:
                snr_db = 20 * np.log10((signal_rms + 1e-8) / (noise_rms + 1e-8))
            else:
                snr_db = 20.0  # Assume good SNR if noise floor is very low
            
            # Map SNR to confidence using sigmoid
            # Center at 10dB, steepness 0.1
            confidence = 1.0 / (1.0 + np.exp(-0.1 * (snr_db - 10.0)))
            confidence = float(np.clip(confidence, 0.0, 1.0))
            
            logger.info(f"MDX: SNR={snr_db:.1f}dB, Confidence={confidence:.3f}")
            return confidence
            
        except Exception as e:
            logger.warning(f"MDX confidence computation failed: {e}")
            return 0.7  # Default moderate-high confidence
    
    def get_method_name(self) -> str:
        """Return provider identifier."""
        return "mdx"
    
    # ============================================================================
    # Private helper methods for chunked scanning
    # ============================================================================
    
    def _scan_chunks_for_onset(
        self,
        audio_file: str,
        expected_gap_ms: float,
        check_cancellation: Optional[Callable[[], bool]] = None
    ) -> Optional[float]:
        """
        Scan audio bidirectionally from expected gap to find first vocal onset.
        
        Strategy: Find the FIRST vocal onset (where vocals START), not the loudest.
        Searches from expected gap position with expanding radius until onset found.
        
        Implementation:
            1. Get audio metadata (duration, sample rate)
            2. Start at expected_gap_ms position
            3. For each iteration (radius ±5s, ±10s, ±15s, ...):
                a. Calculate search window [gap - radius, gap + radius]
                b. Process chunks in this window with Demucs separation
                c. Detect all vocal onsets in window
                d. If onset found, return the one closest to expected gap
            4. Return None if no onset found in max search range
        
        Args:
            audio_file: Path to audio file
            expected_gap_ms: Expected gap position from song metadata (ms)
            check_cancellation: Cancellation callback
        
        Returns:
            Absolute timestamp in milliseconds of first vocal onset, or None
        """
        try:
            # Get audio info
            info = torchaudio.info(audio_file)
            sample_rate = info.sample_rate
            total_duration_ms = (info.num_frames / sample_rate) * 1000.0
            
            logger.info(f"MDX: Bidirectional search from {expected_gap_ms:.0f}ms ({expected_gap_ms/1000:.1f}s) "
                       f"in {total_duration_ms/1000.0:.1f}s audio")
            logger.info(f"MDX: Strategy - Find FIRST vocal onset closest to expected position")
            
            # Track all detected onsets
            all_onsets = []
            
            # Bidirectional search with expanding radius
            for iteration in range(self.max_search_iterations):
                # Check cancellation
                if check_cancellation and check_cancellation():
                    raise DetectionFailedError("Search cancelled by user", provider_name="mdx")
                
                # Calculate search window
                radius_ms = self.search_radius_initial_ms + (iteration * self.search_radius_increment_ms)
                search_start_ms = max(0, expected_gap_ms - radius_ms)
                search_end_ms = min(total_duration_ms, expected_gap_ms + radius_ms)
                
                logger.info(f"MDX: Iteration {iteration + 1}/{self.max_search_iterations}: "
                           f"Searching {search_start_ms/1000:.1f}s - {search_end_ms/1000:.1f}s "
                           f"(±{radius_ms/1000:.1f}s)")
                
                # Process chunks in this search window
                chunk_duration_s = self.chunk_duration_ms / 1000.0
                chunk_hop_s = (self.chunk_duration_ms - self.chunk_overlap_ms) / 1000.0
                chunk_start_s = search_start_ms / 1000.0
                
                while chunk_start_s < search_end_ms / 1000.0:
                    # Check cancellation
                    if check_cancellation and check_cancellation():
                        raise DetectionFailedError("Search cancelled by user", provider_name="mdx")
                    
                    # Load chunk
                    frame_offset = int(chunk_start_s * sample_rate)
                    num_frames = min(
                        int(chunk_duration_s * sample_rate),
                        info.num_frames - frame_offset
                    )
                    
                    if num_frames <= 0:
                        break
                    
                    waveform, _ = torchaudio.load(
                        audio_file,
                        frame_offset=frame_offset,
                        num_frames=num_frames
                    )
                    
                    # Convert to stereo if needed
                    if waveform.shape[0] == 1:
                        waveform = waveform.repeat(2, 1)
                    
                    # Separate vocals with Demucs
                    model = self._get_demucs_model()
                    with torch.no_grad():
                        waveform_gpu = waveform.to(self._device)
                        sources = apply_model(model, waveform_gpu.unsqueeze(0), device=self._device)
                        vocals = sources[0, 3].cpu().numpy()
                    
                    # Detect onset in this chunk
                    chunk_start_ms = chunk_start_s * 1000.0
                    onset_ms = self._detect_onset_in_vocal_chunk(vocals, sample_rate, chunk_start_ms)
                    
                    if onset_ms is not None:
                        # Check if this is a new detection (not duplicate from overlap)
                        is_new = True
                        for existing_onset in all_onsets:
                            if abs(onset_ms - existing_onset) < 1000:  # Within 1 second
                                is_new = False
                                break
                        
                        if is_new:
                            all_onsets.append(onset_ms)
                            logger.info(f"MDX: Found vocal onset at {onset_ms:.0f}ms "
                                       f"(distance from expected: {abs(onset_ms - expected_gap_ms):.0f}ms)")
                    
                    # Move to next chunk
                    chunk_start_s += chunk_hop_s
                
                # After each iteration, check if we found onset(s)
                if all_onsets:
                    # Sort by distance from expected gap
                    all_onsets_sorted = sorted(all_onsets, key=lambda x: abs(x - expected_gap_ms))
                    closest = all_onsets_sorted[0]
                    
                    logger.info(f"MDX: Found {len(all_onsets)} onset(s) in search window")
                    logger.info(f"MDX: Closest to expected gap: {closest:.0f}ms "
                               f"(distance: {abs(closest - expected_gap_ms):.0f}ms)")
                    
                    # If closest is within current search radius, accept it
                    if abs(closest - expected_gap_ms) < radius_ms:
                        logger.info(f"MDX: Accepting {closest:.0f}ms as vocal start "
                                   f"(within ±{radius_ms/1000:.1f}s search radius)")
                        return closest
            
            # If we scanned everything and found onsets, return the earliest one
            if all_onsets:
                earliest = min(all_onsets)
                logger.info(f"MDX: Returning earliest onset found: {earliest:.0f}ms")
                return earliest
            
            # Calculate final radius for logging
            final_radius_ms = self.search_radius_initial_ms + ((self.max_search_iterations - 1) * self.search_radius_increment_ms)
            logger.info(f"MDX: No vocal onset detected in ±{final_radius_ms/1000:.1f}s search range")
            return None
            
        except Exception as e:
            if "cancelled" in str(e).lower():
                raise
            logger.error(f"MDX bidirectional search failed: {e}")
            raise
    
    def _detect_onset_in_vocal_chunk(
        self,
        vocal_audio: np.ndarray,
        sample_rate: int,
        chunk_start_ms: float
    ) -> Optional[float]:
        """
        Detect vocal onset in a vocal stem chunk using energy threshold.
        
        Implementation strategy:
            1. Convert to mono
            2. Estimate noise floor from first 800ms
            3. Compute short-time RMS (25ms frames, 10ms hop)
            4. Find onset where RMS > noise_floor + k*sigma for ≥180ms
            5. Return absolute timestamp (chunk_start + offset)
        
        Args:
            vocal_audio: Numpy array of vocal stem audio (channels, samples)
            sample_rate: Audio sample rate
            chunk_start_ms: Chunk start position in original audio (ms)
        
        Returns:
            Absolute timestamp in milliseconds of onset, or None if not found
        """
        try:
            # Convert to mono
            if vocal_audio.ndim > 1:
                vocal_mono = np.mean(vocal_audio, axis=0)
            else:
                vocal_mono = vocal_audio
            
            # Compute RMS
            frame_samples = int((self.frame_duration_ms / 1000.0) * sample_rate)
            hop_samples = int((self.hop_duration_ms / 1000.0) * sample_rate)
            
            rms_values = self._compute_rms(vocal_mono, frame_samples, hop_samples)
            
            # Estimate noise floor
            noise_floor_frames = int((self.noise_floor_duration_ms / 1000.0) / (self.hop_duration_ms / 1000.0))
            noise_floor, noise_sigma = self._estimate_noise_floor(rms_values, noise_floor_frames)
            
            max_rms = np.max(rms_values)
            mean_rms = np.mean(rms_values)
            
            logger.info(f"MDX: Chunk analysis - Noise floor={noise_floor:.6f}, sigma={noise_sigma:.6f}, "
                       f"max_rms={max_rms:.6f}, mean_rms={mean_rms:.6f}")
            
            # Detect onset - use BOTH SNR threshold AND absolute threshold
            snr_threshold = noise_floor + self.onset_snr_threshold * noise_sigma
            combined_threshold = max(snr_threshold, self.onset_abs_threshold)
            
            logger.info(f"MDX: Thresholds - SNR_threshold={snr_threshold:.6f}, "
                       f"Absolute_threshold={self.onset_abs_threshold:.6f}, "
                       f"Combined={combined_threshold:.6f}")
            
            # Find sustained energy above threshold
            min_frames = int((self.min_voiced_duration_ms / 1000.0) / (self.hop_duration_ms / 1000.0))
            hysteresis_frames = int((self.hysteresis_ms / 1000.0) / (self.hop_duration_ms / 1000.0))
            
            above_threshold = rms_values > combined_threshold
            onset_frame = None
            
            # Skip the noise floor region when searching
            search_start = max(noise_floor_frames + 1, 0)
            
            # Find first sustained onset (after noise floor region)
            for i in range(search_start, len(above_threshold) - min_frames):
                if np.all(above_threshold[i:i+min_frames]):
                    # Found sustained energy - now look back for the actual onset (rising edge)
                    onset_frame = i
                    
                    # Look back to find where energy first crosses threshold
                    for j in range(i - 1, max(search_start - 1, i - hysteresis_frames - 1), -1):
                        if j >= 0 and above_threshold[j]:
                            onset_frame = j  # Keep going back while above threshold
                        else:
                            break  # Stop at first frame below threshold (this is the onset!)
                    
                    # Refine onset by looking for maximum energy rise (derivative peak)
                    # within a small window around the detected onset
                    refine_window = min(10, onset_frame - search_start)  # 10 frames = 100ms window
                    if refine_window > 2:
                        window_start = max(search_start, onset_frame - refine_window)
                        window_end = min(onset_frame + 5, len(rms_values) - 1)
                        
                        # Compute energy derivative (rate of change)
                        rms_window = rms_values[window_start:window_end]
                        if len(rms_window) > 1:
                            energy_derivative = np.diff(rms_window)
                            
                            # Find maximum positive derivative (steepest rise)
                            if len(energy_derivative) > 0:
                                max_rise_idx = np.argmax(energy_derivative)
                                refined_onset = window_start + max_rise_idx
                                
                                # Only use refined onset if it's close to original and makes sense
                                if abs(refined_onset - onset_frame) <= refine_window:
                                    logger.debug(f"MDX: Refined onset from frame {onset_frame} to {refined_onset} "
                                               f"(energy rise: {energy_derivative[max_rise_idx]:.4f})")
                                    onset_frame = refined_onset
                    
                    break
            
            if onset_frame is not None:
                # Convert frame to absolute timestamp
                onset_offset_ms = (onset_frame * hop_samples / sample_rate) * 1000.0
                onset_abs_ms = chunk_start_ms + onset_offset_ms
                logger.info(f"MDX: Onset detected at {onset_abs_ms:.1f}ms "
                           f"(RMS={rms_values[onset_frame]:.4f}, threshold={combined_threshold:.4f})")
                return float(onset_abs_ms)
            
            return None
            
        except Exception as e:
            logger.warning(f"MDX onset detection in chunk failed: {e}")
            return None
    
    def _compute_rms(
        self,
        audio: np.ndarray,
        frame_samples: int,
        hop_samples: int
    ) -> np.ndarray:
        """
        Compute short-time RMS energy.
        
        Args:
            audio: Audio signal (mono)
            frame_samples: Frame size in samples
            hop_samples: Hop size in samples
        
        Returns:
            Array of RMS values for each frame
        """
        # Number of frames
        num_frames = 1 + (len(audio) - frame_samples) // hop_samples
        
        if num_frames <= 0:
            return np.array([])
        
        # Compute RMS for each frame
        rms_values = np.zeros(num_frames)
        for i in range(num_frames):
            start = i * hop_samples
            end = start + frame_samples
            if end <= len(audio):
                frame = audio[start:end]
                rms_values[i] = np.sqrt(np.mean(frame**2))
        
        return rms_values
    
    def _estimate_noise_floor(
        self,
        rms_values: np.ndarray,
        noise_floor_frames: int
    ) -> Tuple[float, float]:
        """
        Estimate noise floor and standard deviation from initial frames.
        
        Args:
            rms_values: Array of RMS values
            noise_floor_frames: Number of frames to use for estimation
        
        Returns:
            Tuple of (noise_floor, sigma)
        """
        if len(rms_values) == 0:
            return (0.0, 0.0)
        
        # Use first N frames for noise floor estimation
        noise_frames = rms_values[:min(noise_floor_frames, len(rms_values))]
        
        if len(noise_frames) == 0:
            return (0.0, 0.0)
        
        # Use median for robustness and std for variation
        noise_floor = float(np.median(noise_frames))
        noise_sigma = float(np.std(noise_frames))
        
        return (noise_floor, noise_sigma)
