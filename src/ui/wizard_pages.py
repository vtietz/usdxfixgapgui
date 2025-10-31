"""
Base wizard page system for multi-step UI flows.

Provides a framework for creating wizard-style dialogs where users progress
through multiple pages. Pages can pass data between each other and control
the flow based on user actions or system state.
"""

from typing import Dict, Any, Optional
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Signal


class WizardPage(QWidget):
    """
    Base class for wizard pages.

    Each page in a wizard extends this class and implements its own UI.
    Pages can emit signals to control wizard flow and pass data forward.

    Signals:
        page_complete: Emitted when page work is done (passes data dict to next page)
        page_skipped: Emitted when page should be skipped
        wizard_finished: Emitted when wizard should close entirely
    """

    # Signals
    page_complete = Signal(dict)  # data to pass to next page
    page_skipped = Signal()
    wizard_finished = Signal(dict)  # final result data

    def __init__(self, parent=None):
        """Initialize wizard page."""
        super().__init__(parent)
        self._page_data: Dict[str, Any] = {}

    def initialize(self, data: Optional[Dict[str, Any]] = None):
        """
        Initialize page with data from previous pages.

        Called when page becomes active. Override to set up UI based on
        incoming data.

        Args:
            data: Dictionary containing data from previous pages
        """
        self._page_data = data or {}

    def can_advance(self) -> bool:
        """
        Check if wizard can advance from this page.

        Override to implement validation logic.

        Returns:
            True if user can proceed to next page
        """
        return True

    def should_skip(self) -> bool:
        """
        Check if this page should be skipped.

        Override to implement skip logic (e.g., based on system state).

        Returns:
            True if page should be skipped
        """
        return False

    def get_page_data(self) -> Dict[str, Any]:
        """
        Get data to pass to next page.

        Override to provide custom data.

        Returns:
            Dictionary of data to pass forward
        """
        return self._page_data.copy()

    def cleanup(self):
        """
        Cleanup when leaving page.

        Override to cancel ongoing operations, disconnect signals, etc.
        """
        pass
