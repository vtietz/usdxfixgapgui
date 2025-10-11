"""
Bidirectional vocal onset detection with confidence scoring.

This algorithm searches for the vocal onset by:
1. Starting at an expected gap position (can be wrong)
2. Expanding search radius in both directions
3. Scoring each candidate based on:
   - RMS energy level
   - Sustained duration
   - Signal-to-noise ratio
   - Energy rise steepness
4. Returning the highest confidence detection

This approach works for vocals at the beginning, middle, or end of a song.
"""

import os
import sys
import numpy as np
import torch
import torchaudio
from demucs.apply import apply_model
from demucs.pretrained import get_model
import matplotlib.pyplot as plt
from typing import List, Tuple, Optional

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Test file - auto-detect
import glob
base_dir = r"Z:\UltraStarDeluxe\Songs\usdb.animux.de"
possible_paths = [
    r"Z:\UltraStarDeluxe\Songs\usdb.animux.de\Alcazar - Don't You Want Me\Alcazar - Don't You Want Me.mp3",
    r"Z:\UltraStarDeluxe\Songs\usdb.animux.de\Alcazar - Don't You Want Me\Alcazar - Don't You Want Me.mp3",
    r"Z:\UltraStarDeluxe\Songs\usdb.animux.de\Alcazar - Dont You Want Me\Alcazar - Dont You Want Me.mp3",
]

AUDIO_FILE = None
for path in possible_paths:
    if os.path.exists(path):
        AUDIO_FILE = path
        break

if AUDIO_FILE is None:
    pattern = os.path.join(base_dir, "Alcazar*Want Me", "*.mp3")
    matches = glob.glob(pattern)
    if matches:
        AUDIO_FILE = matches[0]

if AUDIO_FILE is None:
    AUDIO_FILE = possible_paths[0]

# Algorithm parameters
EXPECTED_GAP_MS = 35280  # Initial guess (can be wrong!)
SEARCH_RADIUS_INITIAL_MS = 5000  # Start with ±5 seconds
SEARCH_RADIUS_INCREMENT_MS = 5000  # Expand by 5 seconds each iteration
MAX_SEARCH_ITERATIONS = 8  # Up to ±40 seconds from expected
CHUNK_DURATION_MS = 12000
FRAME_DURATION_MS = 25
HOP_DURATION_MS = 10
NOISE_FLOOR_DURATION_MS = 800

# Onset detection thresholds
ONSET_ABS_THRESHOLD = 0.02
ONSET_SNR_THRESHOLD = 6.0
MIN_VOICED_DURATION_MS = 500
HYSTERESIS_MS = 200

# Confidence scoring weights
WEIGHT_ENERGY = 0.3
WEIGHT_DURATION = 0.25
WEIGHT_SNR = 0.25
WEIGHT_RISE = 0.20


class OnsetCandidate:
    """Represents a potential vocal onset with confidence score."""
    
    def __init__(self, time_ms: float, rms: float, duration_ms: float, snr: float, rise: float):
        self.time_ms = time_ms
        self.rms = rms
        self.duration_ms = duration_ms
        self.snr = snr
        self.rise = rise
        self.confidence = self._calculate_confidence()
    
    def _calculate_confidence(self) -> float:
        """Calculate confidence score (0-1) based on multiple factors."""
        # Normalize each factor to 0-1 range
        energy_score = min(1.0, self.rms / 0.05)  # Max at 0.05 RMS
        duration_score = min(1.0, self.duration_ms / 2000)  # Max at 2 seconds
        snr_score = min(1.0, self.snr / 20)  # Max at 20 dB SNR
        rise_score = min(1.0, self.rise / 0.01)  # Max at 0.01 rise rate
        
        # Weighted combination
        confidence = (
            WEIGHT_ENERGY * energy_score +
            WEIGHT_DURATION * duration_score +
            WEIGHT_SNR * snr_score +
            WEIGHT_RISE * rise_score
        )
        
        return confidence
    
    def __repr__(self):
        return (f"OnsetCandidate(time={self.time_ms:.0f}ms, rms={self.rms:.4f}, "
                f"duration={self.duration_ms:.0f}ms, snr={self.snr:.1f}dB, "
                f"rise={self.rise:.5f}, confidence={self.confidence:.3f})")


