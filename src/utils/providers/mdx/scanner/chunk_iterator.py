"""
Chunk iteration logic for MDX onset scanning.

Generates audio chunk boundaries with overlap tracking to avoid redundant processing.
Pure iteration logic with no I/O - focuses solely on boundary calculation.
"""

from typing import Iterator, Set
from dataclasses import dataclass


@dataclass
class ChunkBoundaries:
    """
    Audio chunk boundaries in time domain.

    Attributes:
        start_ms: Chunk start position in milliseconds
        end_ms: Chunk end position in milliseconds
        start_s: Chunk start position in seconds (convenience)
        end_s: Chunk end position in seconds (convenience)
    """

    start_ms: float
    end_ms: float

    @property
    def start_s(self) -> float:
        """Chunk start in seconds."""
        return self.start_ms / 1000.0

    @property
    def end_s(self) -> float:
        """Chunk end in seconds."""
        return self.end_ms / 1000.0

    def __hash__(self):
        """Hash for set membership (deduplication)."""
        return hash((int(self.start_ms), int(self.end_ms)))

    def __eq__(self, other):
        """Equality for set membership (deduplication)."""
        if not isinstance(other, ChunkBoundaries):
            return False
        return (int(self.start_ms), int(self.end_ms)) == (int(other.start_ms), int(other.end_ms))


class ChunkIterator:
    """
    Generate audio chunk boundaries with overlap and deduplication.

    Features:
        - Generates overlapping chunks for robust onset detection
        - Tracks processed chunks to avoid redundant work
        - Respects audio duration boundaries
        - Pure iteration - no I/O or side effects

    Example:
        iterator = ChunkIterator(
            chunk_duration_ms=12000,
            chunk_overlap_ms=6000,
            total_duration_ms=180000
        )

        for chunk in iterator.generate_chunks(start_ms=0, end_ms=30000):
            # Process chunk.start_ms to chunk.end_ms
            pass
    """

    def __init__(self, chunk_duration_ms: float, chunk_overlap_ms: float, total_duration_ms: float):
        """
        Initialize chunk iterator.

        Args:
            chunk_duration_ms: Duration of each chunk in milliseconds
            chunk_overlap_ms: Overlap between consecutive chunks in milliseconds
            total_duration_ms: Total audio duration in milliseconds
        """
        self.chunk_duration_ms = chunk_duration_ms
        self.chunk_overlap_ms = chunk_overlap_ms
        self.total_duration_ms = total_duration_ms
        self.chunk_hop_ms = chunk_duration_ms - chunk_overlap_ms

        # Track processed chunks for deduplication
        self._processed: Set[ChunkBoundaries] = set()

    def generate_chunks(self, start_ms: float, end_ms: float) -> Iterator[ChunkBoundaries]:
        """
        Generate chunk boundaries within specified range.

        Only yields chunks that haven't been processed yet (deduplication).

        Args:
            start_ms: Start of range in milliseconds
            end_ms: End of range in milliseconds

        Yields:
            ChunkBoundaries for each unprocessed chunk in range
        """
        current_start_ms = start_ms

        while current_start_ms < end_ms:
            # Calculate chunk boundaries
            chunk_start_ms = current_start_ms
            chunk_end_ms = min(current_start_ms + self.chunk_duration_ms, self.total_duration_ms)

            # Skip if chunk extends beyond range
            if chunk_start_ms >= end_ms:
                break

            # Create chunk boundaries
            chunk = ChunkBoundaries(start_ms=chunk_start_ms, end_ms=chunk_end_ms)

            # Skip if already processed
            if chunk in self._processed:
                current_start_ms += self.chunk_hop_ms
                continue

            # Mark as processed and yield
            self._processed.add(chunk)
            yield chunk

            # Move to next chunk
            current_start_ms += self.chunk_hop_ms

    def reset(self):
        """Reset processed chunks tracking."""
        self._processed.clear()

    @property
    def chunks_processed_count(self) -> int:
        """Number of chunks processed so far."""
        return len(self._processed)
