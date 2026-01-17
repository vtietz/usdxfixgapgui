"""
Per-chunk onset detection pipeline for MDX scanner.

Coordinates audio loading, vocal separation, and onset detection for a single chunk.
Clear I/O boundaries - delegates actual processing to specialized modules.
"""

import logging
from typing import Optional, Callable
import torch
import torchaudio
import numpy as np

from utils.providers.mdx.separator import separate_vocals_chunk
from utils.providers.mdx.detection import detect_onset_in_vocal_chunk
from utils.providers.mdx.vocals_cache import VocalsCache
from utils.providers.mdx.config import MdxConfig
from utils.providers.mdx.scanner.chunk_iterator import ChunkBoundaries
from utils.providers.mdx.audio_compat import get_audio_info_compat, load_audio_compat

logger = logging.getLogger(__name__)


class OnsetDetectorPipeline:
    """
    Per-chunk onset detection pipeline.

    Responsibilities:
        1. Load audio chunk from file
        2. Separate vocals using Demucs (delegate to separator module)
        3. Detect onset in vocals (delegate to detection module)
        4. Cache vocals for potential reuse in confidence computation

    This class acts as the I/O boundary - it handles file loading and
    coordinates between modules, but delegates actual processing.

    Example:
        pipeline = OnsetDetectorPipeline(
            audio_file="song.mp3",
            model=demucs_model,
            device="cuda",
            config=mdx_config,
            vocals_cache=cache
        )

        onset_ms = pipeline.process_chunk(chunk_boundaries)
    """

    def __init__(self, audio_file: str, model, device: str, config: MdxConfig, vocals_cache: VocalsCache):
        """
        Initialize onset detector pipeline.

        Args:
            audio_file: Path to audio file
            model: Demucs model instance
            device: Device for processing ("cuda" or "cpu")
            config: MDX configuration
            vocals_cache: Cache for separated vocals
        """
        self.audio_file = audio_file
        self.model = model
        self.device = device
        self.config = config
        self.vocals_cache = vocals_cache

        # Get audio info once (handles M4A)
        info = get_audio_info_compat(audio_file)
        self.sample_rate = info.sample_rate
        self.num_frames = info.num_frames

    def process_chunk(
        self, chunk: ChunkBoundaries, check_cancellation: Optional[Callable[[], bool]] = None
    ) -> Optional[float]:
        """
        Process single chunk for onset detection.

        Args:
            chunk: Chunk boundaries to process
            check_cancellation: Callback returning True if cancelled

        Returns:
            Absolute onset timestamp in milliseconds, or None if not found
        """
        # Check cancellation
        if check_cancellation and check_cancellation():
            return None

        # Load audio chunk
        waveform = self._load_chunk(chunk)

        # Apply optional resampling for CPU speedup
        if self.config.resample_hz > 0 and self.sample_rate != self.config.resample_hz:
            waveform = torchaudio.functional.resample(waveform, self.sample_rate, self.config.resample_hz)
            current_sample_rate = self.config.resample_hz
        else:
            current_sample_rate = self.sample_rate

        # Separate vocals
        vocals = self._separate_vocals(waveform, current_sample_rate, check_cancellation)

        # Cache vocals for potential reuse
        self.vocals_cache.put(self.audio_file, chunk.start_ms, chunk.end_ms, vocals)

        # Detect onset in vocals
        onset_ms = self._detect_onset(vocals, current_sample_rate, chunk.start_ms)

        return onset_ms

    def _load_chunk(self, chunk: ChunkBoundaries) -> torch.Tensor:
        """
        Load audio chunk from file.

        Args:
            chunk: Chunk boundaries

        Returns:
            Stereo waveform tensor (2, samples)
        """
        # Calculate frame boundaries
        frame_offset = int(chunk.start_s * self.sample_rate)
        chunk_duration_s = (chunk.end_ms - chunk.start_ms) / 1000.0
        num_frames = min(int(chunk_duration_s * self.sample_rate), self.num_frames - frame_offset)

        # Load chunk (handles M4A)
        with load_audio_compat(self.audio_file, frame_offset=frame_offset, num_frames=num_frames) as (waveform, _):
            # Convert to stereo if needed
            if waveform.shape[0] == 1:
                waveform = waveform.repeat(2, 1)

            return waveform

    def _separate_vocals(
        self, waveform: torch.Tensor, sample_rate: int, check_cancellation: Optional[Callable[[], bool]] = None
    ) -> np.ndarray:
        """
        Separate vocals from waveform.

        Delegates to separator module.

        Args:
            waveform: Audio waveform tensor
            sample_rate: Sample rate
            check_cancellation: Cancellation callback

        Returns:
            Vocals-only numpy array
        """
        return separate_vocals_chunk(
            model=self.model,
            waveform=waveform,
            sample_rate=sample_rate,
            device=self.device,
            use_fp16=self.config.use_fp16,
            check_cancellation=check_cancellation,
        )

    def _detect_onset(self, vocal_audio: np.ndarray, sample_rate: int, chunk_start_ms: float) -> Optional[float]:
        """
        Detect onset in vocal audio.

        Delegates to detection module.

        Args:
            vocal_audio: Vocals numpy array
            sample_rate: Sample rate
            chunk_start_ms: Chunk start position

        Returns:
            Absolute onset timestamp in milliseconds, or None
        """
        return detect_onset_in_vocal_chunk(
            vocal_audio=vocal_audio, sample_rate=sample_rate, chunk_start_ms=chunk_start_ms, config=self.config
        )