def compute_rms(audio, frame_samples, hop_samples):
    """Compute RMS energy in sliding windows."""
    num_frames = (len(audio) - frame_samples) // hop_samples + 1
    rms_values = np.zeros(num_frames)
    
    for i in range(num_frames):
        start = i * hop_samples
        end = start + frame_samples
        if end <= len(audio):
            frame = audio[start:end]
            rms_values[i] = np.sqrt(np.mean(frame**2))
    
    return rms_values


def estimate_noise_floor(rms_values, noise_floor_frames):
    """Estimate noise floor from initial frames."""
    noise_region = rms_values[:noise_floor_frames]
    noise_floor = np.mean(noise_region)
    noise_sigma = np.std(noise_region)
    return noise_floor, noise_sigma


def detect_onsets_in_chunk(
    vocals_mono: np.ndarray,
    sample_rate: int,
    chunk_start_ms: float,
    frame_duration_ms: float,
    hop_duration_ms: float
) -> List[OnsetCandidate]:
    """
    Detect all vocal onsets in a chunk and return candidates with confidence scores.
    """
    candidates = []
    
    # Compute RMS
    frame_samples = int((frame_duration_ms / 1000.0) * sample_rate)
    hop_samples = int((hop_duration_ms / 1000.0) * sample_rate)
    rms_values = compute_rms(vocals_mono, frame_samples, hop_samples)
    
    if len(rms_values) == 0:
        return candidates
    
    # Estimate noise floor
    noise_floor_frames = int((NOISE_FLOOR_DURATION_MS / 1000.0) / (hop_duration_ms / 1000.0))
    noise_floor, noise_sigma = estimate_noise_floor(rms_values, min(noise_floor_frames, len(rms_values)))
    
    # Compute thresholds
    snr_threshold = noise_floor + ONSET_SNR_THRESHOLD * noise_sigma
    combined_threshold = max(snr_threshold, ONSET_ABS_THRESHOLD)
    
    # Find all sustained energy regions
    above_threshold = rms_values > combined_threshold
    min_frames = int((MIN_VOICED_DURATION_MS / 1000.0) / (hop_duration_ms / 1000.0))
    hysteresis_frames = int((HYSTERESIS_MS / 1000.0) / (hop_duration_ms / 1000.0))
    search_start = max(noise_floor_frames + 1, 0)
    
    i = search_start
    while i < len(above_threshold) - min_frames:
        # Check if we have sustained energy
        if np.all(above_threshold[i:i+min_frames]):
            # Found sustained region - find onset with hysteresis
            onset_frame = i
            for j in range(i - 1, max(search_start - 1, i - hysteresis_frames - 1), -1):
                if j >= 0 and above_threshold[j]:
                    onset_frame = j
                else:
                    break
            
            # Calculate duration of sustained vocals
            duration_frames = min_frames
            for j in range(i + min_frames, len(above_threshold)):
                if above_threshold[j]:
                    duration_frames += 1
                else:
                    break
            
            # Calculate metrics for this candidate
            onset_ms = chunk_start_ms + (onset_frame * hop_duration_ms)
            rms_at_onset = rms_values[onset_frame]
            duration_ms = duration_frames * hop_duration_ms
            
            # SNR calculation
            if noise_sigma > 0:
                snr_db = 20 * np.log10((rms_at_onset - noise_floor) / noise_sigma) if rms_at_onset > noise_floor else 0
            else:
                snr_db = 0
            
            # Energy rise calculation (derivative before onset)
            rise = 0
            if onset_frame > 5:
                pre_onset_window = rms_values[max(0, onset_frame-10):onset_frame]
                if len(pre_onset_window) > 1:
                    rise = np.max(np.diff(pre_onset_window))
            
            candidate = OnsetCandidate(
                time_ms=onset_ms,
                rms=rms_at_onset,
                duration_ms=duration_ms,
                snr=snr_db,
                rise=rise
            )
            
            candidates.append(candidate)
            
            # Skip past this detected region
            i += duration_frames
        else:
            i += 1
    
    return candidates


