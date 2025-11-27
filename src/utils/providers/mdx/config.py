"""
MDX Provider Configuration

Configuration dataclass and validation for MDX-Net detection provider.
Supports loading from config objects with sensible defaults.
"""

from dataclasses import dataclass


# Performance optimization defaults
DEFAULT_RESAMPLE_HZ = 0
DEFAULT_FP16 = False
DEFAULT_EARLY_STOP_TOLERANCE_MS = 500
DEFAULT_TF32 = True


@dataclass
class MdxConfig:
    """Configuration parameters for MDX provider."""

    # Chunked scanning parameters
    chunk_duration_ms: float = 12000
    chunk_overlap_ms: float = 6000

    # Energy analysis parameters
    frame_duration_ms: float = 25
    hop_duration_ms: float = 20
    noise_floor_duration_ms: float = 1200

    # Onset detection thresholds
    onset_snr_threshold: float = 5.5
    onset_abs_threshold: float = 0.025
    min_voiced_duration_ms: float = 100
    hysteresis_ms: float = 350

    # Expanding search parameters
    initial_radius_ms: float = 7500
    radius_increment_ms: float = 7500
    max_expansions: int = 3

    # Vocal start window parameters (iterative expansion)
    start_window_ms: int = 12000
    start_window_increment_ms: int = 6000
    start_window_max_ms: int = 36000

    # Performance optimizations
    use_fp16: bool = DEFAULT_FP16
    resample_hz: int = DEFAULT_RESAMPLE_HZ
    early_stop_tolerance_ms: int = DEFAULT_EARLY_STOP_TOLERANCE_MS
    tf32: bool = DEFAULT_TF32

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
    def from_config(cls, config) -> "MdxConfig":
        """Create MdxConfig from a config object using getattr with defaults."""
        return cls(
            chunk_duration_ms=getattr(config, "mdx_chunk_duration_ms", cls.chunk_duration_ms),
            chunk_overlap_ms=getattr(config, "mdx_chunk_overlap_ms", cls.chunk_overlap_ms),
            frame_duration_ms=getattr(config, "mdx_frame_duration_ms", cls.frame_duration_ms),
            hop_duration_ms=getattr(config, "mdx_hop_duration_ms", cls.hop_duration_ms),
            noise_floor_duration_ms=getattr(config, "mdx_noise_floor_duration_ms", cls.noise_floor_duration_ms),
            onset_snr_threshold=getattr(config, "mdx_onset_snr_threshold", cls.onset_snr_threshold),
            onset_abs_threshold=getattr(config, "mdx_onset_abs_threshold", cls.onset_abs_threshold),
            min_voiced_duration_ms=getattr(config, "mdx_min_voiced_duration_ms", cls.min_voiced_duration_ms),
            hysteresis_ms=getattr(config, "mdx_hysteresis_ms", cls.hysteresis_ms),
            initial_radius_ms=getattr(config, "mdx_initial_radius_ms", cls.initial_radius_ms),
            radius_increment_ms=getattr(config, "mdx_radius_increment_ms", cls.radius_increment_ms),
            max_expansions=getattr(config, "mdx_max_expansions", cls.max_expansions),
            start_window_ms=int(getattr(config, "vocal_start_window_sec", 12) or 12) * 1000,
            start_window_increment_ms=int(getattr(config, "vocal_window_increment_sec", 6) or 6) * 1000,
            start_window_max_ms=int(getattr(config, "vocal_window_max_sec", 36) or 36) * 1000,
            use_fp16=getattr(config, "mdx_use_fp16", cls.use_fp16),
            resample_hz=getattr(config, "mdx_resample_hz", cls.resample_hz),
            early_stop_tolerance_ms=getattr(config, "mdx_early_stop_tolerance_ms", cls.early_stop_tolerance_ms),
            tf32=getattr(config, "mdx_tf32", cls.tf32),
            confidence_threshold=getattr(config, "mdx_confidence_threshold", cls.confidence_threshold),
            preview_pre_ms=getattr(config, "mdx_preview_pre_ms", cls.preview_pre_ms),
            preview_post_ms=getattr(config, "mdx_preview_post_ms", cls.preview_post_ms),
        )
