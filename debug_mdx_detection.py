"""
Debug script for MDX onset detection.
Tests the Alcazar - Don't You Want Me song and visualizes the detection process.

Expected gap: ~35280ms (35.28 seconds)
Current detection: ~820ms (incorrect - too early)

This script will:
1. Load the audio file
2. Run Demucs separation
3. Compute RMS values over time
4. Show noise floor, thresholds, and detection points
5. Plot the results for visual inspection
"""

import os
import sys
import numpy as np
import torch
import torchaudio
from demucs.apply import apply_model
from demucs.pretrained import get_model
import matplotlib.pyplot as plt

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Test file (adjust path if needed)
# Auto-detect the correct path with any apostrophe variation
import glob
base_dir = r"Z:\UltraStarDeluxe\Songs\usdb.animux.de"
# Try multiple apostrophe variations
possible_paths = [
    r"Z:\UltraStarDeluxe\Songs\usdb.animux.de\Alcazar - Don't You Want Me\Alcazar - Don't You Want Me.mp3",
    r"Z:\UltraStarDeluxe\Songs\usdb.animux.de\Alcazar - Don't You Want Me\Alcazar - Don't You Want Me.mp3",
    r"Z:\UltraStarDeluxe\Songs\usdb.animux.de\Alcazar - Dont You Want Me\Alcazar - Dont You Want Me.mp3",
]

# Try to find the file using glob pattern
AUDIO_FILE = None
for path in possible_paths:
    if os.path.exists(path):
        AUDIO_FILE = path
        break

# If still not found, try glob pattern
if AUDIO_FILE is None:
    pattern = os.path.join(base_dir, "Alcazar*Want Me", "*.mp3")
    matches = glob.glob(pattern)
    if matches:
        AUDIO_FILE = matches[0]

if AUDIO_FILE is None:
    AUDIO_FILE = possible_paths[0]  # Fallback to first option

EXPECTED_GAP_MS = 35280  # From original gap value

# Detection parameters (matching MDX provider)
CHUNK_DURATION_MS = 12000
CHUNK_OVERLAP_MS = 6000
FRAME_DURATION_MS = 25
HOP_DURATION_MS = 10
NOISE_FLOOR_DURATION_MS = 800
ONSET_SNR_THRESHOLD = 6.0
ONSET_ABS_THRESHOLD = 0.02
MIN_VOICED_DURATION_MS = 500
HYSTERESIS_MS = 200
NUM_CHUNKS_TO_SCAN = 4  # Scan first 4 chunks (up to ~42s)


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


