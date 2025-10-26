"""
Audio factory for Tier-2 scanner orchestration tests.

Generates deterministic stereo test files with:
- Left channel: mixture (vocals + instruments)
- Right channel: isolated vocals (ground-truth stem)

This allows testing scanner logic with stubbed separation by returning the right channel.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Optional

import numpy as np
import torchaudio


@dataclass
class VocalEvent:
    """Single vocal event parameters."""
    onset_ms: float
    duration_ms: float
    fade_in_ms: float = 100
    amp: float = 0.7
    f0_hz: float = 220.0
    harmonics: int = 4


@dataclass
class InstrumentBed:
    """Instrument bed parameters."""
    noise_floor_db: float = -60.0
    color: str = "white"
    transients: Optional[List[Dict[str, float]]] = None  # [{t_ms, level_db, dur_ms}]

    def __post_init__(self):
        if self.transients is None:
            self.transients = []


@dataclass
class AudioBuildResult:
    """Result of stereo test audio build."""
    path: str
    sr: int
    truth_onsets_ms: List[float]
    duration_ms: float
    vocal_events: List[VocalEvent]
    instrument_bed: InstrumentBed


def build_stereo_test(
    output_path: Path,
    sr: int = 44100,
    duration_ms: float = 60000,
    vocal_events: Optional[List[VocalEvent]] = None,
    instrument_bed: Optional[InstrumentBed] = None,
    mix_snr_db: Optional[float] = None
) -> AudioBuildResult:
    """
    Build deterministic stereo test audio file.

    Creates:
    - Left channel: mixture = vocals + instruments
    - Right channel: pure vocals

    Args:
        output_path: Output file path (.wav)
        sr: Sample rate
        duration_ms: Total duration in milliseconds
        vocal_events: List of vocal events to synthesize
        instrument_bed: Instrument bed parameters
        mix_snr_db: SNR of vocals in mixture (if None, use event amplitudes directly)

    Returns:
        AudioBuildResult with path, metadata, and ground-truth onsets
    """
    if vocal_events is None:
        vocal_events = []
    if instrument_bed is None:
        instrument_bed = InstrumentBed()

    # Calculate samples
    total_samples = int(duration_ms / 1000.0 * sr)

    # Build vocals channel (right)
    vocals = np.zeros(total_samples, dtype=np.float32)
    truth_onsets_ms = []

    for event in vocal_events:
        vocals = _add_vocal_event(vocals, event, sr)
        truth_onsets_ms.append(event.onset_ms)

    # Build instruments channel
    instruments = _build_instrument_bed(total_samples, instrument_bed, sr)

    # Build mixture (left)
    if mix_snr_db is not None:
        # Compute RMS and scale vocals to achieve target SNR
        vocal_rms = np.sqrt(np.mean(vocals**2))
        instrument_rms = np.sqrt(np.mean(instruments**2))

        if instrument_rms > 0:
            target_vocal_rms = instrument_rms * (10 ** (mix_snr_db / 20.0))
            if vocal_rms > 0:
                vocals_scaled = vocals * (target_vocal_rms / vocal_rms)
            else:
                vocals_scaled = vocals
        else:
            vocals_scaled = vocals

        mixture = vocals_scaled + instruments
    else:
        mixture = vocals + instruments

    # Normalize to avoid clipping
    mixture = _normalize_peak(mixture, peak=0.9)
    vocals = _normalize_peak(vocals, peak=0.9)

    # Stack stereo: [left=mixture, right=vocals]
    stereo = np.stack([mixture, vocals], axis=0)

    # Convert to torch tensor
    import torch
    stereo_tensor = torch.from_numpy(stereo).float()

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Save as WAV
    torchaudio.save(str(output_path), stereo_tensor, sr, encoding='PCM_S', bits_per_sample=16)

    return AudioBuildResult(
        path=str(output_path),
        sr=sr,
        truth_onsets_ms=truth_onsets_ms,
        duration_ms=duration_ms,
        vocal_events=vocal_events,
        instrument_bed=instrument_bed
    )


def _add_vocal_event(
    signal: np.ndarray,
    event: VocalEvent,
    sr: int
) -> np.ndarray:
    """Add a vocal event to the signal."""
    onset_samples = int(event.onset_ms / 1000.0 * sr)
    duration_samples = int(event.duration_ms / 1000.0 * sr)
    fade_in_samples = int(event.fade_in_ms / 1000.0 * sr)

    # Generate harmonic tone
    t = np.arange(duration_samples) / sr
    tone = np.zeros(duration_samples)

    for h in range(1, event.harmonics + 1):
        harmonic_amp = event.amp / h
        tone += harmonic_amp * np.sin(2 * np.pi * event.f0_hz * h * t)

    # Normalize harmonics
    if np.max(np.abs(tone)) > 0:
        tone = tone / np.max(np.abs(tone)) * event.amp

    # Apply fade-in
    if fade_in_samples > 0 and fade_in_samples < len(tone):
        envelope = np.ones(len(tone))
        envelope[:fade_in_samples] = np.linspace(0, 1, fade_in_samples)
        tone = tone * envelope

    # Add to signal
    end_sample = min(onset_samples + duration_samples, len(signal))
    tone_length = end_sample - onset_samples
    if tone_length > 0 and onset_samples < len(signal):
        signal[onset_samples:end_sample] += tone[:tone_length]

    return signal


def _build_instrument_bed(
    total_samples: int,
    bed: InstrumentBed,
    sr: int
) -> np.ndarray:
    """Build instrument bed with noise and transients."""
    # Deterministic RNG
    rng = np.random.default_rng(42)

    # Base noise floor
    if bed.color == "white":
        instruments = rng.normal(0, 1, total_samples)
    elif bed.color == "pink":
        white = rng.normal(0, 1, total_samples)
        # Simple pink approximation
        b = np.ones(5) / 5
        instruments = np.convolve(white, b, mode='same')
    else:
        instruments = rng.normal(0, 1, total_samples)

    # Scale to noise floor level
    noise_amplitude = 10 ** (bed.noise_floor_db / 20.0)
    instruments = instruments * noise_amplitude

    # Add transients
    for transient in (bed.transients or []):
        t_ms = transient['t_ms']
        level_db = transient['level_db']
        dur_ms = transient['dur_ms']

        start_sample = int(t_ms / 1000.0 * sr)
        dur_samples = int(dur_ms / 1000.0 * sr)
        end_sample = min(start_sample + dur_samples, total_samples)

        # Generate short burst
        if end_sample > start_sample:
            burst_len = end_sample - start_sample
            burst = rng.normal(0, 1, burst_len)
            burst_amplitude = 10 ** (level_db / 20.0)
            burst = burst * burst_amplitude
            instruments[start_sample:end_sample] += burst

    return instruments.astype(np.float32)


def _normalize_peak(signal: np.ndarray, peak: float = 0.9) -> np.ndarray:
    """Normalize signal to peak amplitude."""
    max_val = np.max(np.abs(signal))
    if max_val > 0:
        return signal / max_val * peak
    return signal