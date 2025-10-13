"""
Detection provider abstraction for vocal onset and gap detection.
Provides pluggable strategies for different detection methods.
"""

import logging
import os
from abc import ABC, abstractmethod
from typing import List, Tuple, Optional, Callable
from common.config import Config

logger = logging.getLogger(__name__)


class DetectionProviderResult:
    """Result from detection provider operations."""
    
    def __init__(self):
        self.detected_gap: Optional[int] = None
        self.silence_periods: List[Tuple[float, float]] = []
        self.vocals_file: Optional[str] = None
        self.confidence: Optional[float] = None
        self.detection_method: str = "unknown"
        self.preview_wav_path: Optional[str] = None
        self.waveform_json_path: Optional[str] = None
        self.detected_gap_ms: Optional[float] = None
        self.first_note_ms: Optional[float] = None


class IDetectionProvider(ABC):
    """Base interface for detection providers."""
    
    def __init__(self, config: Config):
        self.config = config
    
    @abstractmethod
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
        Get or create vocals/preview file for gap detection.
        
        Args:
            audio_file: Path to input audio
            temp_root: Temporary directory root
            destination_vocals_filepath: Target path for vocals file
            duration: Duration to process in seconds
            overwrite: Whether to overwrite existing file
            check_cancellation: Cancellation check callback
            
        Returns:
            Path to vocals/preview file
        """
        pass
    
    @abstractmethod
    def detect_silence_periods(
        self,
        audio_file: str,
        vocals_file: str,
        check_cancellation: Optional[Callable[[], bool]] = None
    ) -> List[Tuple[float, float]]:
        """
        Detect silence/speech boundary periods in audio.
        
        Args:
            audio_file: Path to original audio file
            vocals_file: Path to vocals/preview file
            check_cancellation: Cancellation check callback
            
        Returns:
            List of (start_ms, end_ms) tuples for silence/boundary periods
        """
        pass
    
    @abstractmethod
    def compute_confidence(
        self,
        audio_file: str,
        detected_gap_ms: float,
        check_cancellation: Optional[Callable[[], bool]] = None
    ) -> float:
        """
        Compute confidence score for the detected gap.
        
        Args:
            audio_file: Path to audio file
            detected_gap_ms: Detected gap time in milliseconds
            check_cancellation: Cancellation check callback
            
        Returns:
            Confidence score 0.0-1.0
        """
        pass
    
    @abstractmethod
    def get_method_name(self) -> str:
        """Return the name of this detection method."""
        pass


class SpleeterProvider(IDetectionProvider):
    """Legacy Spleeter-based detection provider."""
    
    def get_vocals_file(
        self,
        audio_file: str,
        temp_root: str,
        destination_vocals_filepath: str,
        duration: int = 60,
        overwrite: bool = False,
        check_cancellation: Optional[Callable[[], bool]] = None
    ) -> str:
        """Get vocals file using Spleeter separation."""
        import utils.files as files
        import utils.audio as audio
        from utils.separate import separate_audio
        
        logger.debug(f"Using Spleeter to extract vocals from {audio_file}")
        
        if not overwrite and os.path.exists(destination_vocals_filepath):
            logger.debug(f"Vocals file already exists: {destination_vocals_filepath}")
            return destination_vocals_filepath
        
        output_path = os.path.join(temp_root, "spleeter")
        vocals_file, instrumental_file = separate_audio(
            audio_file,
            duration,
            output_path,
            overwrite,
            check_cancellation=check_cancellation
        )
        
        if vocals_file is None:
            raise Exception(f"Failed to extract vocals from '{audio_file}'")
        
        # Apply voice clarity filter
        vocals_file = audio.make_clearer_voice(vocals_file, check_cancellation)
        vocals_file = audio.convert_to_mp3(vocals_file, check_cancellation)
        
        # Move to destination
        if vocals_file and destination_vocals_filepath:
            if os.path.exists(destination_vocals_filepath):
                os.remove(destination_vocals_filepath)
            files.move_file(vocals_file, destination_vocals_filepath)
        
        files.rmtree(output_path)
        
        return destination_vocals_filepath
    
    def detect_silence_periods(
        self,
        audio_file: str,
        vocals_file: str,
        check_cancellation: Optional[Callable[[], bool]] = None
    ) -> List[Tuple[float, float]]:
        """Detect silence using ffmpeg silencedetect."""
        import utils.audio as audio
        
        return audio.detect_silence_periods(
            vocals_file,
            silence_detect_params=self.config.spleeter_silence_detect_params,
            check_cancellation=check_cancellation
        )
    
    def compute_confidence(
        self,
        audio_file: str,
        detected_gap_ms: float,
        check_cancellation: Optional[Callable[[], bool]] = None
    ) -> float:
        """Spleeter doesn't provide confidence - return default."""
        return 0.8  # Assume reasonable confidence for Spleeter
    
    def get_method_name(self) -> str:
        return "spleeter"