def bidirectional_search(
    waveform: torch.Tensor,
    sample_rate: int,
    model,
    device: str,
    expected_gap_ms: float
) -> Tuple[Optional[OnsetCandidate], List[OnsetCandidate]]:
    """
    Search for vocal onset bidirectionally from expected gap position.
    Strategy: Find the FIRST vocal onset (closest to expected gap), not the loudest.
    
    Returns:
        (first_onset, all_candidates)
    """
    all_candidates = []
    
    chunk_duration_s = CHUNK_DURATION_MS / 1000.0
    total_duration_s = waveform.shape[1] / sample_rate
    
    print(f"Starting bidirectional search from {expected_gap_ms}ms ({expected_gap_ms/1000:.1f}s)")
    print(f"Audio duration: {total_duration_s:.1f}s")
    print(f"Strategy: Find FIRST vocal onset (where vocals START), not loudest")
    print()
    
    for iteration in range(MAX_SEARCH_ITERATIONS):
        radius_ms = SEARCH_RADIUS_INITIAL_MS + (iteration * SEARCH_RADIUS_INCREMENT_MS)
        search_start_ms = max(0, expected_gap_ms - radius_ms)
        search_end_ms = min(total_duration_s * 1000, expected_gap_ms + radius_ms)
        
        print(f"Iteration {iteration + 1}/{MAX_SEARCH_ITERATIONS}: Searching {search_start_ms/1000:.1f}s - {search_end_ms/1000:.1f}s (±{radius_ms/1000:.1f}s)")
        
        # Process chunks in this search window
        chunk_start_s = search_start_ms / 1000.0
        while chunk_start_s < search_end_ms / 1000.0:
            chunk_start_sample = int(chunk_start_s * sample_rate)
            chunk_end_sample = min(chunk_start_sample + int(chunk_duration_s * sample_rate), waveform.shape[1])
            
            if chunk_start_sample >= waveform.shape[1]:
                break
            
            chunk_waveform = waveform[:, chunk_start_sample:chunk_end_sample]
            
            # Separate vocals
            with torch.no_grad():
                chunk_gpu = chunk_waveform.to(device)
                sources = apply_model(model, chunk_gpu.unsqueeze(0), device=device)
                vocals = sources[0, 3].cpu().numpy()
            
            vocals_mono = np.mean(vocals, axis=0)
            
            # Detect onsets in this chunk
            chunk_candidates = detect_onsets_in_chunk(
                vocals_mono, sample_rate, chunk_start_s * 1000,
                FRAME_DURATION_MS, HOP_DURATION_MS
            )
            
            for candidate in chunk_candidates:
                # Only add if not already detected in previous iteration
                is_new = True
                for existing in all_candidates:
                    if abs(candidate.time_ms - existing.time_ms) < 1000:  # Within 1 second
                        is_new = False
                        break
                
                if is_new:
                    all_candidates.append(candidate)
                    print(f"  Found vocal onset: {candidate.time_ms:.0f}ms (RMS={candidate.rms:.4f}, duration={candidate.duration_ms:.0f}ms)")
            
            # Move to next chunk (with 50% overlap)
            chunk_start_s += chunk_duration_s / 2
        
        # After each iteration, check if we found any candidates
        # Return the one CLOSEST to expected gap (first vocal start)
        if all_candidates:
            # Sort by distance from expected gap
            sorted_by_distance = sorted(all_candidates, key=lambda c: abs(c.time_ms - expected_gap_ms))
            closest = sorted_by_distance[0]
            
            print(f"\n✓ Found {len(all_candidates)} vocal onset(s)")
            print(f"  Closest to expected gap: {closest.time_ms:.0f}ms (distance: {abs(closest.time_ms - expected_gap_ms):.0f}ms)")
            
            # If closest is within reasonable range, accept it
            if abs(closest.time_ms - expected_gap_ms) < radius_ms:
                print(f"✓ Accepting this as vocal start position (within ±{radius_ms/1000:.1f}s search radius)")
                return closest, all_candidates
        
        print()
    
    # If we scanned everything and found candidates, return the earliest one
    if all_candidates:
        earliest = min(all_candidates, key=lambda c: c.time_ms)
        print(f"✓ Returning earliest vocal onset found: {earliest.time_ms:.0f}ms")
        return earliest, all_candidates
    else:
        return None, []


