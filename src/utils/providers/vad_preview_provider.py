"""
VAD-based preview detection provider.

This provider uses Voice Activity Detection (VAD) combined with Harmonic-Percussive
Source Separation (HPSS) for fast CPU-only gap detection without full stem separation.
"""

import logging
import os
import shutil
from typing import List, Tuple, Optional, Callable

from utils.providers.base import IDetectionProvider
from utils.providers.exceptions import DetectionFailedError

logger = logging.getLogger(__name__)


class VadPreviewProvider(IDetectionProvider):
    """
    VAD-based preview provider with HPSS vocal enhancement.
    
    This provider performs fast vocal onset detection using Voice Activity Detection
    on a harmonic-enhanced version of the audio, without requiring full AI separation.
    
    Performance: 0.5-2 seconds per song (CPU-only)
    Output: Vocal-forward preview snippet (NOT isolated vocals)
    Detection: Speech-start based (finds nearest vocal onset)
    Confidence: Dynamic (70% VAD probability + 30% spectral flux)
    
    Process:
        1. Extract harmonic component from original audio (HPSS)
        2. Apply vocal-range band-pass filter (80Hz-8kHz)
        3. Run WebRTC VAD to detect speech segments
        4. Optionally snap to spectral flux peak (onset refinement)
        5. Create vocal-forward preview snippet around gap
    
    Use Cases:
        - Fast batch processing of large libraries
        - Quick gap verification
        - Visual waveform analysis
        - When true stems aren't needed
    """
    
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
        Prepare audio for VAD analysis (minimal preprocessing).
        
        For VAD preview, we don't perform full separation here. Instead, we prepare
        a temporary audio file that will be used for HPSS and VAD analysis later.
        The actual preview snippet is created after gap detection in the orchestration layer.
        
        Args:
            audio_file: Absolute path to input audio
            temp_root: Root directory for temporary files
            destination_vocals_filepath: Target path for preview file
            duration: Track duration in seconds
            overwrite: If True, regenerate even if destination exists
            check_cancellation: Callback returning True if user cancelled
        
        Returns:
            Absolute path to prepared audio file (usually just a WAV conversion)
        
        Raises:
            DetectionFailedError: If audio preparation fails
        
        Side Effects:
            - Creates temporary WAV file for processing
            - Converts to PCM format for VAD compatibility
        """
        logger.debug(f"VAD preview: Preparing audio from {audio_file}")
        
        # For VAD preview, we'll create the preview later in the full detection flow
        # For now, just prepare a WAV version for processing
        
        if not os.path.exists(destination_vocals_filepath) or overwrite:
            try:
                # Convert to WAV format for processing
                from utils.cancellable_process import run_cancellable_process
                
                temp_file = os.path.join(temp_root, "vad_temp.wav")
                command = [
                    'ffmpeg', '-y', '-i', audio_file,
                    '-t', str(duration),
                    '-acodec', 'pcm_s16le',
                    temp_file
                ]
                
                returncode, stdout, stderr = run_cancellable_process(command, check_cancellation)
                
                if returncode != 0:
                    raise DetectionFailedError(
                        f"VAD audio preparation failed: {stderr}",
                        provider_name="vad_preview"
                    )
                
                # Move to destination
                if os.path.exists(destination_vocals_filepath):
                    os.remove(destination_vocals_filepath)
                shutil.move(temp_file, destination_vocals_filepath)
                
                logger.debug(f"VAD preview: Prepared audio at {destination_vocals_filepath}")
                
            except DetectionFailedError:
                raise
            except Exception as e:
                raise DetectionFailedError(
                    f"VAD audio preparation failed: {e}",
                    provider_name="vad_preview",
                    cause=e
                )
        
        return destination_vocals_filepath
    
    def detect_silence_periods(
        self,
        audio_file: str,
        vocals_file: str,
        check_cancellation: Optional[Callable[[], bool]] = None
    ) -> List[Tuple[float, float]]:
        """
        Detect speech segments using VAD on harmonic component of original audio.
        
        **IMPORTANT:** This provider returns SPEECH segments (not silence), so the
        orchestration layer must use speech-start boundary selection logic.
        
        Process:
            1. Extract harmonic component from original audio (HPSS)
            2. Apply vocal-range band-pass filter (80Hz-8kHz)
            3. Run WebRTC VAD to detect speech activity
            4. Return speech segment boundaries
        
        Args:
            audio_file: Original audio file (used for HPSS extraction)
            vocals_file: Prepared audio file (not used, kept for interface compatibility)
            check_cancellation: Callback returning True if user cancelled
        
        Returns:
            List of (start_ms, end_ms) tuples for SPEECH regions (not silence)
        
        Raises:
            DetectionFailedError: If VAD detection fails
        
        Note:
            On failure, falls back to traditional silence detection for robustness.
        """
        from utils.vad import detect_speech_segments_vad
        from utils.hpss import extract_harmonic_only
        
        logger.debug("VAD preview: Detecting speech segments using VAD on harmonic component")
        
        try:
            # Extract harmonic component from ORIGINAL audio for vocal-focused VAD
            # This ensures we analyze the actual audio content, not a placeholder
            harmonic_file = extract_harmonic_only(
                audio_file,  # Analyze original audio, not vocals_file placeholder
                check_cancellation=check_cancellation
            )
            
            try:
                # Run VAD on harmonic component
                speech_segments = detect_speech_segments_vad(
                    harmonic_file,
                    frame_duration_ms=self.config.vad_frame_ms,
                    min_speech_ms=self.config.vad_min_speech_ms,
                    min_silence_ms=self.config.vad_min_silence_ms,
                    aggressiveness=self.config.vad_aggressiveness,
                    check_cancellation=check_cancellation
                )
                
                logger.debug(f"VAD preview: Detected {len(speech_segments)} speech segments")
                
                # VAD returns SPEECH segments - orchestration will use speech-start selection
                return speech_segments
                
            finally:
                # Clean up harmonic file
                if os.path.exists(harmonic_file):
                    os.remove(harmonic_file)
                    
        except Exception as e:
            logger.warning(f"VAD detection failed, falling back to silence detection: {e}")
            # Fallback to traditional silence detection on prepared audio
            import utils.audio as audio
            
            try:
                return audio.detect_silence_periods(
                    vocals_file,
                    silence_detect_params="silencedetect=noise=-30dB:d=0.2",
                    check_cancellation=check_cancellation
                )
            except Exception as fallback_err:
                raise DetectionFailedError(
                    f"VAD and fallback silence detection failed: {fallback_err}",
                    provider_name="vad_preview",
                    cause=fallback_err
                )
    
    def compute_confidence(
        self,
        audio_file: str,
        detected_gap_ms: float,
        check_cancellation: Optional[Callable[[], bool]] = None
    ) -> float:
        """
        Compute confidence using VAD probability and spectral flux.
        
        Combines two metrics for robust confidence scoring:
        - VAD probability: Speech detection confidence around gap
        - Spectral flux: Onset strength at detected gap position
        
        Formula: 70% VAD + 30% flux
        
        Args:
            audio_file: Original audio file for analysis
            detected_gap_ms: Detected gap position in milliseconds
            check_cancellation: Callback returning True if user cancelled
        
        Returns:
            Confidence score in range [0.0, 1.0]
        
        Note:
            Returns 0.5 default if confidence computation fails.
        """
        from utils.vad import compute_vad_confidence
        from utils.hpss import compute_spectral_flux
        
        try:
            # Compute VAD confidence
            vad_conf = compute_vad_confidence(
                audio_file,
                detected_gap_ms,
                window_ms=self.config.flux_snap_window_ms,
                aggressiveness=self.config.vad_aggressiveness
            )
            
            # Compute spectral flux magnitude
            flux = compute_spectral_flux(
                audio_file,
                detected_gap_ms,
                window_ms=self.config.flux_snap_window_ms,
                check_cancellation=check_cancellation
            )
            
            # Combine: 70% VAD + 30% flux
            confidence = 0.7 * vad_conf + 0.3 * flux
            
            logger.debug(f"VAD preview: Confidence={confidence:.3f} (VAD={vad_conf:.3f}, flux={flux:.3f})")
            return confidence
            
        except Exception as e:
            logger.warning(f"VAD confidence computation failed: {e}")
            return 0.5  # Default moderate confidence
    
    def get_method_name(self) -> str:
        """Return provider identifier."""
        return "vad_preview"
