"""
Window expansion strategy for MDX onset scanning.

Manages search window calculation and expansion logic.
Pure strategy - no side effects, only calculations.
"""

from dataclasses import dataclass
from typing import Tuple


@dataclass
class SearchWindow:
    """
    Search window boundaries around expected gap.
    
    Attributes:
        start_ms: Window start in milliseconds
        end_ms: Window end in milliseconds
        radius_ms: Current radius from expected gap
        expansion_num: Expansion iteration number (0-indexed)
    """
    start_ms: float
    end_ms: float
    radius_ms: float
    expansion_num: int


class ExpansionStrategy:
    """
    Expanding window search strategy for vocal onset detection.
    
    Strategy:
        1. Start with small window around expected gap (±initial_radius)
        2. If no onset found, expand by radius_increment
        3. Continue up to max_expansions times
        4. Balances speed (small window) vs robustness (expansion fallback)
    
    Example:
        strategy = ExpansionStrategy(
            initial_radius_ms=7500,     # ±7.5s initial window
            radius_increment_ms=7500,   # Expand by 7.5s each time
            max_expansions=3            # Max 3 expansions (±30s total)
        )
        
        for window in strategy.generate_windows(expected_gap_ms=5000, total_duration_ms=180000):
            # Search in window.start_ms to window.end_ms
            if found_onset:
                break
    """
    
    def __init__(
        self,
        initial_radius_ms: float,
        radius_increment_ms: float,
        max_expansions: int,
        total_duration_ms: float
    ):
        """
        Initialize expansion strategy.
        
        Args:
            initial_radius_ms: Initial search radius around expected gap
            radius_increment_ms: Amount to expand radius on each iteration
            max_expansions: Maximum number of expansions (0 = no expansion)
            total_duration_ms: Total audio duration for boundary checking
        """
        self.initial_radius_ms = initial_radius_ms
        self.radius_increment_ms = radius_increment_ms
        self.max_expansions = max_expansions
        self.total_duration_ms = total_duration_ms
    
    def generate_windows(
        self,
        expected_gap_ms: float
    ) -> Tuple[SearchWindow, ...]:
        """
        Generate sequence of search windows with expanding radius.
        
        Args:
            expected_gap_ms: Expected gap position from metadata
            
        Returns:
            Tuple of SearchWindow objects (initial + expansions)
        """
        windows = []
        current_radius_ms = self.initial_radius_ms
        
        for expansion_num in range(self.max_expansions + 1):
            window = self._calculate_window(
                expected_gap_ms=expected_gap_ms,
                radius_ms=current_radius_ms,
                expansion_num=expansion_num
            )
            windows.append(window)
            
            # Expand for next iteration
            current_radius_ms += self.radius_increment_ms
        
        return tuple(windows)
    
    def _calculate_window(
        self,
        expected_gap_ms: float,
        radius_ms: float,
        expansion_num: int
    ) -> SearchWindow:
        """
        Calculate search window for given radius.
        
        CRITICAL FIX: Always include position 0 in first expansion to catch
        vocals that start immediately, even if expected_gap suggests later start.
        
        Args:
            expected_gap_ms: Expected gap position
            radius_ms: Search radius around expected gap
            expansion_num: Expansion iteration number
            
        Returns:
            SearchWindow with boundaries clamped to audio duration
        """
        # For first expansion (expansion_num=0), always start from 0 to catch immediate vocals
        # For subsequent expansions, use centered window around expected gap
        if expansion_num == 0:
            start_ms = 0.0
        else:
            start_ms = max(0.0, expected_gap_ms - radius_ms)
        
        end_ms = min(self.total_duration_ms, expected_gap_ms + radius_ms)
        
        return SearchWindow(
            start_ms=start_ms,
            end_ms=end_ms,
            radius_ms=radius_ms,
            expansion_num=expansion_num
        )
    
    def should_continue(self, expansion_num: int, found_onset: bool) -> bool:
        """
        Determine if search should continue to next expansion.
        
        Args:
            expansion_num: Current expansion iteration (0-indexed)
            found_onset: Whether onset was found in current window
            
        Returns:
            True if should continue searching, False otherwise
        """
        # Stop if onset found
        if found_onset:
            return False
        
        # Stop if reached max expansions
        if expansion_num >= self.max_expansions:
            return False
        
        return True
