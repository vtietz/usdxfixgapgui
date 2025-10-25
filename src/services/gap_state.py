"""
Gap State Service - Single source of truth for gap editing state.

Manages current/detected gap values, dirty state, and diff calculations
for the currently selected song.
"""

from dataclasses import dataclass
from typing import Optional, Callable
from enum import Enum


class SeverityBand(Enum):
    """Severity bands for gap differences."""
    GOOD = "good"  # 0-50ms
    WARNING = "warning"  # 50-200ms
    ERROR = "error"  # 200+ms


@dataclass
class GapState:
    """
    State holder for gap editing operations on a single song.

    Tracks:
    - current_gap_ms: The gap value currently set (may be unsaved)
    - detected_gap_ms: The AI-detected gap value
    - diff_ms: Signed difference (current - detected)
    - is_dirty: Whether current differs from saved value
    """

    current_gap_ms: int
    detected_gap_ms: Optional[int] = None
    saved_gap_ms: int = 0
    is_dirty: bool = False

    # Callbacks
    _on_change_callbacks: Optional[list[Callable]] = None

    def __post_init__(self):
        """Initialize callbacks list."""
        if self._on_change_callbacks is None:
            object.__setattr__(self, '_on_change_callbacks', [])
        # Initialize saved_gap_ms if not provided
        if self.saved_gap_ms == 0:
            object.__setattr__(self, 'saved_gap_ms', self.current_gap_ms)

    @property
    def diff_ms(self) -> Optional[int]:
        """
        Signed difference between current and detected gap.

        Returns:
            Positive if current > detected (gap is later than detected)
            Negative if current < detected (gap is earlier than detected)
            None if no detected gap available
        """
        if self.detected_gap_ms is None:
            return None
        return self.current_gap_ms - self.detected_gap_ms

    @property
    def has_detected_gap(self) -> bool:
        """Check if a detected gap is available."""
        return self.detected_gap_ms is not None

    @property
    def can_revert(self) -> bool:
        """Check if revert is possible (current differs from saved)."""
        return self.current_gap_ms != self.saved_gap_ms

    def set_current_gap_ms(self, value: int) -> None:
        """
        Update current gap value and mark as dirty if changed.

        Args:
            value: New gap value in milliseconds
        """
        if value == self.current_gap_ms:
            return

        object.__setattr__(self, 'current_gap_ms', value)
        object.__setattr__(self, 'is_dirty', value != self.saved_gap_ms)
        self._notify_change()

    def set_detected_gap_ms(self, value: Optional[int]) -> None:
        """
        Update detected gap value.

        Args:
            value: Detected gap in milliseconds, or None to clear
        """
        if value == self.detected_gap_ms:
            return

        object.__setattr__(self, 'detected_gap_ms', value)
        self._notify_change()

    def mark_clean(self) -> None:
        """
        Mark state as clean (saved).
        Updates saved_gap_ms to current value.
        """
        object.__setattr__(self, 'saved_gap_ms', self.current_gap_ms)
        object.__setattr__(self, 'is_dirty', False)
        self._notify_change()

    def revert(self) -> None:
        """
        Revert current gap to saved value.
        Clears dirty flag.
        """
        if not self.can_revert:
            return

        object.__setattr__(self, 'current_gap_ms', self.saved_gap_ms)
        object.__setattr__(self, 'is_dirty', False)
        self._notify_change()

    def apply_detected(self) -> None:
        """
        Apply detected gap as current value.
        Marks as dirty if different from saved.
        """
        if not self.has_detected_gap or self.detected_gap_ms is None:
            return

        self.set_current_gap_ms(self.detected_gap_ms)

    def severity_band(self) -> Optional[SeverityBand]:
        """
        Calculate severity band based on absolute difference.

        Returns:
            GOOD (0-50ms), WARNING (50-200ms), ERROR (200+ms), or None
        """
        if self.diff_ms is None:
            return None

        abs_diff = abs(self.diff_ms)
        if abs_diff <= 50:
            return SeverityBand.GOOD
        elif abs_diff <= 200:
            return SeverityBand.WARNING
        else:
            return SeverityBand.ERROR

    def format_diff(self) -> str:
        """
        Format difference for display.

        Returns:
            String like "+25ms", "-120ms", or "No detection" if unavailable
        """
        if self.diff_ms is None:
            return "No detection"

        sign = "+" if self.diff_ms >= 0 else ""
        return f"{sign}{self.diff_ms}ms"

    def subscribe_on_change(self, callback: Callable[[], None]) -> None:
        """
        Subscribe to state changes.

        Args:
            callback: Function to call when state changes (no args)
        """
        if self._on_change_callbacks is None:
            object.__setattr__(self, '_on_change_callbacks', [])

        assert self._on_change_callbacks is not None  # For type checker
        if callback not in self._on_change_callbacks:
            self._on_change_callbacks.append(callback)

    def unsubscribe_on_change(self, callback: Callable[[], None]) -> None:
        """
        Unsubscribe from state changes.

        Args:
            callback: Function to remove from callbacks
        """
        if self._on_change_callbacks is not None and callback in self._on_change_callbacks:
            self._on_change_callbacks.remove(callback)

    def _notify_change(self) -> None:
        """Notify all subscribers of state change."""
        if self._on_change_callbacks is None:
            return
        for callback in self._on_change_callbacks:
            try:
                callback()
            except Exception as e:
                # Log but don't crash on callback errors
                print(f"Error in GapState callback: {e}")

    @classmethod
    def from_song(cls, current_gap: int, detected_gap: Optional[int] = None) -> 'GapState':
        """
        Create GapState from song data.

        Args:
            current_gap: Current gap value in milliseconds
            detected_gap: Detected gap value, or None

        Returns:
            New GapState instance
        """
        return cls(
            current_gap_ms=current_gap,
            detected_gap_ms=detected_gap,
            saved_gap_ms=current_gap,
            is_dirty=False
        )
