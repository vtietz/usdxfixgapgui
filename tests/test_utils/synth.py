"""
Synthetic signal generator for Tier-1 onset detection tests.

Generates deterministic numpy arrays representing vocal stems with controllable onset behavior.
"""

from typing import Tuple

import numpy as np


def harmonic_tone(f0_hz: float, duration_ms: int, sr: int = 44100, harmonics: int = 4, amp: float = 0.8) -> np.ndarray:
    """
    Generate harmonic tone with fundamental and harmonics.

    Args:
        f0_hz: Fundamental frequency in Hz
        duration_ms: Duration in milliseconds
        sr: Sample rate
        harmonics: Number of harmonics (including fundamental)
        amp: Peak amplitude

    Returns:
        Numpy array of harmonic tone
    """
    n_samples = int(duration_ms / 1000.0 * sr)
    t = np.arange(n_samples) / sr

    # Build harmonic series with decreasing amplitude
    signal = np.zeros(n_samples)
    for h in range(1, harmonics + 1):
        harmonic_amp = amp / h  # Amplitude decreases with harmonic number
        signal += harmonic_amp * np.sin(2 * np.pi * f0_hz * h * t)

    # Normalize to peak amplitude
    if np.max(np.abs(signal)) > 0:
        signal = signal / np.max(np.abs(signal)) * amp

    return signal


def envelope_fade_in(signal: np.ndarray, fade_in_ms: int, sr: int = 44100) -> np.ndarray:
    """
    Apply fade-in envelope to signal.

    Args:
        signal: Input signal
        fade_in_ms: Fade-in duration in milliseconds
        sr: Sample rate

    Returns:
        Signal with fade-in applied
    """
    if fade_in_ms <= 0:
        return signal

    fade_samples = int(fade_in_ms / 1000.0 * sr)
    fade_samples = min(fade_samples, len(signal))

    envelope = np.ones(len(signal))
    # Linear fade-in
    envelope[:fade_samples] = np.linspace(0, 1, fade_samples)

    return signal * envelope


def add_breath_preroll(signal: np.ndarray, breath_ms: int, level_db: float, sr: int = 44100) -> np.ndarray:
    """
    Add breath noise before the signal.

    Args:
        signal: Input signal
        breath_ms: Breath duration in milliseconds
        level_db: Breath level in dB relative to full scale
        sr: Sample rate

    Returns:
        Signal with breath preroll prepended
    """
    if breath_ms <= 0:
        return signal

    breath_samples = int(breath_ms / 1000.0 * sr)
    # Deterministic breath noise
    rng = np.random.default_rng(12345)
    breath = rng.normal(0, 1, breath_samples)

    # Scale to desired level
    breath_amplitude = 10 ** (level_db / 20.0)
    breath = breath * breath_amplitude

    # Find signal start position and prepend breath
    return np.concatenate([breath, signal])


def add_noise_floor(signal: np.ndarray, level_db: float, sr: int = 44100, color: str = "white") -> np.ndarray:
    """
    Add noise floor to signal.

    Args:
        signal: Input signal
        level_db: Noise level in dB relative to full scale
        sr: Sample rate
        color: Noise color ("white" or "pink")

    Returns:
        Signal with noise floor added
    """
    if level_db >= 0:
        # No noise or invalid level
        return signal

    # Deterministic noise
    rng = np.random.default_rng(54321)

    if color == "white":
        noise = rng.normal(0, 1, len(signal))
    elif color == "pink":
        # Simple pink noise approximation using white noise and filtering
        white = rng.normal(0, 1, len(signal))
        # Apply simple low-pass effect (rolling average)
        b = np.ones(5) / 5
        noise = np.convolve(white, b, mode="same")
    else:
        noise = rng.normal(0, 1, len(signal))

    # Scale to desired level
    noise_amplitude = 10 ** (level_db / 20.0)
    noise = noise * noise_amplitude

    return signal + noise


def pad_silence(ms: int, sr: int = 44100) -> np.ndarray:
    """
    Generate silence padding.

    Args:
        ms: Duration in milliseconds
        sr: Sample rate

    Returns:
        Numpy array of zeros
    """
    n_samples = int(ms / 1000.0 * sr)
    return np.zeros(n_samples)


def mix_signals(signals: list) -> np.ndarray:
    """
    Mix multiple signals by concatenation.

    Args:
        signals: List of numpy arrays

    Returns:
        Concatenated signal
    """
    return np.concatenate(signals)


def normalize_peak(signal: np.ndarray, peak: float = 0.9) -> np.ndarray:
    """
    Normalize signal to peak amplitude.

    Args:
        signal: Input signal
        peak: Target peak amplitude

    Returns:
        Normalized signal
    """
    max_val = np.max(np.abs(signal))
    if max_val > 0:
        return signal / max_val * peak
    return signal


def build_vocal_onset(
    duration_ms: int,
    onset_ms: int,
    fade_in_ms: int = 0,
    breath_ms: int = 0,
    breath_db: float = -24.0,
    f0_hz: float = 220.0,
    harmonics: int = 4,
    noise_floor_db: float = -60.0,
    sr: int = 44100,
) -> Tuple[np.ndarray, dict]:
    """
    Build synthetic vocal onset scenario.

    Constructs: silence until onset_ms, optional breath preroll, harmonic tone with fade-in,
    optional constant noise floor, normalized to peak.

    Args:
        duration_ms: Total duration in milliseconds
        onset_ms: Onset position in milliseconds
        fade_in_ms: Fade-in duration in milliseconds (0 for abrupt)
        breath_ms: Breath preroll duration in milliseconds (0 for none)
        breath_db: Breath level in dB relative to full scale
        f0_hz: Fundamental frequency in Hz
        harmonics: Number of harmonics (including fundamental)
        noise_floor_db: Noise floor level in dB relative to full scale
        sr: Sample rate

    Returns:
        Tuple of (audio array, metadata dict)
    """
    # Calculate vocal segment duration (after onset)
    vocal_start = onset_ms - breath_ms
    if vocal_start < 0:
        raise ValueError(f"onset_ms ({onset_ms}) must be >= breath_ms ({breath_ms})")

    vocal_duration_ms = duration_ms - vocal_start

    # Build vocal segment
    vocal_tone = harmonic_tone(f0_hz, vocal_duration_ms, sr, harmonics, amp=0.8)

    # Apply fade-in
    if fade_in_ms > 0:
        vocal_tone = envelope_fade_in(vocal_tone, fade_in_ms, sr)

    # Add breath preroll if requested
    if breath_ms > 0:
        vocal_tone = add_breath_preroll(vocal_tone, breath_ms, breath_db, sr)

    # Build complete signal: silence + vocal
    silence = pad_silence(vocal_start, sr)
    signal = mix_signals([silence, vocal_tone])

    # Add noise floor
    if noise_floor_db < 0:
        signal = add_noise_floor(signal, noise_floor_db, sr, color="white")

    # Normalize
    signal = normalize_peak(signal, peak=0.9)

    # Build metadata
    meta = {
        "onset_ms": onset_ms,
        "sr": sr,
        "fade_in_ms": fade_in_ms,
        "breath_ms": breath_ms,
        "breath_db": breath_db,
        "f0_hz": f0_hz,
        "harmonics": harmonics,
        "noise_floor_db": noise_floor_db,
        "duration_ms": duration_ms,
        "vocal_start_ms": vocal_start,
    }

    return signal, meta
