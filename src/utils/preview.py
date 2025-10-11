"""
Vocals preview generator for gap detection.
Creates focused audio previews around detected gap points.
"""

import logging
import os
import tempfile
from typing import Optional, List, Tuple

logger = logging.getLogger(__name__)

try:
    import librosa
    import soundfile as sf
    import numpy as np
    LIBROSA_AVAILABLE = True
except ImportError:
    LIBROSA_AVAILABLE = False
    logger.warning("librosa not available. Preview generation will be limited.")


def extract_time_window(
    audio_file: str,
    start_ms: float,
    end_ms: float,
    output_file: Optional[str] = None,
    check_cancellation: Optional[callable] = None
) -> str:
    """
    Extract a time window from audio file.
    
    Args:
        audio_file: Path to input audio file
        start_ms: Start time in milliseconds
        end_ms: End time in milliseconds
        output_file: Path for output file (defaults to temp file)
        check_cancellation: Optional cancellation check callback
        
    Returns:
        Path to extracted window audio file
    """
    from utils.cancellable_process import run_cancellable_process
    
    if output_file is None:
        temp_dir = os.path.dirname(audio_file)
        output_file = tempfile.NamedTemporaryFile(delete=False, suffix='_window.wav', dir=temp_dir).name
    
    # Use ffmpeg for precise window extraction
    start_sec = start_ms / 1000.0
    duration_sec = (end_ms - start_ms) / 1000.0
    
    command = [
        'ffmpeg', '-y',
        '-ss', str(start_sec),
        '-t', str(duration_sec),
        '-i', audio_file,
        '-acodec', 'pcm_s16le',
        output_file
    ]
    
    returncode, stdout, stderr = run_cancellable_process(command, check_cancellation)
    
    if returncode != 0:
        if os.path.exists(output_file):
            os.remove(output_file)
        raise Exception(f"Failed to extract window: {stderr}")
    
    return output_file


def apply_vad_gate(
    audio_file: str,
    vad_segments: List[Tuple[float, float]],
    attenuation_db: float = -12.0,
    output_file: Optional[str] = None,
    check_cancellation: Optional[callable] = None
) -> str:
    """
    Apply VAD-based gating to attenuate non-vocal frames.
    
    Args:
        audio_file: Path to input audio file
        vad_segments: List of (start_ms, end_ms) speech segments
        attenuation_db: Attenuation for non-speech areas in dB
        output_file: Path for output file
        check_cancellation: Optional cancellation check callback
        
    Returns:
        Path to gated audio file
    """
    if not LIBROSA_AVAILABLE:
        logger.warning("librosa not available, skipping VAD gating")
        return audio_file
    
    logger.debug(f"Applying VAD gate with {len(vad_segments)} speech segments")
    
    # Load audio
    y, sr = librosa.load(audio_file, sr=None, mono=True)
    
    if check_cancellation and check_cancellation():
        raise Exception("Operation cancelled")
    
    # Create mask for speech regions
    mask = np.ones_like(y)
    attenuation_factor = 10 ** (attenuation_db / 20.0)  # Convert dB to linear
    
    # Set mask to attenuation factor for non-speech regions
    mask[:] = attenuation_factor
    
    # Mark speech regions as full volume (1.0)
    for start_ms, end_ms in vad_segments:
        start_sample = int(start_ms * sr / 1000)
        end_sample = int(end_ms * sr / 1000)
        start_sample = max(0, start_sample)
        end_sample = min(len(y), end_sample)
        mask[start_sample:end_sample] = 1.0
    
    # Apply mask
    y_gated = y * mask
    
    if check_cancellation and check_cancellation():
        raise Exception("Operation cancelled")
    
    # Determine output file
    if output_file is None:
        temp_dir = os.path.dirname(audio_file)
        output_file = tempfile.NamedTemporaryFile(delete=False, suffix='_gated.wav', dir=temp_dir).name
    
    # Save
    logger.debug(f"Saving gated audio to {output_file}")
    sf.write(output_file, y_gated, sr)
    
    return output_file


