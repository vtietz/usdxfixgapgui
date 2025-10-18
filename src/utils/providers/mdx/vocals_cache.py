"""
LRU cache for separated vocals to avoid redundant Demucs processing.

This cache stores numpy arrays of separated vocals indexed by (audio_file, start_ms, end_ms).
Uses OrderedDict for simple LRU eviction when capacity is reached.
"""

import logging
from collections import OrderedDict
from typing import Tuple, Optional
import numpy as np

logger = logging.getLogger(__name__)

# Cache configuration
MAX_VOCALS_CACHE_SIZE = 6  # Maximum cached vocals chunks


class VocalsCache:
    """
    LRU cache for separated vocals chunks.
    
    Caches vocals numpy arrays to reuse between detection and confidence computation,
    avoiding redundant Demucs separation calls.
    
    Cache key: (audio_file: str, start_ms: float, end_ms: float)
    Cache value: vocals numpy array (channels, samples)
    
    Eviction: Oldest entry removed when cache reaches MAX_VOCALS_CACHE_SIZE.
    """
    
    def __init__(self, max_size: int = MAX_VOCALS_CACHE_SIZE):
        """
        Initialize vocals cache.
        
        Args:
            max_size: Maximum number of cached vocal chunks
        """
        self._cache = OrderedDict()
        self._max_size = max_size
        logger.debug(f"VocalsCache initialized with max_size={max_size}")
    
    def get(
        self,
        audio_file: str,
        position_ms: float
    ) -> Optional[Tuple[np.ndarray, float, float]]:
        """
        Get cached vocals that cover the specified position.
        
        Args:
            audio_file: Audio file path
            position_ms: Position to check (milliseconds)
        
        Returns:
            Tuple of (vocals_array, chunk_start_ms, chunk_end_ms) if found, else None
        """
        for (cached_file, start_ms, end_ms), cached_vocals in self._cache.items():
            if cached_file == audio_file and start_ms <= position_ms <= end_ms:
                logger.debug(f"Cache HIT: Found vocals covering {position_ms:.0f}ms "
                             f"in chunk [{start_ms:.0f}ms-{end_ms:.0f}ms]")
                return (cached_vocals, start_ms, end_ms)
        
        logger.debug(f"Cache MISS: No vocals found covering {position_ms:.0f}ms")
        return None
    
    def put(
        self,
        audio_file: str,
        start_ms: float,
        end_ms: float,
        vocals: np.ndarray
    ):
        """
        Store vocals in cache with LRU eviction if needed.
        
        Args:
            audio_file: Audio file path
            start_ms: Chunk start position (milliseconds)
            end_ms: Chunk end position (milliseconds)
            vocals: Separated vocals numpy array (channels, samples)
        """
        cache_key = (audio_file, start_ms, end_ms)
        
        # Evict oldest entry if cache is full
        if len(self._cache) >= self._max_size:
            oldest_key = next(iter(self._cache))
            logger.debug(f"Cache FULL ({self._max_size} entries), evicting oldest: "
                         f"[{oldest_key[1]:.0f}ms-{oldest_key[2]:.0f}ms]")
            self._cache.pop(oldest_key)
        
        # Add new entry (OrderedDict maintains insertion order for LRU)
        self._cache[cache_key] = vocals
        logger.debug(f"Cache PUT: Stored vocals chunk [{start_ms:.0f}ms-{end_ms:.0f}ms] "
                     f"({len(self._cache)}/{self._max_size} entries)")
    
    def clear(self):
        """Clear all cached vocals."""
        logger.debug(f"Clearing vocals cache ({len(self._cache)} entries)")
        self._cache.clear()
    
    def __len__(self) -> int:
        """Return number of cached entries."""
        return len(self._cache)
    
    @property
    def cache_dict(self) -> OrderedDict:
        """
        Get underlying OrderedDict for direct access (backward compatibility).
        
        Returns:
            OrderedDict mapping (file, start_ms, end_ms) to vocals arrays
        """
        return self._cache
