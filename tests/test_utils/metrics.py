"""
Metrics utilities for Tier-2 scanner tests.

Provides spies/counters for tracking chunk processing behavior.
"""

from contextlib import contextmanager
from typing import Set


class ChunkMetrics:
    """Tracks chunk processing metrics during scanner execution."""

    def __init__(self):
        self.processed_chunks: int = 0
        self.unique_chunk_starts_ms: Set[float] = set()
        self.chunk_boundaries: list = []

    def record_chunk(self, chunk_start_ms: float):
        """Record a processed chunk."""
        self.processed_chunks += 1
        self.unique_chunk_starts_ms.add(chunk_start_ms)
        self.chunk_boundaries.append(chunk_start_ms)

    def reset(self):
        """Reset all metrics."""
        self.processed_chunks = 0
        self.unique_chunk_starts_ms.clear()
        self.chunk_boundaries.clear()

    @property
    def unique_chunks(self) -> int:
        """Get count of unique chunk starts."""
        return len(self.unique_chunk_starts_ms)

    def has_duplicates(self) -> bool:
        """Check if any chunks were processed multiple times."""
        return self.processed_chunks != self.unique_chunks


@contextmanager
def spy_on_process_chunk(pipeline_instance):
    """
    Context manager to spy on OnsetDetectorPipeline.process_chunk calls.

    Usage:
        metrics = ChunkMetrics()
        with spy_on_process_chunk(pipeline_instance) as metrics:
            # Run scanner
            ...
        assert metrics.processed_chunks <= expected_max
    """
    metrics = ChunkMetrics()

    # Store original method
    original_process_chunk = pipeline_instance.process_chunk

    # Create wrapper that records metrics
    def wrapped_process_chunk(chunk, check_cancellation=None):
        metrics.record_chunk(chunk.start_ms)
        return original_process_chunk(chunk, check_cancellation)

    # Monkey-patch
    pipeline_instance.process_chunk = wrapped_process_chunk

    try:
        yield metrics
    finally:
        # Restore original
        pipeline_instance.process_chunk = original_process_chunk
