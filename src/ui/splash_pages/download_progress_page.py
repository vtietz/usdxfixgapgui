"""
GPU Pack download progress wizard page.

Shows real-time download progress when user chooses to download GPU Pack.
"""

import logging
from typing import Optional, Dict, Any
from pathlib import Path
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QTextEdit, QPushButton
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from ui.wizard_pages import WizardPage
from ui.gpu_download_dialog import GpuDownloadWorker
from utils import gpu_manifest
from utils.files import get_localappdata_dir

logger = logging.getLogger(__name__)


class DownloadProgressPage(WizardPage):
    """
    GPU Pack download progress page (Page 3 of wizard).

    Shown when user clicks "Download" on GPU Pack offer page.
    Displays real-time download progress and handles installation.
    """

    # Custom signal for download completion (to trigger wizard advance)
    download_complete = Signal(bool, str)  # (success, message)

    def __init__(self, parent=None):
        """Initialize download progress page."""
        super().__init__(parent)
        self._config = None
        self._worker: Optional[GpuDownloadWorker] = None
        self._download_finished = False
        self._download_success = False

        self._setup_ui()

    def _setup_ui(self):
        """Setup page UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(40, 40, 40, 30)

        # Title
        title_label = QLabel("📥 Downloading GPU Pack...")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        layout.addSpacing(10)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #555;
                border-radius: 5px;
                text-align: center;
                background-color: #2d2d2d;
                color: white;
                height: 25px;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                border-radius: 4px;
            }
        """)
        layout.addWidget(self.progress_bar)

        # Status label (speed, ETA, etc.)
        self.status_label = QLabel("Preparing download...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("color: #999; font-size: 10pt;")
        layout.addWidget(self.status_label)

        layout.addSpacing(10)

        # Current file label
        self.file_label = QLabel("")
        self.file_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.file_label.setStyleSheet("color: #777; font-size: 9pt; font-style: italic;")
        layout.addWidget(self.file_label)

        layout.addStretch()

        # Log area (for detailed progress)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(100)
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #1E1E1E;
                color: #E0E0E0;
                border: 1px solid #3a3a3a;
                border-radius: 4px;
                padding: 5px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 8pt;
            }
        """)
        self.log_text.setVisible(False)  # Hidden by default, show on error
        layout.addWidget(self.log_text)

        layout.addStretch()

    def initialize(self, data: Optional[Dict[str, Any]] = None):
        """
        Initialize page and start download.

        Args:
            data: Dictionary containing 'gpu_flavor', 'config'
        """
        super().initialize(data)

        if data:
            self._config = data.get('config')
            gpu_flavor = data.get('gpu_flavor', 'cu121')

            # Start download
            self._start_download(gpu_flavor)

    def _start_download(self, gpu_flavor: str):
        """
        Start GPU Pack download in background.

        Args:
            gpu_flavor: GPU flavor to download ('cu121', 'cu118', etc.)
        """
        try:
            # Get manifest
            manifest = gpu_manifest.get_manifest_for_flavor(gpu_flavor)
            if not manifest:
                self._on_download_failed(f"No manifest found for {gpu_flavor}")
                return

            # Prepare download paths
            pack_dir = Path(get_localappdata_dir()) / "gpu_pack"
            pack_dir.mkdir(parents=True, exist_ok=True)
            dest_zip = pack_dir / f"gpu_pack_{gpu_flavor}.zip"

            # Create worker
            self._worker = GpuDownloadWorker(
                self._config,
                manifest,
                pack_dir,
                dest_zip
            )

            # Connect signals
            self._worker.progress.connect(self._on_download_progress)
            self._worker.finished.connect(self._on_download_finished)

            # Start download
            self._worker.start()

            self.log("Download started...")

        except Exception as e:
            logger.error(f"Failed to start download: {e}")
            self._on_download_failed(str(e))

    def _on_download_progress(self, percentage: int, status_msg: str):
        """
        Handle download progress update.

        Args:
            percentage: Progress percentage (0-100)
            status_msg: Status message with speed/ETA
        """
        self.progress_bar.setValue(percentage)
        self.status_label.setText(status_msg)

        # Extract filename from status if present
        if "Downloading:" in status_msg:
            # Show "Installing..." when extracting
            pass

    def _on_download_finished(self, success: bool, message: str):
        """
        Handle download completion.

        Args:
            success: Whether download succeeded
            message: Result message
        """
        self._download_finished = True
        self._download_success = success

        if success:
            self.progress_bar.setValue(100)
            self.status_label.setText("✅ GPU Pack installed successfully!")
            self.status_label.setStyleSheet("color: #4CAF50; font-size: 11pt; font-weight: bold;")
            self.log(message)

            # Auto-advance after 2 seconds
            from PySide6.QtCore import QTimer
            QTimer.singleShot(2000, self._finish_download)
        else:
            self.status_label.setText("❌ Download failed")
            self.status_label.setStyleSheet("color: #f44336; font-size: 11pt; font-weight: bold;")
            self.log_text.append(message)
            self.log_text.setVisible(True)

    def _on_download_failed(self, error_msg: str):
        """
        Handle download failure.

        Args:
            error_msg: Error message
        """
        self._download_finished = True
        self._download_success = False

        self.progress_bar.setValue(0)
        self.status_label.setText("❌ Failed to start download")
        self.status_label.setStyleSheet("color: #f44336; font-size: 11pt; font-weight: bold;")
        self.log_text.append(error_msg)
        self.log_text.setVisible(True)

    def _finish_download(self):
        """Finish download and advance wizard."""
        # Emit completion
        self.page_complete.emit(self.get_page_data())

    def log(self, message: str):
        """Add message to log."""
        logger.info(f"[Download] {message}")

    def can_advance(self) -> bool:
        """Can advance only after download finishes."""
        return self._download_finished

    def should_skip(self) -> bool:
        """Never skip this page (only shown when download requested)."""
        return False

    def get_page_data(self) -> Dict[str, Any]:
        """
        Get data to pass forward.

        Returns:
            Dictionary with download results
        """
        return {
            'download_completed': self._download_success,
            'config': self._config
        }

    def cleanup(self):
        """Cleanup when leaving page."""
        # Cancel download if still running
        if self._worker and self._worker.isRunning():
            self._worker.cancel_token.cancel()
            self._worker.wait(2000)  # Wait max 2 seconds
            if self._worker.isRunning():
                self._worker.terminate()
