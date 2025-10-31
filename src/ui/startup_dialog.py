"""
Simplified Startup/About Dialog

Single dialog for:
- System health check at startup
- Optional GPU Pack download
- Reusable as "About" dialog from Help menu

No wizard, no pagination - just one simple dialog.
"""

import os
import logging
from typing import Optional
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QProgressBar,
    QCheckBox,
    QMessageBox,
    QSizePolicy,
)
from PySide6.QtCore import Qt, QTimer, Signal, QThread
from PySide6.QtGui import QFont

from common.constants import APP_NAME
from services.system_capabilities import SystemCapabilities, check_system_capabilities
from utils import gpu_bootstrap, gpu_manifest, gpu_downloader

logger = logging.getLogger(__name__)


class GpuDownloadWorker(QThread):
    """
    Worker thread for GPU Pack download.

    Signals:
        progress: (percentage: int, message: str) - download progress updates
        finished: (success: bool, message: str) - download completion status
        log_message: (message: str) - log message for UI display
    """

    progress = Signal(int, str)
    finished = Signal(bool, str)
    log_message = Signal(str)

    def __init__(self, config, chosen_manifest, pack_dir: Path, dest_zip: Path):
        super().__init__()
        self.config = config
        self.chosen_manifest = chosen_manifest
        self.pack_dir = pack_dir
        self.dest_zip = dest_zip
        self.cancel_token = gpu_downloader.CancelToken()

    def run(self):
        """Download and extract GPU Pack."""
        try:
            # Progress callback - convert bytes to MB and calculate speed/ETA
            def on_progress(bytes_downloaded, total_bytes):
                if self.cancel_token.is_cancelled():
                    return

                downloaded_mb = bytes_downloaded / (1024 * 1024)
                total_mb = total_bytes / (1024 * 1024)
                percentage = int((bytes_downloaded / total_bytes) * 100) if total_bytes > 0 else 0

                # Simple progress message
                message = f"{downloaded_mb:.1f} MB / {total_mb:.1f} MB"
                self.progress.emit(percentage, message)

            # Download
            logger.info(f"Starting download: {self.chosen_manifest.url}")
            self.log_message.emit(f"Downloading from: {self.chosen_manifest.url}")

            download_success = gpu_downloader.download_with_resume(
                url=self.chosen_manifest.url,
                dest_zip=self.dest_zip,
                expected_sha256=self.chosen_manifest.sha256,
                expected_size=self.chosen_manifest.size,
                progress_cb=on_progress,
                cancel_token=self.cancel_token,
                config=self.config,
            )

            if self.cancel_token.is_cancelled():
                self.finished.emit(False, "Download cancelled by user. You can resume the download later.")
                return

            if not download_success:
                self.finished.emit(False, "Download verification failed. Please try again.")
                return

            # Extract
            logger.info(f"Extracting to {self.pack_dir}")
            self.log_message.emit(f"Extracting to: {self.pack_dir}")
            self.progress.emit(95, "Extracting GPU Pack...")

            import zipfile

            with zipfile.ZipFile(self.dest_zip, "r") as zip_ref:
                zip_ref.extractall(self.pack_dir)

            logger.info("GPU Pack installed successfully")
            self.finished.emit(True, "GPU Pack installed successfully!")

        except Exception as e:
            logger.error(f"GPU Pack download failed: {e}", exc_info=True)

            # User-friendly error messages
            if "404" in str(e):
                error_msg = "GPU Pack not available for your system yet. Please check back later."
            elif "network" in str(e).lower() or "connection" in str(e).lower():
                error_msg = f"Network error: {str(e)}\n\nPlease check your internet connection and try again."
            else:
                error_msg = f"Download failed: {str(e)}"

            self.finished.emit(False, error_msg)


