"""
Wizard-style splash screen controller.

Manages multi-page wizard flow for application startup including:
- System health checks
- GPU Pack offers
- Download progress

This is the main controller that coordinates page transitions and user navigation.
"""

import logging
import sys
import os
from typing import List, Optional, Dict, Any, Type
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QStackedWidget
)
from PySide6.QtCore import Qt, QTimer, Signal, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QFont

from ui.wizard_pages import WizardPage

logger = logging.getLogger(__name__)


def _is_running_tests() -> bool:
    """Check if we're running in a test environment (pytest only, not false positives from unittest imports)."""
    return ('pytest' in sys.modules) or (os.getenv('USDX_TEST_MODE') == '1')


class WizardSplash(QDialog):
    """
    Multi-page wizard splash screen.

    Coordinates page flow, navigation, and data passing between pages.
    Auto-skips pages based on system state and user preferences.

    Signals:
        wizard_complete: Emitted when wizard finishes (passes final data dict)
        wizard_cancelled: Emitted when user cancels wizard
    """

    # Signals
    wizard_complete = Signal(dict)
    wizard_cancelled = Signal()

    def __init__(self, parent=None, config=None):
        """
        Initialize wizard splash screen.

        Args:
            parent: Parent widget (usually None for splash)
            config: Config object for settings
        """
        super().__init__(parent)
        self.config = config
        self._pages: List[WizardPage] = []
        self._page_indices_to_show: List[int] = []
        self._current_page_index = 0
        self._page_data: Dict[str, Any] = {}

        self._setup_ui()

    def _setup_ui(self):
        """Setup wizard UI (inherits dark theme from app's global palette)."""
        self.setWindowTitle("USDXFixGap - Starting...")
        self.setModal(True)
        self.setFixedSize(650, 500)

        # Don't show as splash screen in tests
        if _is_running_tests():
            self.setWindowFlags(Qt.WindowType.Dialog)
        else:
            self.setWindowFlags(Qt.WindowType.SplashScreen | Qt.WindowType.WindowStaysOnTopHint)

        # No custom styles - use app's global Fusion dark palette
        # Buttons inherit: background QColor(53,53,53), text white, highlight QColor(42,130,218)

        # Main layout
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # Stacked widget for pages
        self._stack = QStackedWidget()
        layout.addWidget(self._stack, 1)        # Navigation bar at bottom
        nav_layout = self._create_navigation_bar()
        layout.addLayout(nav_layout)

    def _create_navigation_bar(self) -> QHBoxLayout:
        """Create bottom navigation bar with buttons and progress dots."""
        nav_layout = QHBoxLayout()
        nav_layout.setContentsMargins(20, 10, 20, 20)
        nav_layout.setSpacing(10)

        # Progress dots (left side)
        self._dots_label = QLabel("● ○ ○")
        self._dots_label.setStyleSheet("color: #999; font-size: 16px;")
        nav_layout.addWidget(self._dots_label)

        nav_layout.addStretch()

        # Navigation buttons (right side)
        self._back_btn = QPushButton("← Back")
        self._back_btn.clicked.connect(self._on_back_clicked)
        self._back_btn.setVisible(False)  # Hidden on first page
        nav_layout.addWidget(self._back_btn)

        self._skip_btn = QPushButton("Skip")
        self._skip_btn.clicked.connect(self._on_skip_clicked)
        nav_layout.addWidget(self._skip_btn)

        self._next_btn = QPushButton("Next →")
        self._next_btn.clicked.connect(self._on_next_clicked)
        self._next_btn.setDefault(True)
        nav_layout.addWidget(self._next_btn)

        # Separator
        nav_layout.addSpacing(10)

        # Close button (always visible, far right) - exits app immediately
        self._close_btn = QPushButton("✕ Close App")
        self._close_btn.setToolTip("Exit application")
        self._close_btn.clicked.connect(self._on_close_clicked)
        nav_layout.addWidget(self._close_btn)

        return nav_layout

    def add_page(self, page: WizardPage):
        """
        Add a page to the wizard.

        Args:
            page: WizardPage instance to add
        """
        self._pages.append(page)
        self._stack.addWidget(page)

        # Connect page signals
        page.page_complete.connect(self._on_page_complete)
        page.page_skipped.connect(self._on_page_skipped)
        page.wizard_finished.connect(self._on_wizard_finished)

    def set_page_flow(self, indices: List[int]):
        """
        Set which pages should be shown (in order).

        Args:
            indices: List of page indices to show (e.g., [0, 2] to skip page 1)
        """
        self._page_indices_to_show = indices
        self._current_page_index = 0

    def start(self):
        """Start the wizard (show first page)."""
        # Skip showing UI during tests
        if _is_running_tests():
            logger.info("Test environment detected - skipping splash display")
            # Return empty capabilities for tests
            self._page_data['capabilities'] = None
            self.wizard_complete.emit(self._page_data)
            return

        if not self._page_indices_to_show:
            logger.warning("No pages to show, closing wizard")
            self._finish_wizard()
            return

        self._show_current_page()
        self.exec()

    def _show_current_page(self):
        """Display the current page and update navigation."""
        if self._current_page_index >= len(self._page_indices_to_show):
            # No more pages, finish wizard
            self._finish_wizard()
            return

        page_index = self._page_indices_to_show[self._current_page_index]
        page = self._pages[page_index]

        # Initialize page with accumulated data
        page.initialize(self._page_data)

        # Check if page should be skipped
        if page.should_skip():
            logger.info(f"Page {page_index} skipped (should_skip returned True)")
            self._advance_page()
            return

        # Show page
        self._stack.setCurrentIndex(page_index)

        # Update navigation buttons
        self._update_navigation()

        # Update progress dots
        self._update_progress_dots()

        logger.debug(f"Showing page {self._current_page_index + 1}/{len(self._page_indices_to_show)}")

    def _update_navigation(self):
        """Update navigation button visibility and labels."""
        is_first = self._current_page_index == 0
        is_last = self._current_page_index == len(self._page_indices_to_show) - 1

        # Back button only visible after first page
        self._back_btn.setVisible(not is_first)

        # Next button label changes on last page
        if is_last:
            self._next_btn.setText("Finish")
        else:
            self._next_btn.setText("Next →")

        # Check if current page can advance
        current_page = self._get_current_page()
        if current_page:
            can_advance = current_page.can_advance()
            self._next_btn.setEnabled(can_advance)

    def _update_progress_dots(self):
        """Update progress indicator dots."""
        total_pages = len(self._page_indices_to_show)
        current = self._current_page_index

        # Build dots string: ● for current, ○ for others
        dots = []
        for i in range(total_pages):
            dots.append("●" if i == current else "○")

        self._dots_label.setText(" ".join(dots))

    def _get_current_page(self) -> Optional[WizardPage]:
        """Get the currently displayed page."""
        if 0 <= self._current_page_index < len(self._page_indices_to_show):
            page_index = self._page_indices_to_show[self._current_page_index]
            return self._pages[page_index]
        return None

    def _advance_page(self):
        """Move to next page in sequence."""
        self._current_page_index += 1
        self._show_current_page()

    def _go_back(self):
        """Go back to previous page."""
        if self._current_page_index > 0:
            # Cleanup current page
            current_page = self._get_current_page()
            if current_page:
                current_page.cleanup()

            self._current_page_index -= 1
            self._show_current_page()

    def _on_next_clicked(self):
        """Handle Next/Finish button click."""
        current_page = self._get_current_page()
        if not current_page:
            return

        # Check if page allows advancing
        if not current_page.can_advance():
            logger.warning("Cannot advance from current page")
            return

        # Get data from current page and merge
        page_data = current_page.get_page_data()
        self._page_data.update(page_data)

        # Emit page_complete signal (page may trigger actions)
        current_page.page_complete.emit(page_data)

        # Advance to next page (or finish if last page)
        self._advance_page()

    def _on_back_clicked(self):
        """Handle Back button click."""
        self._go_back()

    def _on_skip_clicked(self):
        """Handle Skip button click."""
        current_page = self._get_current_page()
        if current_page:
            current_page.page_skipped.emit()

        # Skip to next page
        self._advance_page()

    def _on_close_clicked(self):
        """Handle Close button click - immediately exit application."""
        logger.info("User clicked Close & Exit - terminating application")

        # Cleanup all pages first
        for page in self._pages:
            page.cleanup()

        # Emit cancellation signal (allows main app to handle exit gracefully)
        self.wizard_cancelled.emit()

        # Close the dialog
        self.reject()

    def _on_page_complete(self, data: Dict[str, Any]):
        """
        Handle page completion signal.

        Args:
            data: Data from completed page
        """
        # Page already handled in _on_next_clicked
        # This handler is for pages that auto-complete
        pass

    def _on_page_skipped(self):
        """Handle page skipped signal."""
        # Already handled in _on_skip_clicked
        pass

    def _on_wizard_finished(self, data: Dict[str, Any]):
        """
        Handle wizard finish signal from page.

        Args:
            data: Final wizard data
        """
        self._page_data.update(data)
        self._finish_wizard()

    def _finish_wizard(self):
        """Complete wizard and emit result."""
        logger.info("Wizard complete")

        # Cleanup all pages
        for page in self._pages:
            page.cleanup()

        # Emit completion signal
        self.wizard_complete.emit(self._page_data)

        # Accept dialog
        self.accept()

    def reject(self):
        """Handle dialog rejection (Esc key, X button)."""
        logger.info("Wizard cancelled by user")

        # Cleanup all pages
        for page in self._pages:
            page.cleanup()

        # Emit cancellation signal
        self.wizard_cancelled.emit()

        super().reject()