def build_vocals_preview(
    audio_file: str,
    detected_gap_ms: float,
    pre_ms: int = 3000,
    post_ms: int = 9000,
    vad_segments: Optional[List[Tuple[float, float]]] = None,
    use_hpss: bool = True,
    output_file: Optional[str] = None,
    check_cancellation: Optional[callable] = None
) -> str:
    """
    Build a vocals-focused preview window around the detected gap.
    
    Args:
        audio_file: Path to input audio file
        detected_gap_ms: Detected gap time in milliseconds
        pre_ms: Milliseconds before gap to include
        post_ms: Milliseconds after gap to include
        vad_segments: Optional VAD segments for gating (relative to audio start)
        use_hpss: Whether to use HPSS blend (requires librosa)
        output_file: Path for output file
        check_cancellation: Optional cancellation check callback
        
    Returns:
        Path to vocals preview file
    """
    logger.info(f"Building vocals preview around {detected_gap_ms}ms (±{pre_ms}/{post_ms}ms)")
    
    # Calculate window bounds
    start_ms = max(0, detected_gap_ms - pre_ms)
    end_ms = detected_gap_ms + post_ms
    
    # Extract time window
    window_file = extract_time_window(audio_file, start_ms, end_ms, check_cancellation=check_cancellation)
    
    try:
        # Apply HPSS blend if available and requested
        if use_hpss and LIBROSA_AVAILABLE:
            logger.debug("Applying HPSS blend to preview")
            from utils.hpss import hpss_mono, blend_hpss_components
            
            # Perform HPSS on the window
            output_dir = os.path.dirname(window_file)
            harmonic_file, percussive_file = hpss_mono(
                window_file, 
                output_dir=output_dir,
                check_cancellation=check_cancellation
            )
            
            try:
                # Blend: 0.8 harmonic + 0.2 percussive
                blended_file = blend_hpss_components(
                    harmonic_file, 
                    percussive_file,
                    harmonic_weight=0.8,
                    percussive_weight=0.2,
                    check_cancellation=check_cancellation
                )
                
                # Replace window file with blended version
                if os.path.exists(window_file):
                    os.remove(window_file)
                window_file = blended_file
                
            finally:
                # Clean up HPSS components
                if os.path.exists(harmonic_file):
                    os.remove(harmonic_file)
                if os.path.exists(percussive_file):
                    os.remove(percussive_file)
        
        # Apply VAD gating if segments provided
        if vad_segments and LIBROSA_AVAILABLE:
            # Adjust VAD segments to window coordinates
            adjusted_segments = []
            for seg_start, seg_end in vad_segments:
                # Convert to window-relative time
                rel_start = seg_start - start_ms
                rel_end = seg_end - start_ms
                
                # Only include segments that overlap the window
                if rel_end > 0 and rel_start < (end_ms - start_ms):
                    rel_start = max(0, rel_start)
                    rel_end = min(end_ms - start_ms, rel_end)
                    adjusted_segments.append((rel_start, rel_end))
            
            if adjusted_segments:
                logger.debug(f"Applying VAD gating with {len(adjusted_segments)} segments")
                gated_file = apply_vad_gate(
                    window_file,
                    adjusted_segments,
                    attenuation_db=-9.0,  # 9dB attenuation for non-vocal
                    check_cancellation=check_cancellation
                )
                
                if gated_file != window_file:
                    if os.path.exists(window_file):
                        os.remove(window_file)
                    window_file = gated_file
        
        # Apply voice clarity filter
        from utils.audio import make_clearer_voice
        logger.debug("Applying voice clarity filter")
        window_file = make_clearer_voice(window_file, check_cancellation)
        
        # Determine final output file
        if output_file is None:
            temp_dir = os.path.dirname(audio_file)
            output_file = os.path.join(temp_dir, f"vocals_preview.wav")
        
        # Move to final location
        if window_file != output_file:
            if os.path.exists(output_file):
                os.remove(output_file)
            os.rename(window_file, output_file)
        
        logger.info(f"Vocals preview created: {output_file}")
        return output_file
        
    except Exception as e:
        # Clean up on error
        if os.path.exists(window_file):
            os.remove(window_file)
        raise e
