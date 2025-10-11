"""
Voice Activity Detection (VAD) utilities using WebRTC VAD.
Detects speech segments in audio files for vocal onset detection.
"""

import logging
import os
import struct
import tempfile
from typing import List, Tuple, Optional
import wave

logger = logging.getLogger(__name__)

try:
    import webrtcvad
    WEBRTCVAD_AVAILABLE = True
except ImportError:
    WEBRTCVAD_AVAILABLE = False
    logger.warning("webrtcvad not available. VAD functionality will be limited.")


def convert_to_pcm_wav(audio_file: str, sample_rate: int = 16000) -> str:
    """
    Convert audio file to PCM WAV format suitable for VAD.
    Applies vocal-range band-pass filter to reduce music bias.
    
    Args:
        audio_file: Path to input audio file
        sample_rate: Target sample rate (8000, 16000, or 32000 for WebRTC VAD)
        
    Returns:
        Path to converted PCM WAV file
    """
    from utils.cancellable_process import run_cancellable_process
    
    temp_dir = os.path.dirname(audio_file)
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='_vad.wav', dir=temp_dir).name
    
    # Convert to mono PCM WAV with vocal-range band-pass filter
    # highpass=80Hz removes low-frequency rumble and bass
    # lowpass=8000Hz removes high-frequency noise and focuses on vocal range
    command = [
        'ffmpeg', '-y', '-i', audio_file,
        '-acodec', 'pcm_s16le',  # 16-bit PCM
        '-ac', '1',               # Mono
        '-ar', str(sample_rate),  # Sample rate
        '-af', 'highpass=f=80,lowpass=f=8000',  # Vocal-range band-pass filter
        temp_file
    ]
    
    returncode, stdout, stderr = run_cancellable_process(command, None)
    
    if returncode != 0:
        if os.path.exists(temp_file):
            os.remove(temp_file)
        raise Exception(f"Failed to convert audio to PCM WAV: {stderr}")
    
    return temp_file


def read_wave_frames(wav_file: str, frame_duration_ms: int) -> Tuple[int, List[bytes]]:
    """
    Read audio frames from WAV file.
    
    Args:
        wav_file: Path to PCM WAV file
        frame_duration_ms: Duration of each frame in milliseconds
        
    Returns:
        Tuple of (sample_rate, list of audio frames as bytes)
    """
    with wave.open(wav_file, 'rb') as wf:
        sample_rate = wf.getframerate()
        n_channels = wf.getnchannels()
        sample_width = wf.getsampwidth()
        
        if n_channels != 1:
            raise ValueError(f"Audio must be mono, got {n_channels} channels")
        if sample_width != 2:
            raise ValueError(f"Audio must be 16-bit, got {sample_width * 8}-bit")
        if sample_rate not in [8000, 16000, 32000]:
            raise ValueError(f"Sample rate must be 8000, 16000, or 32000 Hz, got {sample_rate}")
        
        # Calculate frame size in samples
        frame_size = int(sample_rate * frame_duration_ms / 1000)
        frame_bytes = frame_size * sample_width
        
        frames = []
        while True:
            frame_data = wf.readframes(frame_size)
            if len(frame_data) < frame_bytes:
                # Pad last frame if needed
                if len(frame_data) > 0:
                    frame_data += b'\x00' * (frame_bytes - len(frame_data))
                    frames.append(frame_data)
                break
            frames.append(frame_data)
    
    return sample_rate, frames


def merge_speech_segments(
    speech_frames: List[Tuple[int, bool]], 
    frame_duration_ms: int,
    min_speech_ms: int = 120,
    min_silence_ms: int = 200
) -> List[Tuple[float, float]]:
    """
    Merge consecutive speech frames into segments, filtering by duration.
    
    Args:
        speech_frames: List of (frame_index, is_speech) tuples
        frame_duration_ms: Duration of each frame in milliseconds
        min_speech_ms: Minimum speech segment duration to keep
        min_silence_ms: Minimum silence duration to split segments
        
    Returns:
        List of (start_ms, end_ms) tuples for speech segments
    """
    if not speech_frames:
        return []
    
    segments = []
    current_start = None
    silence_start = None
    
    for frame_idx, is_speech in speech_frames:
        time_ms = frame_idx * frame_duration_ms
        
        if is_speech:
            if current_start is None:
                # Start new speech segment
                current_start = time_ms
                silence_start = None
            elif silence_start is not None:
                # Check if silence gap was long enough to split
                silence_duration = time_ms - silence_start
                if silence_duration >= min_silence_ms:
                    # End previous segment and start new one
                    end_ms = silence_start
                    if (end_ms - current_start) >= min_speech_ms:
                        segments.append((current_start, end_ms))
                    current_start = time_ms
                silence_start = None
        else:
            if current_start is not None and silence_start is None:
                # Start tracking silence
                silence_start = time_ms
    
    # Handle final segment
    if current_start is not None:
        last_frame_idx = speech_frames[-1][0]
        end_ms = (last_frame_idx + 1) * frame_duration_ms
        if silence_start is not None and silence_start < end_ms:
            end_ms = silence_start
        if (end_ms - current_start) >= min_speech_ms:
            segments.append((current_start, end_ms))
    
    return segments


