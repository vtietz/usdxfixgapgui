"""Synthetic signal generation utilities for testing audio processing.

This module provides functions to generate synthetic audio signals
for unit testing onset detection, envelope extraction, and other
signal processing components without requiring real audio files.
"""

import numpy as np
from typing import Optional


def generate_silent_then_vocal(
    duration_sec: float, onset_at_sec: float, sample_rate: int = 22050, frequency: float = 440.0, amplitude: float = 0.5
) -> np.ndarray:
    """Generate synthetic audio: silence then tone.

    Creates a step function in amplitude - perfect for testing
    onset detection algorithms that look for sudden energy increases.

    Args:
        duration_sec: Total duration in seconds
        onset_at_sec: When tone starts (seconds)
        sample_rate: Sample rate in Hz
        frequency: Tone frequency in Hz (default 440Hz = A4)
        amplitude: Tone amplitude 0.0-1.0

    Returns:
        np.ndarray: Mono audio signal (float32)

    Example:
        >>> audio = generate_silent_then_vocal(2.0, 1.0)
        >>> # 2 seconds total, tone starts at 1 second
        >>> assert audio[:22050].max() < 0.01  # First second is silent
        >>> assert audio[22050:].max() > 0.4   # Second second has tone
    """
    n_samples = int(duration_sec * sample_rate)
    onset_sample = int(onset_at_sec * sample_rate)

    # Silence before onset
    audio = np.zeros(n_samples, dtype=np.float32)

    # Tone after onset
    tone_samples = n_samples - onset_sample
    t = np.arange(tone_samples) / sample_rate
    audio[onset_sample:] = amplitude * np.sin(2 * np.pi * frequency * t)

    return audio


def generate_chirp(
    duration_sec: float, start_freq: float, end_freq: float, sample_rate: int = 22050, amplitude: float = 0.5
) -> np.ndarray:
    """Generate frequency sweep (chirp) for onset detection testing.

    Useful for testing how detection algorithms respond to
    continuously changing frequency content.

    Args:
        duration_sec: Duration in seconds
        start_freq: Starting frequency in Hz
        end_freq: Ending frequency in Hz
        sample_rate: Sample rate in Hz
        amplitude: Signal amplitude 0.0-1.0

    Returns:
        np.ndarray: Mono audio signal (float32)

    Example:
        >>> audio = generate_chirp(2.0, 220, 880)  # A3 to A5
        >>> # Frequency increases linearly over 2 seconds
    """
    n_samples = int(duration_sec * sample_rate)

    # Linear frequency sweep
    freq = np.linspace(start_freq, end_freq, n_samples)
    # Integrate frequency to get phase
    phase = 2 * np.pi * np.cumsum(freq) / sample_rate

    return (amplitude * np.sin(phase)).astype(np.float32)


def generate_impulse_train(
    duration_sec: float, impulse_interval_sec: float, sample_rate: int = 22050, amplitude: float = 0.8
) -> np.ndarray:
    """Generate series of impulses (spikes) at regular intervals.

    Useful for testing peak detection and debouncing logic.

    Args:
        duration_sec: Total duration in seconds
        impulse_interval_sec: Time between impulses
        sample_rate: Sample rate in Hz
        amplitude: Impulse amplitude 0.0-1.0

    Returns:
        np.ndarray: Mono audio signal (float32) with impulses

    Example:
        >>> audio = generate_impulse_train(2.0, 0.5)
        >>> # Impulses at 0.0s, 0.5s, 1.0s, 1.5s
    """
    n_samples = int(duration_sec * sample_rate)
    audio = np.zeros(n_samples, dtype=np.float32)

    impulse_interval_samples = int(impulse_interval_sec * sample_rate)

    # Place impulses
    for i in range(0, n_samples, impulse_interval_samples):
        if i < n_samples:
            audio[i] = amplitude

    return audio


def generate_noise(
    duration_sec: float, sample_rate: int = 22050, amplitude: float = 0.1, seed: Optional[int] = None
) -> np.ndarray:
    """Generate white noise for testing noise floor estimation.

    Args:
        duration_sec: Duration in seconds
        sample_rate: Sample rate in Hz
        amplitude: Noise amplitude 0.0-1.0
        seed: Random seed for reproducibility

    Returns:
        np.ndarray: Mono white noise signal (float32)

    Example:
        >>> noise = generate_noise(1.0, seed=42)
        >>> # Reproducible noise for testing
    """
    if seed is not None:
        np.random.seed(seed)

    n_samples = int(duration_sec * sample_rate)
    noise = np.random.randn(n_samples).astype(np.float32)

    # Normalize to amplitude range
    noise = amplitude * noise / (np.abs(noise).max() + 1e-8)

    return noise


def generate_envelope_test_signal(
    duration_sec: float,
    attack_sec: float,
    sustain_sec: float,
    release_sec: float,
    sample_rate: int = 22050,
    frequency: float = 440.0,
    amplitude: float = 0.7,
) -> np.ndarray:
    """Generate signal with ADSR-like envelope for envelope extraction testing.

    Args:
        duration_sec: Total duration
        attack_sec: Attack time (ramp up)
        sustain_sec: Sustain time (constant)
        release_sec: Release time (ramp down)
        sample_rate: Sample rate in Hz
        frequency: Carrier frequency in Hz
        amplitude: Maximum amplitude

    Returns:
        np.ndarray: Mono audio signal (float32) with envelope
    """
    n_samples = int(duration_sec * sample_rate)
    attack_samples = int(attack_sec * sample_rate)
    sustain_samples = int(sustain_sec * sample_rate)
    release_samples = int(release_sec * sample_rate)

    # Generate carrier tone
    t = np.arange(n_samples) / sample_rate
    carrier = np.sin(2 * np.pi * frequency * t).astype(np.float32)

    # Generate envelope
    envelope = np.zeros(n_samples, dtype=np.float32)

    # Attack
    envelope[:attack_samples] = np.linspace(0, amplitude, attack_samples)

    # Sustain
    sustain_start = attack_samples
    sustain_end = sustain_start + sustain_samples
    envelope[sustain_start:sustain_end] = amplitude

    # Release
    release_start = sustain_end
    release_end = min(release_start + release_samples, n_samples)
    release_len = release_end - release_start
    envelope[release_start:release_end] = np.linspace(amplitude, 0, release_len)

    # Apply envelope
    return carrier * envelope


def add_noise_to_signal(signal: np.ndarray, snr_db: float, seed: Optional[int] = None) -> np.ndarray:
    """Add white noise to signal at specified SNR.

    Args:
        signal: Input signal
        snr_db: Signal-to-noise ratio in dB
        seed: Random seed for reproducibility

    Returns:
        np.ndarray: Signal + noise

    Example:
        >>> clean = generate_silent_then_vocal(1.0, 0.5)
        >>> noisy = add_noise_to_signal(clean, snr_db=20)
        >>> # Signal 20dB louder than noise
    """
    if seed is not None:
        np.random.seed(seed)

    # Calculate signal power
    signal_power = np.mean(signal**2)

    # Calculate noise power from SNR
    snr_linear = 10 ** (snr_db / 10)
    noise_power = signal_power / snr_linear

    # Generate noise
    noise = np.random.randn(len(signal)).astype(np.float32)
    noise = noise * np.sqrt(noise_power)

    return signal + noise
