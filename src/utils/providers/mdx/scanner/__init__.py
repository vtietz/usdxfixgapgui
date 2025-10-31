"""
Modular MDX onset scanner with expanding window search.

This module provides the MDX vocal onset scanner,
breaking down the complex _scan_chunks_for_onset function (CCN=18, NLOC=102)
into focused, testable components.

Architecture:
    - ChunkIterator: Generate chunk boundaries with overlap tracking
    - ExpansionStrategy: Manage search window expansion logic
    - OnsetDetectorPipeline: Coordinate per-chunk processing
    - scan_for_onset: Main orchestrator

Complexity Reduction:
    Original: CCN=18, NLOC=102 (monolithic function)
    Target: CCN≤5 per function, NLOC≤40

Usage:
    from utils.providers.mdx.scanner import scan_for_onset

    onset_ms = scan_for_onset(
        audio_file="song.mp3",
        expected_gap_ms=5000.0,
        config=mdx_config,
        ...
    )
"""

from utils.providers.mdx.scanner.pipeline import scan_for_onset

__all__ = ["scan_for_onset"]