class StartupDialog(QDialog):
    """
    Unified startup and about dialog.

    Shows system health check and optionally offers GPU Pack download.
    """

    # Signal emitted when dialog completes
    completed = Signal(object)  # SystemCapabilities or None

    def __init__(self, parent=None, config=None, startup_mode=True):
        """
        Initialize startup dialog.

        Args:
            parent: Parent widget (None for startup, main window for About)
            config: Application config
            startup_mode: If True, exits app on close.
                         If False, just closes dialog (for About mode)
        """
        super().__init__(parent)
        self.config = config
        self.startup_mode = startup_mode
        self.capabilities: Optional[SystemCapabilities] = None
        self._download_worker: Optional[GpuDownloadWorker] = None

        self._setup_ui()
        self._run_health_check()

    def _setup_ui(self):
        """Setup dialog UI."""
        # Window setup
        self.setWindowTitle(f"{APP_NAME} - Starting..." if self.startup_mode else f"{APP_NAME} - About")
        # Modal only in startup mode, non-modal in About mode
        self.setModal(self.startup_mode)
        self.setFixedSize(700, 450)

        # Window flags - make dialog movable
        if self.startup_mode:
            # FramelessWindowHint allows custom drag, but keep title bar
            self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(Qt.WindowType.Dialog)

        # Enable mouse tracking for drag and drop
        self._drag_position = None  # Main layout
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        # App title and version
        from utils.files import resource_path

        version = "unknown"
        try:
            # Try multiple paths for VERSION file
            version_paths = [
                resource_path("VERSION"),
                os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "VERSION"),
                "VERSION",
            ]

            for version_file in version_paths:
                if os.path.exists(version_file):
                    with open(version_file, "r", encoding="utf-8") as f:
                        version = f.read().strip()
                        if version:  # Found valid version
                            break
        except Exception as e:
            logger.warning(f"Failed to read VERSION file: {e}")

        title_label = QLabel(f"{APP_NAME} {version}")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        subtitle_label = QLabel("System Health Check")
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle_label.setStyleSheet("color: #999; font-size: 11pt;")
        layout.addWidget(subtitle_label)

        # Status label
        self.status_label = QLabel("Checking system requirements...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("color: #999;")
        layout.addWidget(self.status_label)

        # Log output area
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        # self.log_text.setMaximumHeight(300)  # Limit height to prevent overlay
        self.log_text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.log_text.setStyleSheet(
            """
            QTextEdit {
                background-color: #1E1E1E;
                color: #E0E0E0;
                border: 1px solid #3a3a3a;
                border-radius: 4px;
                padding: 8px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 9pt;
            }
        """
        )
        layout.addWidget(self.log_text)

        # Progress bar (full width, no extra spacing)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(True)
        layout.addWidget(self.progress_bar)

        # Progress status label
        self.progress_label = QLabel("")
        self.progress_label.setVisible(False)
        self.progress_label.setStyleSheet("color: #999; font-size: 9pt;")
        layout.addWidget(self.progress_label)

        # "Don't show again" checkbox (only in startup mode)
        if self.startup_mode:
            self.dont_show_checkbox = QCheckBox("Don't show this check again (skip if system is healthy)")
            self.dont_show_checkbox.setStyleSheet("color: #999;")
            layout.addWidget(self.dont_show_checkbox)

        # Buttons layout
        button_layout = QHBoxLayout()

        # Start/Close button (leftmost)
        if self.startup_mode:
            self.start_btn = QPushButton("Start App")
            self.start_btn.clicked.connect(self._on_start_clicked)
            self.start_btn.setDefault(True)
            button_layout.addWidget(self.start_btn)
        else:
            # About mode - Close button on left
            self.close_btn = QPushButton("Close")
            self.close_btn.clicked.connect(self.accept)
            self.close_btn.setDefault(True)
            button_layout.addWidget(self.close_btn)

        button_layout.addStretch()

        # Download GPU Pack button (middle, hidden initially)
        self.download_btn = QPushButton("Download GPU Pack")
        self.download_btn.setVisible(False)
        self.download_btn.clicked.connect(self._on_download_clicked)
        button_layout.addWidget(self.download_btn)

        # Close app button (rightmost, startup mode only)
        if self.startup_mode:
            self.close_app_btn = QPushButton("Close App")
            self.close_app_btn.setToolTip("Exit application")
            self.close_app_btn.clicked.connect(self._on_close_app_clicked)
            button_layout.addWidget(self.close_app_btn)

        layout.addLayout(button_layout)

    def _run_health_check(self):
        """Run system capability checks after short delay."""
        QTimer.singleShot(100, self._do_health_check)

    def _do_health_check(self):
        """Perform health check."""
        self.log("Starting system checks...")
        self.log("")

        # Run checks with progress logging
        self.capabilities = check_system_capabilities(log_callback=self.log)

        self.log("")

        # Update UI based on results
        self._update_ui_for_results()

    def _update_ui_for_results(self):
        """Update UI based on capability check results."""
        if not self.capabilities:
            logger.error("No capabilities detected")
            return

        # Determine overall status
        if self.capabilities.can_detect:
            detection_mode = self.capabilities.get_detection_mode()

            if detection_mode == "gpu":
                self.log("✅ Gap detection ready (GPU acceleration enabled)")
                self.status_label.setText("✅ System Ready (GPU Mode)")
                self.status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
            elif detection_mode == "cpu":
                # Check if GPU is available but pack not installed
                if self.capabilities.gpu_name and not self.capabilities.has_cuda:
                    self.log("⚡ GPU Pack Available for Download")
                    self.log(f"  • Hardware detected: {self.capabilities.gpu_name}")
                    self.log(f"  • Current mode: CPU (GPU Pack not installed)")
                    self.log("")
                    self.log("Benefits of GPU Pack:")
                    self.log("  • 5-10x faster gap detection")
                    self.log("  • Process songs in 10-30 seconds (vs 2-3 minutes)")
                    self.log("  • Download size: ~2.5 GB")
                    self.log("")
                    self.log("→ Click 'Download GPU Pack' button below to enable GPU acceleration")
                    self.log("")
                    self.log("💡 Note: You can download the GPU Pack later from the About menu")
                    self.status_label.setText("✅ System Ready (CPU Mode - GPU Available)")

                    # Show download button
                    self.download_btn.setVisible(True)
                else:
                    self.log("✅ System ready (CPU mode)")
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

    def _on_download_clicked(self):
        """Handle Download GPU Pack button click."""
        # Disable buttons during download
        self.download_btn.setEnabled(False)
        if hasattr(self, "start_btn"):
            self.start_btn.setEnabled(False)

        # Show progress UI
        self.progress_bar.setVisible(True)
        self.progress_label.setVisible(True)
        self.progress_bar.setValue(0)

        self.log("Preparing GPU Pack download...")

        # Get appropriate manifest
        try:
            # Get manifests and capability info
            from utils.files import resource_path

            version_file = resource_path("VERSION")
            app_version = "unknown"
            if os.path.exists(version_file):
                with open(version_file, "r", encoding="utf-8") as f:
                    app_version = f.read().strip()

            manifests = gpu_manifest.load_local_manifest(app_version)
            cap = gpu_bootstrap.capability_probe()

            # Choose pack based on driver version
            flavor_override = (
                self.config.gpu_flavor
                if self.config and hasattr(self.config, "gpu_flavor") and self.config.gpu_flavor
                else None
            )
            chosen_manifest = gpu_manifest.choose_pack(
                manifests, cap.get("driver_version") if cap else None, flavor_override
            )

            if not chosen_manifest:
                QMessageBox.critical(
                    self,
                    "GPU Pack Not Available",
                    "No GPU Pack manifest available for your system.\n\n"
                    "This could mean:\n"
                    "• GPU Pack is not yet available for your Python version\n"
                    "• Your system is not compatible\n\n"
                    "Please check the documentation for supported configurations.",
                )
                self._reset_download_ui()
                return

            # Prepare paths using config (centralized path management)
            from pathlib import Path

            # Use config to get GPU Pack directory (respects user config and provides defaults)
            pack_dir = Path(self.config.get_gpu_pack_dir(chosen_manifest.torch_version))
            pack_dir.mkdir(parents=True, exist_ok=True)

            # Store ZIP in parent directory (gpu_runtime/)
            torch_version_normalized = chosen_manifest.torch_version.replace("+", "-")
            dest_zip = pack_dir.parent / f"gpu_pack_{torch_version_normalized}.zip"

            # Log download destination (both to file and UI)
            logger.info(f"GPU Pack download destination: {pack_dir}")
            logger.info(f"Download ZIP location: {dest_zip}")
            self.log(f"Download destination: {pack_dir}")

            # Start download worker
            self._download_worker = GpuDownloadWorker(
                config=self.config, chosen_manifest=chosen_manifest, pack_dir=pack_dir, dest_zip=dest_zip
            )
            self._download_worker.progress.connect(self._on_download_progress)
            self._download_worker.finished.connect(self._on_download_finished)
            self._download_worker.log_message.connect(self.log)  # Connect log signal to UI
            self._download_worker.start()

        except Exception as e:
            logger.error(f"Failed to start GPU Pack download: {e}", exc_info=True)
            QMessageBox.critical(self, "Download Failed", f"Failed to start GPU Pack download:\n\n{str(e)}")
            self._reset_download_ui()

    def _on_download_progress(self, percentage: int, message: str):
        """Handle download progress update."""
        self.progress_bar.setValue(percentage)
        self.progress_label.setText(message)

    def _on_download_finished(self, success: bool, message: str):
        """Handle download completion."""
        if success:
            self.log("")
            self.log("✅ GPU Pack downloaded successfully!")
            self.log("   Restart the application to use GPU acceleration")

            # Save GPU Pack path to config
            if self._download_worker and self.config:
                pack_dir = self._download_worker.pack_dir
                self.config.gpu_pack_path = str(pack_dir)
                self.config.gpu_opt_in = True  # Enable GPU
                try:
                    self.config.save_config()
                    logger.info(f"Saved GPU Pack path to config: {pack_dir}")
                except Exception as e:
                    logger.error(f"Failed to save GPU Pack path: {e}")

            # Update status label to show restart warning
            self.status_label.setText("⚠️ GPU Pack Installed - Please Restart Application")
            self.status_label.setStyleSheet("color: #FFA500; font-weight: bold;")

            # Disable Start App button - user MUST restart
            if hasattr(self, "start_btn"):
                self.start_btn.setEnabled(False)
                self.start_btn.setText("Restart Required")

            # Hide download button
            self.download_btn.setVisible(False)

            # Clean up worker reference
            self._download_worker = None

            QMessageBox.information(
                self,
                "Download Complete",
                "GPU Pack downloaded and installed successfully!\n\n"
                "Please restart the application to enable GPU acceleration.\n\n"
                "Click 'Close App' to exit, then start the application again.",
            )
        else:
            # Clean up worker reference
            self._download_worker = None

            self.log("")
            self.log(f"❌ Download failed: {message}")

            # Ask user if they want to retry
            reply = QMessageBox.question(
                self,
                "Download Failed",
                f"GPU Pack download failed:\n\n{message}\n\n" "Would you like to retry the download?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )

            if reply == QMessageBox.StandardButton.Yes:
                # Clean up any partial/corrupted download files before retry
                try:
                    from pathlib import Path
                    from utils.files import get_localappdata_dir

                    if self.config and hasattr(self.config, "data_dir") and self.config.data_dir:
                        pack_dir = Path(self.config.data_dir) / "gpu_runtime"
                    else:
                        localappdata = get_localappdata_dir()
                        pack_dir = Path(localappdata) / "gpu_runtime"

                    # Delete all .zip files in pack_dir to ensure fresh download
                    if pack_dir.exists():
                        for zip_file in pack_dir.glob("*.zip"):
                            try:
                                zip_file.unlink()
                                logger.info(f"Deleted corrupted download file: {zip_file}")
                            except Exception as e:
                                logger.warning(f"Failed to delete {zip_file}: {e}")
                except Exception as e:
                    logger.warning(f"Failed to clean up download files: {e}")

                # Reset UI and retry download
                self._reset_download_ui()
                self.log("")
                self.log("Cleaning up failed download and retrying...")
                # Small delay to let UI update
                QTimer.singleShot(100, self._on_download_clicked)
                return  # Don't reset UI yet, retry is starting

        self._reset_download_ui()

    def _reset_download_ui(self):
        """Reset download UI elements."""
        self.progress_bar.setVisible(False)
        self.progress_label.setVisible(False)
        self.download_btn.setEnabled(True)
        if hasattr(self, "start_btn"):
            self.start_btn.setEnabled(True)

    def _on_start_clicked(self):
        """Handle Start App button click."""
        # Save "don't show" preference if checked
        if hasattr(self, "dont_show_checkbox") and self.dont_show_checkbox.isChecked():
            if self.config:
                self.config.splash_dont_show_health = True
                self.config.save()
                logger.info("Health check auto-show disabled")

        # Emit completion signal with capabilities
        self.completed.emit(self.capabilities)
        self.accept()

    def _on_close_app_clicked(self):
        """Handle Close button click - exits application."""
        logger.info("User clicked Close - terminating application")

        # Reject dialog and force exit
        self.reject()

        # Raise SystemExit to stop the application startup
        import sys

        sys.exit(0)

    def log(self, message: str):
        """Add message to log output."""
        self.log_text.append(message)
        # Auto-scroll to bottom
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def mousePressEvent(self, event):
        """Handle mouse press for window dragging."""
        # Enable window dragging
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Handle mouse move for window dragging."""
        if event.buttons() == Qt.MouseButton.LeftButton and self._drag_position is not None:
            self.move(event.globalPosition().toPoint() - self._drag_position)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Handle mouse release to end dragging."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_position = None
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def closeEvent(self, event):
        """Handle dialog close event."""
        # Cancel download if running
        if self._download_worker and self._download_worker.isRunning():
            reply = QMessageBox.question(
                self,
                "Download in Progress",
                "GPU Pack download is in progress.\n\n" "Are you sure you want to cancel?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return

            # Cancel download
            if self._download_worker.cancel_token:
                self._download_worker.cancel_token.cancel()
            self._download_worker.wait(2000)  # Wait up to 2 seconds

        # In startup mode, exit application when closing with X
        if self.startup_mode:
            # Reject the dialog (don't start app)
            self.reject()
            # Use sys.exit to terminate the application
            import sys

            sys.exit(0)
        else:
            event.accept()

    @staticmethod
    def show_startup(parent=None, config=None) -> Optional[SystemCapabilities]:
        """
        Show dialog in startup mode.

        Respects the splash_dont_show_health config setting:
        - If enabled, only shows dialog when there's a critical error
        - If disabled, always shows dialog for health check

        Args:
            parent: Parent widget (usually None for startup)
            config: Application config

        Returns:
            SystemCapabilities if successful, None if cancelled
        """
        # Check if we should skip the dialog
        skip_if_healthy = config and hasattr(config, "splash_dont_show_health") and config.splash_dont_show_health

        if skip_if_healthy:
            # Run quick health check without showing dialog
            from services.system_capabilities import check_system_capabilities

            capabilities = check_system_capabilities()

            # Only show dialog if there's a critical error
            if capabilities and capabilities.can_detect:
                logger.info("Health check passed - skipping startup dialog (splash_dont_show_health=True)")
                return capabilities

            # Critical error - show dialog anyway
            logger.warning("Health check failed - showing startup dialog despite splash_dont_show_health=True")

        # Show the dialog
        dialog = StartupDialog(parent=parent, config=config, startup_mode=True)
        result = dialog.exec()

        if result == QDialog.DialogCode.Accepted:
            return dialog.capabilities
        return None

    @staticmethod
    def show_about(parent=None, config=None):
        """
        Show dialog in About mode (no countdown, just informational).

        Args:
            parent: Parent widget (main window)
            config: Application config
        """
        dialog = StartupDialog(parent=parent, config=config, startup_mode=False)
        dialog.show()  # Non-modal: allows interaction with main window
        return dialog  # Return reference so dialog doesn't get garbage collected
