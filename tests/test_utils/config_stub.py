"""
Config stub for Tier-3 pipeline integration tests.

Provides minimal Config object with fields needed by pipeline and worker.
"""

from pathlib import Path
from typing import Optional

# Import MdxConfig to use its defaults as single source of truth
import sys
import os
SRC_ROOT = Path(__file__).parent.parent.parent / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from utils.providers.mdx.config import MdxConfig  # noqa: E402

# Create default instance to extract values
_MDX_DEFAULTS = MdxConfig()


class ConfigStub:
    """
    Minimal Config object for testing pipeline/worker without full config system.

    Provides defaults matching production MdxConfig while allowing test-specific overrides.
    All MDX defaults come from MdxConfig dataclass (single source of truth).
    """

    def __init__(
        self,
        tmp_root: Optional[str] = None,
        method: str = "mdx",
        default_detection_time: int = 30,
        gap_tolerance: int = 500,
        vocal_start_window_sec: Optional[int] = None,
        vocal_window_increment_sec: Optional[int] = None,
        vocal_window_max_sec: Optional[int] = None,
        # MDX-specific settings (None = use MdxConfig defaults)
        mdx_chunk_duration_ms: Optional[int] = None,
        mdx_chunk_overlap_ms: Optional[int] = None,
        mdx_frame_duration_ms: Optional[int] = None,
        mdx_hop_duration_ms: Optional[int] = None,
        mdx_noise_floor_duration_ms: Optional[int] = None,
        mdx_onset_snr_threshold: Optional[float] = None,
        mdx_onset_abs_threshold: Optional[float] = None,
        mdx_min_voiced_duration_ms: Optional[int] = None,
        mdx_hysteresis_ms: Optional[int] = None,
        mdx_initial_radius_ms: Optional[int] = None,
        mdx_radius_increment_ms: Optional[int] = None,
        mdx_max_expansions: Optional[int] = None,
        mdx_early_stop_tolerance_ms: Optional[int] = None,
        mdx_confidence_threshold: Optional[float] = None,
    ):
        """
        Initialize config stub with defaults from MdxConfig dataclass.

        Args:
            tmp_root: Temporary directory root (defaults to system temp)
            method: Detection method ("mdx")
            default_detection_time: Initial detection window in seconds
            gap_tolerance: Gap match tolerance in milliseconds
            vocal_start_window_sec: Initial vocal scan window (None = use MdxConfig default)
            vocal_window_increment_sec: Window expansion increment (None = use MdxConfig default)
            vocal_window_max_sec: Maximum vocal scan window (None = use MdxConfig default)
            mdx_*: MDX-specific detection parameters (None = use MdxConfig defaults)
        """
        self.tmp_root = tmp_root or str(Path.cwd() / "tmp")
        self.method = method
        self.default_detection_time = default_detection_time
        self.gap_tolerance = gap_tolerance

        # Vocal window settings: use provided or fall back to MdxConfig defaults
        self.vocal_start_window_sec = (
            vocal_start_window_sec if vocal_start_window_sec is not None
            else int(_MDX_DEFAULTS.start_window_ms / 1000)
        )
        self.vocal_window_increment_sec = (
            vocal_window_increment_sec if vocal_window_increment_sec is not None
            else int(_MDX_DEFAULTS.start_window_increment_ms / 1000)
        )
        self.vocal_window_max_sec = (
            vocal_window_max_sec if vocal_window_max_sec is not None
            else int(_MDX_DEFAULTS.start_window_max_ms / 1000)
        )

        # MDX settings: use provided or fall back to MdxConfig defaults
        self.mdx_chunk_duration_ms = (
            mdx_chunk_duration_ms if mdx_chunk_duration_ms is not None
            else _MDX_DEFAULTS.chunk_duration_ms
        )
        self.mdx_chunk_overlap_ms = (
            mdx_chunk_overlap_ms if mdx_chunk_overlap_ms is not None
            else _MDX_DEFAULTS.chunk_overlap_ms
        )
        self.mdx_frame_duration_ms = (
            mdx_frame_duration_ms if mdx_frame_duration_ms is not None
            else _MDX_DEFAULTS.frame_duration_ms
        )
        self.mdx_hop_duration_ms = (
            mdx_hop_duration_ms if mdx_hop_duration_ms is not None
            else _MDX_DEFAULTS.hop_duration_ms
        )
        self.mdx_noise_floor_duration_ms = (
            mdx_noise_floor_duration_ms if mdx_noise_floor_duration_ms is not None
            else _MDX_DEFAULTS.noise_floor_duration_ms
        )
        self.mdx_onset_snr_threshold = (
            mdx_onset_snr_threshold if mdx_onset_snr_threshold is not None
            else _MDX_DEFAULTS.onset_snr_threshold
        )
        self.mdx_onset_abs_threshold = (
            mdx_onset_abs_threshold if mdx_onset_abs_threshold is not None
            else _MDX_DEFAULTS.onset_abs_threshold
        )
        self.mdx_min_voiced_duration_ms = (
            mdx_min_voiced_duration_ms if mdx_min_voiced_duration_ms is not None
            else _MDX_DEFAULTS.min_voiced_duration_ms
        )
        self.mdx_hysteresis_ms = (
            mdx_hysteresis_ms if mdx_hysteresis_ms is not None
            else _MDX_DEFAULTS.hysteresis_ms
        )
        self.mdx_initial_radius_ms = (
            mdx_initial_radius_ms if mdx_initial_radius_ms is not None
            else _MDX_DEFAULTS.initial_radius_ms
        )
        self.mdx_radius_increment_ms = (
            mdx_radius_increment_ms if mdx_radius_increment_ms is not None
            else _MDX_DEFAULTS.radius_increment_ms
        )
        self.mdx_max_expansions = (
            mdx_max_expansions if mdx_max_expansions is not None
            else _MDX_DEFAULTS.max_expansions
        )
        self.mdx_early_stop_tolerance_ms = (
            mdx_early_stop_tolerance_ms if mdx_early_stop_tolerance_ms is not None
            else _MDX_DEFAULTS.early_stop_tolerance_ms
        )
        self.mdx_confidence_threshold = (
            mdx_confidence_threshold if mdx_confidence_threshold is not None
            else _MDX_DEFAULTS.confidence_threshold
        )

        # Additional fields that might be accessed
        self.tf32 = _MDX_DEFAULTS.tf32
        self.use_gpu = False