def main():
    print("=" * 80)
    print("BIDIRECTIONAL VOCAL ONSET DETECTION")
    print("=" * 80)
    print(f"Audio file: {AUDIO_FILE}")
    print(f"Expected gap (initial guess): {EXPECTED_GAP_MS}ms ({EXPECTED_GAP_MS/1000:.1f}s)")
    print()
    
    # Check file
    if not os.path.exists(AUDIO_FILE):
        print("ERROR: Audio file not found!")
        return
    
    # Load audio
    print("Loading audio...")
    waveform, sample_rate = torchaudio.load(AUDIO_FILE)
    duration_s = waveform.shape[1] / sample_rate
    print(f"✓ Loaded: {duration_s:.1f}s, {sample_rate}Hz")
    print()
    
    if waveform.shape[0] == 1:
        waveform = waveform.repeat(2, 1)
    
    # Load model
    print("Loading Demucs model...")
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f"Using device: {device}")
    model = get_model('htdemucs')
    model.to(device)
    model.eval()
    print("✓ Model loaded")
    print()
    
    # Perform bidirectional search
    best_candidate, all_candidates = bidirectional_search(
        waveform, sample_rate, model, device, EXPECTED_GAP_MS
    )
    
    print("=" * 80)
    print("DETECTION RESULTS")
    print("=" * 80)
    
    if best_candidate:
        print(f"✓ VOCAL START DETECTED:")
        print(f"  Time:       {best_candidate.time_ms:.0f}ms ({best_candidate.time_ms/1000:.2f}s)")
        print(f"  RMS:        {best_candidate.rms:.4f}")
        print(f"  Duration:   {best_candidate.duration_ms:.0f}ms")
        print(f"  SNR:        {best_candidate.snr:.1f}dB")
        print()
        print(f"  Expected:   {EXPECTED_GAP_MS}ms ({EXPECTED_GAP_MS/1000:.2f}s)")
        print(f"  Difference: {best_candidate.time_ms - EXPECTED_GAP_MS:+.0f}ms ({(best_candidate.time_ms - EXPECTED_GAP_MS)/1000:+.2f}s)")
        print()
        
        if len(all_candidates) > 1:
            print(f"Other vocal onsets found ({len(all_candidates) - 1}):")
            sorted_candidates = sorted(all_candidates, key=lambda c: c.time_ms)
            for i, candidate in enumerate(sorted_candidates, 1):
                if candidate.time_ms != best_candidate.time_ms:
                    marker = "  "
                    if candidate.time_ms == best_candidate.time_ms:
                        marker = "→ "
                    print(f"{marker}#{i}: {candidate.time_ms:.0f}ms ({candidate.time_ms/1000:.2f}s), RMS={candidate.rms:.4f}, duration={candidate.duration_ms:.0f}ms")
    else:
        print("✗ No vocal onset detected")
    
    print()
    print("=" * 80)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
