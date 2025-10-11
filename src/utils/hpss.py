"""
Harmonic-Percussive Source Separation (HPSS) utilities using librosa.
Separates audio into harmonic (tonal/vocal) and percussive (rhythmic) components.
"""

import logging
import os
import tempfile
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

try:
    import librosa
    import soundfile as sf
    import numpy as np
    LIBROSA_AVAILABLE = True
except ImportError:
    LIBROSA_AVAILABLE = False
    logger.warning("librosa not available. HPSS functionality will be disabled.")


def hpss_mono(
    audio_file: str,
    output_dir: Optional[str] = None,
    kernel_size: int = 31,
    power: float = 2.0,
    margin: float = 1.0,
    check_cancellation: Optional[callable] = None
) -> Tuple[str, str]:
    """
    Perform Harmonic-Percussive Source Separation on mono audio.
    
    Args:
        audio_file: Path to input audio file
        output_dir: Directory for output files (defaults to same as input)
        kernel_size: Size of median filter kernel
        power: Exponent for the spectrogram magnitude
        margin: Margin for separation (higher = more aggressive separation)
        check_cancellation: Optional cancellation check callback
        
    Returns:
        Tuple of (harmonic_file_path, percussive_file_path)
    """
    if not LIBROSA_AVAILABLE:
        raise ImportError("librosa is required for HPSS. Install with: pip install librosa soundfile")
    
    if not os.path.exists(audio_file):
        raise FileNotFoundError(f"Audio file not found: {audio_file}")
    
    logger.debug(f"Performing HPSS on {audio_file}")
    
    if check_cancellation and check_cancellation():
        logger.info("HPSS cancelled before loading")
        raise Exception("Operation cancelled")
    
    # Load audio
    y, sr = librosa.load(audio_file, sr=None, mono=True)
    
    if check_cancellation and check_cancellation():
        logger.info("HPSS cancelled after loading")
        raise Exception("Operation cancelled")
    
    # Perform HPSS
    logger.debug(f"Separating harmonic and percussive components (kernel={kernel_size}, power={power}, margin={margin})")
    y_harmonic, y_percussive = librosa.effects.hpss(
        y, 
        kernel_size=kernel_size,
        power=power,
        margin=margin
    )
    
    if check_cancellation and check_cancellation():
        logger.info("HPSS cancelled after separation")
        raise Exception("Operation cancelled")
    
    # Determine output directory
    if output_dir is None:
        output_dir = os.path.dirname(audio_file)
    os.makedirs(output_dir, exist_ok=True)
    
    # Create output file paths
    base_name = os.path.splitext(os.path.basename(audio_file))[0]
    harmonic_file = os.path.join(output_dir, f"{base_name}_harmonic.wav")
    percussive_file = os.path.join(output_dir, f"{base_name}_percussive.wav")
    
    # Save separated components
    logger.debug(f"Saving harmonic component to {harmonic_file}")
    sf.write(harmonic_file, y_harmonic, sr)
    
    if check_cancellation and check_cancellation():
        logger.info("HPSS cancelled after saving harmonic")
        # Clean up
        if os.path.exists(harmonic_file):
            os.remove(harmonic_file)
        raise Exception("Operation cancelled")
    
    logger.debug(f"Saving percussive component to {percussive_file}")
    sf.write(percussive_file, y_percussive, sr)
    
    logger.info(f"HPSS completed: {harmonic_file}, {percussive_file}")
    return harmonic_file, percussive_file


def blend_hpss_components(
    harmonic_file: str,
    percussive_file: str,
    harmonic_weight: float = 0.8,
    percussive_weight: float = 0.2,
    output_file: Optional[str] = None,
    check_cancellation: Optional[callable] = None
) -> str:
    """
    Blend harmonic and percussive components with specified weights.
    
    Args:
        harmonic_file: Path to harmonic component
        percussive_file: Path to percussive component
        harmonic_weight: Weight for harmonic (0.0-1.0)
        percussive_weight: Weight for percussive (0.0-1.0)
        output_file: Path for output file (defaults to temp file)
        check_cancellation: Optional cancellation check callback
        
    Returns:
        Path to blended audio file
    """
    if not LIBROSA_AVAILABLE:
        raise ImportError("librosa is required for blending. Install with: pip install librosa soundfile")
    
    logger.debug(f"Blending HPSS components: {harmonic_weight}*H + {percussive_weight}*P")
    
    # Load components
    y_harmonic, sr_h = librosa.load(harmonic_file, sr=None, mono=True)
    y_percussive, sr_p = librosa.load(percussive_file, sr=None, mono=True)
    
    if sr_h != sr_p:
        raise ValueError(f"Sample rates must match: {sr_h} vs {sr_p}")
    
    if check_cancellation and check_cancellation():
        logger.info("Blending cancelled")
        raise Exception("Operation cancelled")
    
    # Ensure same length
    min_len = min(len(y_harmonic), len(y_percussive))
    y_harmonic = y_harmonic[:min_len]
    y_percussive = y_percussive[:min_len]
    
    # Blend
    y_blended = harmonic_weight * y_harmonic + percussive_weight * y_percussive
    
    # Determine output file
    if output_file is None:
        temp_dir = os.path.dirname(harmonic_file)
        output_file = tempfile.NamedTemporaryFile(delete=False, suffix='_blended.wav', dir=temp_dir).name
    
    # Save
    logger.debug(f"Saving blended audio to {output_file}")
    sf.write(output_file, y_blended, sr_h)
    
    return output_file


