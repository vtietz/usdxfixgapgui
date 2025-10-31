"""
Waveform visualization utilities for Tier-1 onset detection tests.

Creates compact .png previews showing waveform, ground-truth onset, and detected onset.
"""

import os
from typing import Optional

import matplotlib
import matplotlib.pyplot as plt
import numpy as np

# Use non-interactive backend for headless testing
matplotlib.use("Agg")


def save_waveform_preview(
    wave: np.ndarray,
    sr: int,
    title: str,
    truth_ms: float,
    detected_ms: Optional[float],
    out_path: str,
    rms_overlay: bool = True,
) -> str:
    """
    Save waveform preview with onset markers.

    Args:
        wave: Audio waveform (mono)
        sr: Sample rate
        title: Plot title
        truth_ms: Ground-truth onset time in milliseconds
        detected_ms: Detected onset time in milliseconds (None if not detected)
        out_path: Output file path
        rms_overlay: Whether to overlay RMS envelope

    Returns:
        Path to saved file
    """
    # Create output directory if needed
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    # Compute time axis
    duration_ms = len(wave) / sr * 1000.0
    time_ms = np.linspace(0, duration_ms, len(wave))

    # Downsample waveform for plotting (target ~1000 points)
    target_points = 1000
    if len(wave) > target_points:
        decimate_factor = len(wave) // target_points
        wave_plot = wave[::decimate_factor]
        time_plot = time_ms[::decimate_factor]
    else:
        wave_plot = wave
        time_plot = time_ms

    # Create figure
    fig, ax = plt.subplots(figsize=(10, 3))

    # Plot waveform
    ax.plot(time_plot, wave_plot, color="#2C3E50", alpha=0.6, linewidth=0.5, label="Waveform")

    # Plot RMS overlay if requested
    if rms_overlay:
        # Compute coarse RMS with 10 ms hop for display
        hop_ms = 10
        hop_samples = int(hop_ms / 1000.0 * sr)
        frame_samples = hop_samples * 2  # 20 ms frames

        num_frames = max(1, (len(wave) - frame_samples) // hop_samples + 1)
        rms_values = np.zeros(num_frames)
        rms_times = np.zeros(num_frames)

        for i in range(num_frames):
            start = i * hop_samples
            end = start + frame_samples
            if end <= len(wave):
                frame = wave[start:end]
                rms_values[i] = np.sqrt(np.mean(frame**2))
                rms_times[i] = start / sr * 1000.0

        # Plot RMS envelope
        ax.plot(rms_times, rms_values, color="#E74C3C", linewidth=1.5, label="RMS", alpha=0.8)

    # Plot ground-truth onset
    ax.axvline(truth_ms, color="#27AE60", linestyle="--", linewidth=2, label=f"Truth: {truth_ms:.1f}ms")

    # Plot detected onset
    if detected_ms is not None:
        error_ms = detected_ms - truth_ms
        ax.axvline(
            detected_ms,
            color="#3498DB",
            linestyle="-",
            linewidth=2,
            label=f"Detected: {detected_ms:.1f}ms (Δ{error_ms:+.1f}ms)",
        )
    else:
        ax.text(
            0.98,
            0.95,
            "NO DETECTION",
            transform=ax.transAxes,
            fontsize=10,
            color="#E74C3C",
            fontweight="bold",
            ha="right",
            va="top",
            bbox=dict(boxstyle="round", facecolor="white", alpha=0.8),
        )

    # Formatting
    ax.set_xlabel("Time (ms)", fontsize=10)
    ax.set_ylabel("Amplitude", fontsize=10)
    ax.set_title(title, fontsize=12, fontweight="bold")
    ax.legend(loc="upper left", fontsize=8, framealpha=0.9)
    ax.grid(True, alpha=0.3, linestyle=":", linewidth=0.5)
    ax.set_xlim(0, duration_ms)

    # Tight layout
    plt.tight_layout()

    # Save
    plt.savefig(out_path, dpi=100, bbox_inches="tight")
    plt.close(fig)

    return out_path


def save_pipeline_overview(
    audio_path: str,
    sr: int,
    truth_ms: float,
    detected_ms: Optional[float],
    out_path: str,
    confidence: Optional[float] = None,
) -> str:
    """
    Save pipeline-level waveform overview with truth/detected markers.

    Loads audio from file, extracts left channel (mixture), and plots with
    onset markers. Suitable for Tier-3 pipeline test artifacts.

    Args:
        audio_path: Path to stereo WAV file (L=mixture, R=vocals)
        sr: Sample rate (for time axis calculation)
        truth_ms: Ground-truth onset time in milliseconds
        detected_ms: Detected onset time in milliseconds (None if not detected)
        out_path: Output file path
        confidence: Optional confidence score to display

    Returns:
        Path to saved file
    """
    import torchaudio

    # Load audio and extract left channel (mixture)
    waveform, file_sr = torchaudio.load(audio_path)

    # Use left channel (mixture) for visualization
    if waveform.shape[0] >= 2:
        wave_mono = waveform[0, :].numpy()  # Left channel
    else:
        wave_mono = waveform[0, :].numpy()  # Mono fallback

    # Build title with confidence if provided
    title = f"Pipeline Overview: {os.path.basename(audio_path)}"
    if confidence is not None:
        title += f" (Confidence: {confidence:.2f})"

    # Reuse existing visualization function
    return save_waveform_preview(
        wave=wave_mono,
        sr=file_sr,
        title=title,
        truth_ms=truth_ms,
        detected_ms=detected_ms,
        out_path=out_path,
        rms_overlay=True,
    )
