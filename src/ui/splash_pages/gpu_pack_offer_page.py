"""
GPU Pack offer wizard page.

Presents GPU Pack download option to users with CPU-only PyTorch
who have opted in for GPU acceleration.
"""

import logging
from typing import Optional, Dict, Any
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QWidget
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from ui.wizard_pages import WizardPage
from services.system_capabilities import SystemCapabilities

logger = logging.getLogger(__name__)


class GpuPackOfferPage(WizardPage):
    """
    GPU Pack offer page (Page 2 of wizard).

    Shown when:
    - PyTorch CPU is available
    - CUDA is not available
    - User has gpu_opt_in enabled
    - User hasn't disabled this prompt

    Offers to download GPU Pack for 5-10x faster processing.
    """

    def __init__(self, parent=None):
        """Initialize GPU Pack offer page."""
        super().__init__(parent)
        self.capabilities: Optional[SystemCapabilities] = None
        self._config = None

        self._setup_ui()

    def _setup_ui(self):
        """Setup page UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(40, 40, 40, 30)

        # Emoji + Title
        title_layout = QHBoxLayout()
        title_layout.addStretch()

        emoji_label = QLabel("⚡")
        emoji_font = QFont()
        emoji_font.setPointSize(32)
        emoji_label.setFont(emoji_font)
        title_layout.addWidget(emoji_label)

        title_label = QLabel("GPU Acceleration Available")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_layout.addWidget(title_label)

        title_layout.addStretch()
        layout.addLayout(title_layout)

        # Benefit message
        benefit_label = QLabel("🎵 Detect gaps 5-10x faster with NVIDIA GPU")
        benefit_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        benefit_label.setStyleSheet("font-size: 12pt; color: #ccc;")
        layout.addWidget(benefit_label)

        layout.addSpacing(10)

        # Download details
        details_widget = self._create_details_section()
        layout.addWidget(details_widget)

        layout.addSpacing(10)

        # System info
        self.system_info_label = QLabel()
        self.system_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.system_info_label.setStyleSheet("color: #999; font-size: 10pt;")
        layout.addWidget(self.system_info_label)

        layout.addStretch()

        # "Don't ask again" checkbox
        self.dont_ask_checkbox = QCheckBox("Don't ask me about GPU Pack again")
        self.dont_ask_checkbox.setStyleSheet("color: #999;")
        layout.addWidget(self.dont_ask_checkbox)

    def _create_details_section(self) -> QWidget:
        """Create download details section."""
        widget = QWidget()
        widget.setStyleSheet("""
            QWidget {
                background-color: #2d2d2d;
                border-radius: 8px;
                padding: 15px;
            }
        """)

        layout = QVBoxLayout(widget)
        layout.setSpacing(8)

        # Download size
        size_label = QLabel("📦 Download Size: ~2.8 GB")
        size_label.setStyleSheet("color: #ccc; font-size: 11pt;")
        layout.addWidget(size_label)

        # Time estimate
        time_label = QLabel("⏱️  One-time download: ~15-30 minutes")
        time_label.setStyleSheet("color: #ccc; font-size: 11pt;")
        layout.addWidget(time_label)

        # Disk space
        disk_label = QLabel("💾 Disk Space: ~3.5 GB after installation")
        disk_label.setStyleSheet("color: #ccc; font-size: 11pt;")
        layout.addWidget(disk_label)

        return widget

    def initialize(self, data: Optional[Dict[str, Any]] = None):
        """
        Initialize page with data from health check.

        Args:
            data: Dictionary containing 'capabilities' and 'config'
        """
        super().initialize(data)

        if data:
            self.capabilities = data.get('capabilities')
            self._config = data.get('config')

            # Update system info label
            if self.capabilities:
                info_parts = []

                # GPU name
                if self.capabilities.gpu_name:
                    info_parts.append(f"System: {self.capabilities.gpu_name} ✅")

                # PyTorch version
                if self.capabilities.torch_version:
                    info_parts.append(f"PyTorch CPU: {self.capabilities.torch_version} ✅")

                if info_parts:
                    self.system_info_label.setText(" • ".join(info_parts))

    def can_advance(self) -> bool:
        """Can always advance from this page."""
        return True

    def should_skip(self) -> bool:
        """
        Skip if user doesn't want GPU Pack offers.

        Returns:
            True if page should be skipped
        """
        if not self._config:
            return False

        # Skip if user has disabled GPU Pack prompts
        if hasattr(self._config, 'gpu_pack_dont_ask') and self._config.gpu_pack_dont_ask:
            return True

        # Skip if GPU already available (shouldn't happen, but safety check)
        if self.capabilities and self.capabilities.has_cuda:
            return True

        # Skip if PyTorch not available (can't install GPU Pack without base PyTorch)
        if self.capabilities and not self.capabilities.has_torch:
            return True

        # Skip if user doesn't want GPU acceleration
        if not self._config.gpu_opt_in:
            return True

        return False

    def get_page_data(self) -> Dict[str, Any]:
        """
        Get data to pass to next page.

        Returns:
            Dictionary with download request status
        """
        # Save "don't ask" preference if checked
        if self._config and self.dont_ask_checkbox.isChecked():
            self._config.gpu_pack_dont_ask = True
            self._config.save()
            logger.info("GPU Pack prompts disabled")

        # Determine GPU flavor (default to cu121)
        gpu_flavor = self._config.gpu_flavor if self._config else 'cu121'

        return {
            'capabilities': self.capabilities,
            'download_requested': False,  # Updated by navigation buttons
            'gpu_flavor': gpu_flavor,
            'config': self._config
        }

    def cleanup(self):
        """Cleanup when leaving page."""
        # Nothing to cleanup for this page
        pass