def extract_harmonic_only(
    audio_file: str,
    output_file: Optional[str] = None,
    kernel_size: int = 31,
    check_cancellation: Optional[callable] = None
) -> str:
    """
    Extract only the harmonic component (convenience function for vocal-focused analysis).
    
    Args:
        audio_file: Path to input audio file
        output_file: Path for output file (defaults to temp file)
        kernel_size: Size of median filter kernel
        check_cancellation: Optional cancellation check callback
        
    Returns:
        Path to harmonic component file
    """
    if not LIBROSA_AVAILABLE:
        raise ImportError("librosa is required. Install with: pip install librosa soundfile")
    
    logger.debug(f"Extracting harmonic component from {audio_file}")
    
    # Load audio
    y, sr = librosa.load(audio_file, sr=None, mono=True)
    
    if check_cancellation and check_cancellation():
        raise Exception("Operation cancelled")
    
    # Extract harmonic only
    y_harmonic = librosa.effects.harmonic(y, kernel_size=kernel_size)
    
    # Determine output file
    if output_file is None:
        temp_dir = os.path.dirname(audio_file)
        base_name = os.path.splitext(os.path.basename(audio_file))[0]
        output_file = os.path.join(temp_dir, f"{base_name}_harmonic.wav")
    
    # Save
    logger.debug(f"Saving harmonic component to {output_file}")
    sf.write(output_file, y_harmonic, sr)
    
    return output_file


def compute_spectral_flux(
    audio_file: str,
    time_ms: float,
    window_ms: int = 150,
    check_cancellation: Optional[callable] = None
) -> float:
    """
    Compute spectral flux around a specific time point (for onset snap).
    
    Args:
        audio_file: Path to audio file
        time_ms: Time point in milliseconds
        window_ms: Window size in milliseconds
        check_cancellation: Optional cancellation check callback
        
    Returns:
        Normalized spectral flux magnitude (0.0-1.0)
    """
    if not LIBROSA_AVAILABLE:
        return 0.5  # Default when unavailable
    
    try:
        # Load audio
        y, sr = librosa.load(audio_file, sr=None, mono=True)
        
        if check_cancellation and check_cancellation():
            return 0.0
        
        # Convert time to samples
        time_samples = int(time_ms * sr / 1000)
        window_samples = int(window_ms * sr / 1000)
        
        start_sample = max(0, time_samples - window_samples // 2)
        end_sample = min(len(y), time_samples + window_samples // 2)
        
        # Extract window
        y_window = y[start_sample:end_sample]
        
        # Compute onset strength (spectral flux)
        onset_env = librosa.onset.onset_strength(y=y_window, sr=sr)
        
        if len(onset_env) == 0:
            return 0.0
        
        # Normalize to 0-1 range
        flux = float(np.max(onset_env))
        if flux > 0:
            flux = min(1.0, flux / np.mean(onset_env))
        
        logger.debug(f"Spectral flux at {time_ms}ms: {flux:.3f}")
        return flux
        
    except Exception as e:
        logger.warning(f"Error computing spectral flux: {e}")
        return 0.5


def find_flux_peak(
    audio_file: str,
    center_ms: float,
    window_ms: int = 150,
    check_cancellation: Optional[callable] = None
) -> Optional[float]:
    """
    Find the spectral flux peak (onset) within a window around center_ms.
    
    Args:
        audio_file: Path to audio file
        center_ms: Center time point in milliseconds
        window_ms: Search window size in milliseconds (±window_ms/2 from center)
        check_cancellation: Optional cancellation check callback
        
    Returns:
        Time in ms of the flux peak, or None if unavailable
    """
    if not LIBROSA_AVAILABLE:
        logger.warning("librosa not available, cannot perform flux snap")
        return None
    
    try:
        # Load audio
        y, sr = librosa.load(audio_file, sr=None, mono=True)
        
        if check_cancellation and check_cancellation():
            return None
        
        # Convert time to samples
        center_samples = int(center_ms * sr / 1000)
        window_samples = int(window_ms * sr / 1000)
        
        start_sample = max(0, center_samples - window_samples // 2)
        end_sample = min(len(y), center_samples + window_samples // 2)
        
        # Extract window
        y_window = y[start_sample:end_sample]
        
        # Compute onset strength envelope
        onset_env = librosa.onset.onset_strength(y=y_window, sr=sr)
        
        if len(onset_env) == 0:
            logger.warning("No onset envelope computed")
            return None
        
        # Find peak position in onset envelope
        peak_idx = int(np.argmax(onset_env))
        
        # Convert back to milliseconds relative to original audio
        # onset_strength downsamples by default, need to account for hop_length
        hop_length = 512  # librosa default
        peak_sample_in_window = peak_idx * hop_length
        peak_sample_absolute = start_sample + peak_sample_in_window
        peak_ms = float(peak_sample_absolute * 1000 / sr)
        
        logger.debug(f"Flux peak found at {peak_ms:.1f}ms (original: {center_ms:.1f}ms, diff: {peak_ms - center_ms:+.1f}ms)")
        return peak_ms
        
    except Exception as e:
        logger.warning(f"Error finding flux peak: {e}")
        return None
