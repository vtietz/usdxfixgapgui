"""Configuration and constants for MDX provider."""

from dataclasses import dataclass

# Constants
DEMUCS_MODEL_NAME = 'htdemucs'
VOCALS_INDEX = 3
DEFAULT_RESAMPLE_HZ = 0
DEFAULT_FP16 = False
MAX_VOCALS_CACHE_SIZE = 6  # Maximum cached vocals chunks


@dataclass
class MdxConfig:
    """Configuration parameters for MDX provider."""
    # Chunked scanning parameters
    chunk_duration_ms: float = 12000
    chunk_overlap_ms: float = 6000

    # Energy analysis parameters
    frame_duration_ms: float = 25
    hop_duration_ms: float = 20
    noise_floor_duration_ms: float = 800

    # Onset detection thresholds
    onset_snr_threshold: float = 6.0
    onset_abs_threshold: float = 0.02
    min_voiced_duration_ms: float = 300
    hysteresis_ms: float = 200

    # Expanding search parameters
    initial_radius_ms: float = 7500
    radius_increment_ms: float = 7500
    max_expansions: int = 3

    # Performance optimizations
    use_fp16: bool = DEFAULT_FP16
    resample_hz: int = DEFAULT_RESAMPLE_HZ

    # Confidence and preview
    confidence_threshold: float = 0.55
    preview_pre_ms: float = 3000
    preview_post_ms: float = 9000

    def __post_init__(self):
        """Validate configuration parameters."""
        if self.chunk_duration_ms <= 0:
            raise ValueError(f"chunk_duration_ms must be positive, got {self.chunk_duration_ms}")
        if self.chunk_overlap_ms < 0:
            raise ValueError(f"chunk_overlap_ms must be non-negative, got {self.chunk_overlap_ms}")
        if self.chunk_overlap_ms >= self.chunk_duration_ms:
            raise ValueError(
                f"chunk_overlap_ms ({self.chunk_overlap_ms}) must be less than "
                f"chunk_duration_ms ({self.chunk_duration_ms})"
            )
        if self.frame_duration_ms <= 0:
            raise ValueError(f"frame_duration_ms must be positive, got {self.frame_duration_ms}")
        if self.hop_duration_ms <= 0:
            raise ValueError(f"hop_duration_ms must be positive, got {self.hop_duration_ms}")
        if self.noise_floor_duration_ms < 0:
            raise ValueError(f"noise_floor_duration_ms must be non-negative, got {self.noise_floor_duration_ms}")

    @classmethod
    def from_config(cls, config) -> 'MdxConfig':
        """Create MdxConfig from a config object using getattr with defaults."""
        return cls(
            chunk_duration_ms=getattr(config, 'mdx_chunk_duration_ms', cls.__dataclass_fields__['chunk_duration_ms'].default),
            chunk_overlap_ms=getattr(config, 'mdx_chunk_overlap_ms', cls.__dataclass_fields__['chunk_overlap_ms'].default),
            frame_duration_ms=getattr(config, 'mdx_frame_duration_ms', cls.__dataclass_fields__['frame_duration_ms'].default),
            hop_duration_ms=getattr(config, 'mdx_hop_duration_ms', cls.__dataclass_fields__['hop_duration_ms'].default),
            noise_floor_duration_ms=getattr(config, 'mdx_noise_floor_duration_ms', cls.__dataclass_fields__['noise_floor_duration_ms'].default),
            onset_snr_threshold=getattr(config, 'mdx_onset_snr_threshold', cls.__dataclass_fields__['onset_snr_threshold'].default),
            onset_abs_threshold=getattr(config, 'mdx_onset_abs_threshold', cls.__dataclass_fields__['onset_abs_threshold'].default),
            min_voiced_duration_ms=getattr(config, 'mdx_min_voiced_duration_ms', cls.__dataclass_fields__['min_voiced_duration_ms'].default),
            hysteresis_ms=getattr(config, 'mdx_hysteresis_ms', cls.__dataclass_fields__['hysteresis_ms'].default),
            initial_radius_ms=getattr(config, 'mdx_initial_radius_ms', cls.__dataclass_fields__['initial_radius_ms'].default),
            radius_increment_ms=getattr(config, 'mdx_radius_increment_ms', cls.__dataclass_fields__['radius_increment_ms'].default),
            max_expansions=getattr(config, 'mdx_max_expansions', cls.__dataclass_fields__['max_expansions'].default),
            use_fp16=getattr(config, 'mdx_use_fp16', cls.__dataclass_fields__['use_fp16'].default),
            resample_hz=getattr(config, 'mdx_resample_hz', cls.__dataclass_fields__['resample_hz'].default),
            confidence_threshold=getattr(config, 'mdx_confidence_threshold', cls.__dataclass_fields__['confidence_threshold'].default),
            preview_pre_ms=getattr(config, 'mdx_preview_pre_ms', cls.__dataclass_fields__['preview_pre_ms'].default),
            preview_post_ms=getattr(config, 'mdx_preview_post_ms', cls.__dataclass_fields__['preview_post_ms'].default),
        )