def detect_speech_segments_vad(
    audio_file: str,
    frame_duration_ms: int = 30,
    min_speech_ms: int = 120,
    min_silence_ms: int = 200,
    aggressiveness: int = 3,
    check_cancellation: Optional[callable] = None
) -> List[Tuple[float, float]]:
    """
    Detect speech segments using WebRTC VAD.
    
    Args:
        audio_file: Path to audio file
        frame_duration_ms: Frame duration (10, 20, or 30 ms)
        min_speech_ms: Minimum speech duration to keep
        min_silence_ms: Minimum silence duration to split segments
        aggressiveness: VAD aggressiveness (0-3, higher = more aggressive)
        check_cancellation: Optional cancellation check callback
        
    Returns:
        List of (start_ms, end_ms) tuples for detected speech segments
    """
    if not WEBRTCVAD_AVAILABLE:
        logger.error("webrtcvad not available, falling back to silence detection")
        from utils.audio import detect_silence_periods
        # Invert silence periods to speech periods
        silence_periods = detect_silence_periods(
            audio_file, 
            silence_detect_params="silencedetect=noise=-30dB:d=0.2",
            check_cancellation=check_cancellation
        )
        # This is a fallback - we'll need to invert or use a different approach
        # For now, return empty to indicate failure
        return []
    
    if frame_duration_ms not in [10, 20, 30]:
        raise ValueError(f"Frame duration must be 10, 20, or 30 ms, got {frame_duration_ms}")
    
    if aggressiveness not in [0, 1, 2, 3]:
        raise ValueError(f"Aggressiveness must be 0-3, got {aggressiveness}")
    
    logger.debug(f"Detecting speech segments in {audio_file} with VAD")
    
    # Convert to PCM WAV
    pcm_wav = convert_to_pcm_wav(audio_file, sample_rate=16000)
    
    try:
        # Read audio frames
        sample_rate, frames = read_wave_frames(pcm_wav, frame_duration_ms)
        
        # Initialize VAD
        vad = webrtcvad.Vad(aggressiveness)
        
        # Detect speech in each frame
        speech_frames = []
        for i, frame in enumerate(frames):
            if check_cancellation and check_cancellation():
                logger.info("VAD detection cancelled")
                return []
            
            try:
                is_speech = vad.is_speech(frame, sample_rate)
                speech_frames.append((i, is_speech))
            except Exception as e:
                logger.warning(f"VAD error on frame {i}: {e}")
                speech_frames.append((i, False))
        
        # Merge frames into segments
        segments = merge_speech_segments(
            speech_frames, 
            frame_duration_ms,
            min_speech_ms,
            min_silence_ms
        )
        
        logger.debug(f"Detected {len(segments)} speech segments")
        return segments
        
    finally:
        # Clean up temporary file
        if os.path.exists(pcm_wav):
            os.remove(pcm_wav)


def compute_vad_confidence(
    audio_file: str,
    time_ms: float,
    window_ms: int = 150,
    aggressiveness: int = 3
) -> float:
    """
    Compute VAD confidence at a specific time point.
    
    Args:
        audio_file: Path to audio file
        time_ms: Time point in milliseconds
        window_ms: Window around time_ms to analyze
        aggressiveness: VAD aggressiveness
        
    Returns:
        Confidence score 0.0-1.0 (percentage of frames detected as speech)
    """
    if not WEBRTCVAD_AVAILABLE:
        return 0.5  # Default confidence when VAD unavailable
    
    frame_duration_ms = 30
    pcm_wav = convert_to_pcm_wav(audio_file, sample_rate=16000)
    
    try:
        sample_rate, frames = read_wave_frames(pcm_wav, frame_duration_ms)
        vad = webrtcvad.Vad(aggressiveness)
        
        # Calculate frame range around target time
        target_frame = int(time_ms / frame_duration_ms)
        window_frames = int(window_ms / frame_duration_ms)
        start_frame = max(0, target_frame - window_frames // 2)
        end_frame = min(len(frames), target_frame + window_frames // 2)
        
        # Count speech frames in window
        speech_count = 0
        total_count = 0
        
        for i in range(start_frame, end_frame):
            if i < len(frames):
                try:
                    is_speech = vad.is_speech(frames[i], sample_rate)
                    if is_speech:
                        speech_count += 1
                    total_count += 1
                except Exception:
                    pass
        
        if total_count == 0:
            return 0.0
        
        confidence = speech_count / total_count
        logger.debug(f"VAD confidence at {time_ms}ms: {confidence:.2f}")
        return confidence
        
    finally:
        if os.path.exists(pcm_wav):
            os.remove(pcm_wav)
