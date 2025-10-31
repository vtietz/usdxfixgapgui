"""
Health check wizard page.

Runs system capability checks and displays results.
Auto-advances when all checks pass (unless user wants to review).
"""

import logging
from typing import Optional, Dict, Any
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QProgressBar, QCheckBox
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont

from ui.wizard_pages import WizardPage
from services.system_capabilities import SystemCapabilities, check_system_capabilities

logger = logging.getLogger(__name__)


class HealthCheckPage(WizardPage):
    """
    System health check page (Page 1 of wizard).

    Checks:
    - PyTorch availability
    - CUDA/GPU detection
    - FFmpeg availability

    Auto-advances after checks complete (with 2s delay for user to see results).
    """

    def __init__(self, parent=None):
        """Initialize health check page."""
        super().__init__(parent)
        self.capabilities: Optional[SystemCapabilities] = None
        self._config = None
        self._checks_complete = False

        self._setup_ui()

    def _setup_ui(self):
        """Setup page UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(30, 30, 30, 20)

        # Page title
        title_label = QLabel("System Health Check")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        # Status label
        self.status_label = QLabel("Checking system requirements...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("color: #999;")
        layout.addWidget(self.status_label)

        # Progress bar
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)  # Indeterminate
        self.progress.setTextVisible(False)
        layout.addWidget(self.progress)

        # Log output area
        log_label = QLabel("Details:")
        log_label.setStyleSheet("color: #999; font-size: 10pt;")
        layout.addWidget(log_label)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(200)
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #1E1E1E;
                color: #E0E0E0;
                border: 1px solid #3a3a3a;
                border-radius: 4px;
                padding: 8px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 9pt;
            }
        """)
        layout.addWidget(self.log_text)

        # "Don't show again" checkbox
        self.dont_show_checkbox = QCheckBox("Don't show this check again (skip if system is healthy)")
        self.dont_show_checkbox.setStyleSheet("color: #999;")
        layout.addWidget(self.dont_show_checkbox)

        layout.addStretch()

    def initialize(self, data: Optional[Dict[str, Any]] = None):
        """
        Initialize page with data.

        Args:
            data: Dictionary containing 'config' object
        """
        super().initialize(data)
        self._config = data.get('config') if data else None

        # Start health checks after a short delay (let page render)
        QTimer.singleShot(100, self._run_checks)

    def _run_checks(self):
        """Run system capability checks."""
        self.log("Starting system checks...")
        self.log("")

        # Run checks with progress logging
        self.capabilities = check_system_capabilities(log_callback=self.log)

        self.log("")
        self.log("=" * 50)
        self.log("")

        # Update UI based on results
        self._update_ui_for_results()

        self._checks_complete = True

    def _update_ui_for_results(self):
        """Update UI based on capability check results."""
        if not self.capabilities:
            logger.error("No capabilities detected")
            return

        # Stop progress bar
        self.progress.setRange(0, 1)
        self.progress.setValue(1)

        # Determine overall status
        if self.capabilities.can_detect:
            detection_mode = self.capabilities.get_detection_mode()

            if detection_mode == 'gpu':
                self.log("✅ GPU acceleration available")
                self.status_label.setText("✅ System Ready (GPU Mode)")
                self.status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
            elif detection_mode == 'cpu':
                self.log("✅ CPU detection available")
                self.status_label.setText("✅ System Ready (CPU Mode)")
                self.status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
        else:
            # Critical failure
            if not self.capabilities.has_torch:
                self.log("❌ PyTorch not available - BUILD ERROR")
                self.status_label.setText("❌ PyTorch Missing (Build Error)")
            elif not self.capabilities.has_ffmpeg:
                self.log("❌ FFmpeg not available")
                self.status_label.setText("❌ FFmpeg Missing")
            else:
                self.log("❌ System not ready")
                self.status_label.setText("❌ System Not Ready")

            self.status_label.setStyleSheet("color: #f44336; font-weight: bold;")

        # Auto-advance after 2 seconds if all OK
        if self.capabilities.can_detect:
            self.log("")
            self.log("Auto-advancing in 2 seconds...")
            QTimer.singleShot(2000, self._auto_advance)

    def _auto_advance(self):
        """Auto-advance to next page."""
        # Save "don't show" preference
        if self._config and self.dont_show_checkbox.isChecked():
            self._config.splash_dont_show_health = True
            self._config.save()
            logger.info("Health check auto-show disabled")

        # Emit completion with capabilities data
        self.page_complete.emit(self.get_page_data())

    def log(self, message: str):
        """
        Add message to log output.

        Args:
            message: Message to display
        """
        self.log_text.append(message)
        # Auto-scroll to bottom
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def can_advance(self) -> bool:
        """Can advance if checks are complete."""
        return self._checks_complete

    def should_skip(self) -> bool:
        """
        Skip if user doesn't want to see health checks and system is healthy.

        Returns:
            True if page should be skipped
        """
        if not self._config:
            return False

        # Don't skip on first run or if user hasn't disabled it
        if not hasattr(self._config, 'splash_dont_show_health'):
            return False

        return self._config.splash_dont_show_health

    def get_page_data(self) -> Dict[str, Any]:
        """
        Get data to pass to next page.

        Returns:
            Dictionary with capabilities and health status
        """
        return {
            'capabilities': self.capabilities,
            'health_check_passed': self.capabilities.can_detect if self.capabilities else False,
            'config': self._config
        }

    def cleanup(self):
        """Cleanup when leaving page."""
        # Nothing to cleanup for this page
        pass
