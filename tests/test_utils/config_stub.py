"""
Config stub for Tier-3 pipeline integration tests.

Provides minimal Config object with fields needed by pipeline and worker.
"""

from pathlib import Path
from typing import Optional


class ConfigStub:
    """
    Minimal Config object for testing pipeline/worker without full config system.

    Provides defaults matching production MdxConfig while allowing test-specific overrides.
    """

    def __init__(
        self,
        tmp_root: Optional[str] = None,
        method: str = "mdx",
        default_detection_time: int = 30,
        gap_tolerance: int = 500,
        vocal_start_window_sec: int = 20,
        vocal_window_increment_sec: int = 10,
        vocal_window_max_sec: int = 60,
        # MDX-specific settings
        mdx_chunk_duration_ms: int = 12000,
        mdx_chunk_overlap_ms: int = 6000,
        mdx_frame_duration_ms: int = 25,
        mdx_hop_duration_ms: int = 20,
        mdx_noise_floor_duration_ms: int = 1000,
        mdx_onset_snr_threshold: float = 4.0,
        mdx_onset_abs_threshold: float = 0.01,
        mdx_min_voiced_duration_ms: int = 300,
        mdx_hysteresis_ms: int = 200,
        mdx_initial_radius_ms: int = 7500,
        mdx_radius_increment_ms: int = 7500,
        mdx_max_expansions: int = 2,
        mdx_early_stop_tolerance_ms: int = 500,
        mdx_confidence_threshold: float = 0.55,
    ):
        """
        Initialize config stub with sensible defaults.

        Args:
            tmp_root: Temporary directory root (defaults to system temp)
            method: Detection method ("mdx")
            default_detection_time: Initial detection window in seconds
            gap_tolerance: Gap match tolerance in milliseconds
            vocal_start_window_sec: Initial vocal scan window in seconds
            vocal_window_increment_sec: Window expansion increment in seconds
            vocal_window_max_sec: Maximum vocal scan window in seconds
            mdx_*: MDX-specific detection parameters
        """
        self.tmp_root = tmp_root or str(Path.cwd() / "tmp")
        self.method = method
        self.default_detection_time = default_detection_time
        self.gap_tolerance = gap_tolerance
        self.vocal_start_window_sec = vocal_start_window_sec
        self.vocal_window_increment_sec = vocal_window_increment_sec
        self.vocal_window_max_sec = vocal_window_max_sec

        # MDX settings
        self.mdx_chunk_duration_ms = mdx_chunk_duration_ms
        self.mdx_chunk_overlap_ms = mdx_chunk_overlap_ms
        self.mdx_frame_duration_ms = mdx_frame_duration_ms
        self.mdx_hop_duration_ms = mdx_hop_duration_ms
        self.mdx_noise_floor_duration_ms = mdx_noise_floor_duration_ms
        self.mdx_onset_snr_threshold = mdx_onset_snr_threshold
        self.mdx_onset_abs_threshold = mdx_onset_abs_threshold
        self.mdx_min_voiced_duration_ms = mdx_min_voiced_duration_ms
        self.mdx_hysteresis_ms = mdx_hysteresis_ms
        self.mdx_initial_radius_ms = mdx_initial_radius_ms
        self.mdx_radius_increment_ms = mdx_radius_increment_ms
        self.mdx_max_expansions = mdx_max_expansions
        self.mdx_early_stop_tolerance_ms = mdx_early_stop_tolerance_ms
        self.mdx_confidence_threshold = mdx_confidence_threshold

        # Additional fields that might be accessed
        self.tf32 = True
        self.use_gpu = False