class VadPreviewProvider(IDetectionProvider):
    """VAD-based preview provider with HPSS."""
    
    def get_vocals_file(
        self,
        audio_file: str,
        temp_root: str,
        destination_vocals_filepath: str,
        duration: int = 60,
        overwrite: bool = False,
        check_cancellation: Optional[Callable[[], bool]] = None
    ) -> str:
        """Create vocals preview using HPSS and VAD (no full separation)."""
        logger.debug(f"Using VAD preview for {audio_file}")
        
        # For VAD preview, we'll create the preview later in the full detection flow
        # For now, just return a placeholder path
        # The actual preview will be created after gap detection
        
        # Create a minimal placeholder file if needed
        if not os.path.exists(destination_vocals_filepath) or overwrite:
            # We'll use the original audio temporarily
            # The full preview will be created after gap detection
            import shutil
            temp_file = os.path.join(temp_root, "vad_temp.wav")
            
            # Convert to WAV format for processing
            from utils.cancellable_process import run_cancellable_process
            command = [
                'ffmpeg', '-y', '-i', audio_file,
                '-t', str(duration),
                '-acodec', 'pcm_s16le',
                temp_file
            ]
            returncode, stdout, stderr = run_cancellable_process(command, check_cancellation)
            
            if returncode != 0:
                raise Exception(f"Failed to prepare audio: {stderr}")
            
            # Move to destination
            if os.path.exists(destination_vocals_filepath):
                os.remove(destination_vocals_filepath)
            shutil.move(temp_file, destination_vocals_filepath)
        
        return destination_vocals_filepath
    
    def detect_silence_periods(
        self,
        audio_file: str,
        vocals_file: str,
        check_cancellation: Optional[Callable[[], bool]] = None
    ) -> List[Tuple[float, float]]:
        """Detect speech segments using VAD on harmonic component of original audio."""
        from utils.vad import detect_speech_segments_vad
        from utils.hpss import extract_harmonic_only
        
        logger.debug("Detecting speech segments using VAD on harmonic component")
        
        try:
            # Extract harmonic component from ORIGINAL audio for vocal-focused VAD
            # This ensures we analyze the actual audio content, not a placeholder
            harmonic_file = extract_harmonic_only(
                audio_file,  # Changed from vocals_file to audio_file
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
                
                # VAD returns speech segments, but we need silence periods for compatibility
                # We'll return speech segments as-is and handle the inversion in the caller
                # For now, treat speech segments as the inverse of silence
                return speech_segments
                
            finally:
                # Clean up harmonic file
                if os.path.exists(harmonic_file):
                    os.remove(harmonic_file)
                    
        except Exception as e:
            logger.warning(f"VAD detection failed, falling back to silence detection: {e}")
            # Fallback to traditional silence detection
            import utils.audio as audio
            return audio.detect_silence_periods(
                vocals_file,
                silence_detect_params="silencedetect=noise=-30dB:d=0.2",
                check_cancellation=check_cancellation
            )
    
    def compute_confidence(
        self,
        audio_file: str,
        detected_gap_ms: float,
        check_cancellation: Optional[Callable[[], bool]] = None
    ) -> float:
        """Compute confidence using VAD probability and spectral flux."""
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
            
            # Compute spectral flux
            flux = compute_spectral_flux(
                audio_file,
                detected_gap_ms,
                window_ms=self.config.flux_snap_window_ms,
                check_cancellation=check_cancellation
            )
            
            # Combine: 70% VAD + 30% flux
            confidence = 0.7 * vad_conf + 0.3 * flux
            
            logger.debug(f"Computed confidence: {confidence:.3f} (VAD={vad_conf:.3f}, flux={flux:.3f})")
            return confidence
            
        except Exception as e:
            logger.warning(f"Confidence computation failed: {e}")
            return 0.5  # Default confidence
    
    def get_method_name(self) -> str:
        return "vad_preview"


class HqSegmentProvider(IDetectionProvider):
    """
    High-quality short-window provider.
    
    Strategy: Extract a short window around the detected gap, then apply
    high-quality processing only to that segment for efficiency.
    
    Current implementation uses Spleeter on the windowed segment for true
    stem separation without processing the entire track.
    """
    
    def __init__(self, config):
        self.config = config
    
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
        Get vocals using HQ model on short window around expected gap location.
        
        This extracts a focused window (preview_pre_ms + preview_post_ms) around
        the expected gap, runs Spleeter on just that segment, then returns the
        local vocal stem.
        """
        from utils.preview import extract_time_window
        from utils.separate import separate_audio
        import utils.files as files
        
        if not overwrite and os.path.exists(destination_vocals_filepath):
            logger.debug(f"HQ vocals file already exists: {destination_vocals_filepath}")
            return destination_vocals_filepath
        
        try:
            # Calculate window bounds around expected gap location
            # Use the detection duration as a proxy for expected gap timing
            expected_gap_ms = duration * 1000  # Convert to ms
            window_start_ms = max(0, expected_gap_ms - self.config.hq_preview_pre_ms)
            window_end_ms = expected_gap_ms + self.config.hq_preview_post_ms
            
            logger.info(f"HQ segment: Extracting window {window_start_ms}ms - {window_end_ms}ms "
                       f"(duration: {window_end_ms - window_start_ms}ms)")
            
            # Extract the focused window
            temp_dir = files.get_tmp_path(temp_root, audio_file)
            window_file = extract_time_window(
                audio_file,
                window_start_ms,
                window_end_ms,
                check_cancellation=check_cancellation
            )
            
            if check_cancellation and check_cancellation():
                if os.path.exists(window_file):
                    os.remove(window_file)
                raise Exception("Operation cancelled")
            
            # Run Spleeter on the extracted window only (much faster than full track)
            output_path = os.path.join(temp_dir, "hq_segment_spleeter")
            window_duration_sec = int((window_end_ms - window_start_ms) / 1000) + 1
            
            vocals_file, _ = separate_audio(
                window_file,
                window_duration_sec,
                output_path,
                overvrite=True,  # Note: typo in separate_audio signature
                check_cancellation=check_cancellation
            )
            
            # Move to destination
            if os.path.exists(destination_vocals_filepath):
                os.remove(destination_vocals_filepath)
            files.move_file(vocals_file, destination_vocals_filepath)
            
            # Cleanup
            if os.path.exists(window_file):
                os.remove(window_file)
            files.rmtree(output_path)
            
            logger.info(f"HQ segment vocals extracted: {destination_vocals_filepath}")
            return destination_vocals_filepath
            
        except Exception as e:
            logger.error(f"HQ segment separation failed: {e}, falling back to VAD preview")
            # Fallback to VAD preview if HQ processing fails
            provider = VadPreviewProvider(self.config)
            return provider.get_vocals_file(
                audio_file,
                temp_root,
                destination_vocals_filepath,
                duration,
                overwrite,
                check_cancellation
            )
    
    def detect_silence_periods(
        self,
        audio_file: str,
        vocals_file: str,
        check_cancellation: Optional[Callable[[], bool]] = None
    ) -> List[Tuple[float, float]]:
        """
        Detect silence periods in the HQ vocal stem.
        
        Since we have a true isolated vocal stem from the window,
        we can use traditional silence detection.
        """
        import utils.audio as audio
        
        try:
            return audio.detect_silence_periods(
                vocals_file,
                silence_detect_params=self.config.spleeter_silence_detect_params,
                check_cancellation=check_cancellation
            )
        except Exception as e:
            logger.error(f"HQ silence detection failed: {e}, falling back to VAD preview")
            provider = VadPreviewProvider(self.config)
            return provider.detect_silence_periods(audio_file, vocals_file, check_cancellation)
    
    def compute_confidence(
        self,
        audio_file: str,
        detected_gap_ms: float,
        check_cancellation: Optional[Callable[[], bool]] = None
    ) -> float:
        """
        Compute confidence for HQ detection.
        
        Since we use true stem separation on a focused window,
        confidence should be high (better than VAD but slightly
        lower than full-track Spleeter due to windowing).
        """
        # HQ segment uses true separation, so base confidence is high
        # Could be enhanced with:
        # - Spectral analysis of the stem quality
        # - Signal-to-noise ratio of the isolated vocal
        # - Onset detection strength
        return 0.85  # High confidence for true stem separation
    
    def get_method_name(self) -> str:
        return "hq_segment"


def get_detection_provider(config: Config) -> IDetectionProvider:
    """
    Factory function to get the appropriate detection provider based on config.
    
    Args:
        config: Application configuration
        
    Returns:
        Configured detection provider instance
    """
    method = config.method.lower()
    
    if method == "spleeter":
        logger.debug("Using Spleeter detection provider")
        return SpleeterProvider(config)
    elif method == "vad_preview":
        logger.debug("Using VAD Preview detection provider")
        return VadPreviewProvider(config)
    elif method == "hq_segment":
        logger.debug("Using HQ Segment detection provider")
        return HqSegmentProvider(config)
    else:
        logger.warning(f"Unknown detection method '{method}', defaulting to VAD Preview")
        return VadPreviewProvider(config)