def main():
    print("=" * 80)
    print("MDX ONSET DETECTION DEBUG SCRIPT")
    print("=" * 80)
    print(f"Audio file: {AUDIO_FILE}")
    print(f"Expected gap: {EXPECTED_GAP_MS}ms ({EXPECTED_GAP_MS/1000:.1f}s)")
    print()
    
    # Check if file exists
    if not os.path.exists(AUDIO_FILE):
        print(f"ERROR: Audio file not found!")
        print(f"Checked path: {AUDIO_FILE}")
        print(f"Path exists check: {os.path.exists(AUDIO_FILE)}")
        
        # Try to find the file
        base_dir = r"Z:\UltraStarDeluxe\Songs\usdb.animux.de"
        print(f"\nTrying to locate the file...")
        print(f"Base directory exists: {os.path.exists(base_dir)}")
        
        if os.path.exists(base_dir):
            print(f"\nSearching for 'Alcazar' folders in {base_dir}...")
            try:
                for item in os.listdir(base_dir):
                    if 'Alcazar' in item and 'Want Me' in item:
                        folder_path = os.path.join(base_dir, item)
                        print(f"  Found folder: {item}")
                        if os.path.isdir(folder_path):
                            print(f"  Contents:")
                            for file in os.listdir(folder_path):
                                if file.endswith('.mp3'):
                                    print(f"    - {file}")
            except Exception as e:
                print(f"  Error listing directory: {e}")
        
        print(f"\nPlease update AUDIO_FILE path in the script.")
        return
    
    # Load audio
    print("Loading audio...")
    waveform, sample_rate = torchaudio.load(AUDIO_FILE)
    duration_s = waveform.shape[1] / sample_rate
    print(f"✓ Loaded: {duration_s:.1f}s, {sample_rate}Hz, {waveform.shape[0]} channels")
    print()
    
    # Convert to stereo if needed
    if waveform.shape[0] == 1:
        waveform = waveform.repeat(2, 1)
    
    # Load Demucs model
    print("Loading Demucs model...")
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f"Using device: {device}")
    model = get_model('htdemucs')
    model.to(device)
    model.eval()
    print("✓ Model loaded")
    print()
    
    # Scan multiple chunks to find vocals
    chunk_duration_s = CHUNK_DURATION_MS / 1000.0
    chunk_overlap_s = CHUNK_OVERLAP_MS / 1000.0
    chunk_hop_s = chunk_duration_s - chunk_overlap_s
    
    all_rms_values = []
    all_rms_times = []
    onset_ms = None
    onset_chunk = None
    
    print(f"Scanning first {NUM_CHUNKS_TO_SCAN} chunks (up to {NUM_CHUNKS_TO_SCAN * chunk_hop_s + chunk_duration_s - chunk_hop_s:.1f}s)...")
    print()
    
    for chunk_num in range(NUM_CHUNKS_TO_SCAN):
        chunk_start_s = chunk_num * chunk_hop_s
        chunk_samples = int(chunk_duration_s * sample_rate)
        chunk_start_sample = int(chunk_start_s * sample_rate)
        chunk_end_sample = min(chunk_start_sample + chunk_samples, waveform.shape[1])
        
        if chunk_start_sample >= waveform.shape[1]:
            break
        
        print(f"Processing chunk {chunk_num + 1}/{NUM_CHUNKS_TO_SCAN} ({chunk_start_s:.1f}s - {chunk_end_sample/sample_rate:.1f}s)...")
        chunk_waveform = waveform[:, chunk_start_sample:chunk_end_sample]
        
        # Separate vocals
        print("  Running Demucs separation...")
        with torch.no_grad():
            chunk_gpu = chunk_waveform.to(device)
            sources = apply_model(model, chunk_gpu.unsqueeze(0), device=device)
            vocals = sources[0, 3].cpu().numpy()  # vocals channel
        print("  ✓ Vocals separated")
        
        # Convert to mono
        vocals_mono = np.mean(vocals, axis=0)
        
        # Compute RMS
        frame_samples = int((FRAME_DURATION_MS / 1000.0) * sample_rate)
        hop_samples = int((HOP_DURATION_MS / 1000.0) * sample_rate)
        rms_values = compute_rms(vocals_mono, frame_samples, hop_samples)
        
        # Convert frame indices to absolute time
        rms_times_ms = (chunk_start_s * 1000) + np.arange(len(rms_values)) * HOP_DURATION_MS
        
        all_rms_values.extend(rms_values)
        all_rms_times.extend(rms_times_ms)
        
        # Detect onset in this chunk
        noise_floor_frames = int((NOISE_FLOOR_DURATION_MS / 1000.0) / (HOP_DURATION_MS / 1000.0))
        noise_floor, noise_sigma = estimate_noise_floor(rms_values, noise_floor_frames)
        
        snr_threshold = noise_floor + ONSET_SNR_THRESHOLD * noise_sigma
        combined_threshold = max(snr_threshold, ONSET_ABS_THRESHOLD)
        
        print(f"  Noise floor={noise_floor:.6f}, sigma={noise_sigma:.6f}")
        print(f"  SNR threshold={snr_threshold:.6f}, Abs threshold={ONSET_ABS_THRESHOLD:.6f}")
        print(f"  Combined threshold={combined_threshold:.6f}, Max RMS={np.max(rms_values):.6f}")
        
        # Find onset
        above_threshold = rms_values > combined_threshold
        min_frames = int((MIN_VOICED_DURATION_MS / 1000.0) / (HOP_DURATION_MS / 1000.0))
        hysteresis_frames = int((HYSTERESIS_MS / 1000.0) / (HOP_DURATION_MS / 1000.0))
        search_start = max(noise_floor_frames + 1, 0)
        
        onset_frame = None
        for i in range(search_start, len(above_threshold) - min_frames):
            if np.all(above_threshold[i:i+min_frames]):
                onset_frame = i
                for j in range(i - 1, max(search_start - 1, i - hysteresis_frames - 1), -1):
                    if j >= 0 and above_threshold[j]:
                        onset_frame = j
                    else:
                        break
                break
        
        if onset_frame is not None:
            onset_ms = rms_times_ms[onset_frame]
            onset_chunk = chunk_num + 1
            onset_rms = rms_values[onset_frame]
            print(f"  ✓ ONSET DETECTED at {onset_ms:.1f}ms (RMS={onset_rms:.6f})")
            print()
            break
        else:
            print(f"  No onset detected in this chunk")
        print()
    
    # Convert lists to numpy arrays for plotting
    all_rms_values = np.array(all_rms_values)
    all_rms_times = np.array(all_rms_times)
    
    print("=" * 80)
    print("DETECTION SUMMARY")
    
    print("=" * 80)
    print("DETECTION SUMMARY")
    print("=" * 80)
    
    if onset_ms is not None:
        print(f"✓ Onset detected at: {onset_ms:.1f}ms ({onset_ms/1000:.2f}s) in chunk {onset_chunk}")
        print(f"  Expected gap:       {EXPECTED_GAP_MS}ms ({EXPECTED_GAP_MS/1000:.1f}s)")
        print(f"  Difference:         {abs(onset_ms - EXPECTED_GAP_MS):.1f}ms ({'TOO EARLY' if onset_ms < EXPECTED_GAP_MS else 'TOO LATE'})")
    else:
        print(f"✗ No onset detected in first {NUM_CHUNKS_TO_SCAN} chunks")
        print(f"  Scanned up to:      {all_rms_times[-1]/1000:.1f}s")
        print(f"  Expected gap:       {EXPECTED_GAP_MS}ms ({EXPECTED_GAP_MS/1000:.1f}s)")
        if all_rms_times[-1] < EXPECTED_GAP_MS:
            print(f"  NOTE: Expected gap is BEYOND scanned region!")
            print(f"        Increase NUM_CHUNKS_TO_SCAN to reach it")
    print()
    
    # Frame-by-frame analysis
    print("FRAME-BY-FRAME ANALYSIS:")
    print()
    
    if onset_frame is not None:
        print(f"Around detected onset ({onset_ms:.0f}ms):")
        start_frame = max(0, onset_frame - 10)
        end_frame = min(len(rms_values), onset_frame + 10)
        for i in range(start_frame, end_frame):
            t_ms = i * HOP_DURATION_MS
            rms = rms_values[i]
            above = "✓" if rms > combined_threshold else " "
            marker = " ← ONSET" if i == onset_frame else ""
            print(f"  {above} Frame {i:4d}: {t_ms:7.1f}ms  RMS={rms:.6f}{marker}")
        print()
    
    # Check around expected gap
    expected_frame = int(EXPECTED_GAP_MS / HOP_DURATION_MS)
    if expected_frame < len(rms_values):
        print(f"Around expected gap ({EXPECTED_GAP_MS}ms):")
        start_frame = max(0, expected_frame - 10)
        end_frame = min(len(rms_values), expected_frame + 10)
        for i in range(start_frame, end_frame):
            t_ms = i * HOP_DURATION_MS
            rms = rms_values[i]
            above = "✓" if rms > combined_threshold else " "
            marker = " ← EXPECTED" if abs(t_ms - EXPECTED_GAP_MS) < HOP_DURATION_MS else ""
            print(f"  {above} Frame {i:4d}: {t_ms:7.1f}ms  RMS={rms:.6f}{marker}")
    else:
        print(f"Expected gap ({EXPECTED_GAP_MS}ms) is in chunk 2 or later")
    print()
    
    # Plot results
    print("Generating plot...")
    plt.style.use('dark_background')  # Dark theme
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 10))
    
    # Plot 1: All scanned chunks
    ax1.plot(np.array(all_rms_times) / 1000, all_rms_values, linewidth=0.8, label='RMS Energy', color='cyan')
    ax1.axhline(y=ONSET_ABS_THRESHOLD, color='red', linestyle='--', linewidth=2, label=f'Absolute Threshold ({ONSET_ABS_THRESHOLD:.4f})')
    
    if onset_ms is not None:
        ax1.axvline(x=onset_ms / 1000, color='lime', linestyle='-', linewidth=2, label=f'Detected Onset ({onset_ms:.0f}ms)')
    
    if EXPECTED_GAP_MS < all_rms_times[-1]:
        ax1.axvline(x=EXPECTED_GAP_MS / 1000, color='yellow', linestyle='--', linewidth=2, label=f'Expected Gap ({EXPECTED_GAP_MS}ms)')
    
    ax1.set_xlabel('Time (seconds)', fontsize=12)
    ax1.set_ylabel('RMS Energy', fontsize=12)
    ax1.set_title(f'MDX Onset Detection - First {NUM_CHUNKS_TO_SCAN} Chunks (0-{all_rms_times[-1]/1000:.1f}s)', fontsize=14)
    ax1.legend(loc='upper right', fontsize=10)
    ax1.grid(True, alpha=0.3)
    
    # Plot 2: Zoomed view around expected gap
    if EXPECTED_GAP_MS < all_rms_times[-1]:
        zoom_start_ms = max(0, EXPECTED_GAP_MS - 5000)
        zoom_end_ms = min(all_rms_times[-1], EXPECTED_GAP_MS + 5000)
        zoom_mask = (np.array(all_rms_times) >= zoom_start_ms) & (np.array(all_rms_times) <= zoom_end_ms)
        
        ax2.plot(np.array(all_rms_times)[zoom_mask] / 1000, np.array(all_rms_values)[zoom_mask], 
                linewidth=1.5, label='RMS Energy', color='cyan')
        ax2.axhline(y=ONSET_ABS_THRESHOLD, color='red', linestyle='--', linewidth=2, label=f'Threshold ({ONSET_ABS_THRESHOLD:.4f})')
        ax2.axvline(x=EXPECTED_GAP_MS / 1000, color='yellow', linestyle='--', linewidth=2, label=f'Expected ({EXPECTED_GAP_MS}ms)')
        
        if onset_ms is not None and zoom_start_ms <= onset_ms <= zoom_end_ms:
            ax2.axvline(x=onset_ms / 1000, color='lime', linestyle='-', linewidth=2, label=f'Detected ({onset_ms:.0f}ms)')
        
        ax2.set_xlabel('Time (seconds)', fontsize=12)
        ax2.set_ylabel('RMS Energy', fontsize=12)
        ax2.set_title(f'Zoomed View: ±5s Around Expected Gap', fontsize=14)
        ax2.legend(loc='upper right', fontsize=10)
        ax2.grid(True, alpha=0.3)
    else:
        ax2.text(0.5, 0.5, f'Expected gap ({EXPECTED_GAP_MS}ms) is beyond scanned region\nIncrease NUM_CHUNKS_TO_SCAN',
                ha='center', va='center', fontsize=14, color='yellow')
        ax2.set_xlim(0, 1)
        ax2.set_ylim(0, 1)
    
    plt.tight_layout()
    
    # Save plot
    plot_file = "mdx_detection_debug.png"
    plt.savefig(plot_file, dpi=150)
    print(f"✓ Plot saved to: {plot_file}")
    
    # Show plot
    plt.show()
    
    print()
    print("=" * 80)
    print("DEBUG COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
