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
    QComboBox,
    QMessageBox,
    QSizePolicy,
)
from PySide6.QtCore import Qt, QTimer, Signal, QThread
from PySide6.QtGui import QFont

from common.constants import APP_NAME
from services.system_capabilities import SystemCapabilities, check_system_capabilities
from utils import gpu_bootstrap, gpu_manifest, gpu_downloader
from utils.download_cleanup import cleanup_download_files, cleanup_download_files_safe
from ui.workers.gpu_download_worker import GpuDownloadWorker
from ui.handlers.gpu_download_handler import on_download_clicked, on_download_progress, on_download_finished

logger = logging.getLogger(__name__)


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
        self._download_failure_count = 0  # Track consecutive download failures for flavor fallback

        self._setup_ui()
        self._run_health_check()

    def _setup_ui(self):
        """Setup dialog UI."""
        # Window setup
        self.setWindowTitle(f"{APP_NAME} - Starting..." if self.startup_mode else f"{APP_NAME} - About")
        # Always modal to prevent I/O contention during downloads
        # Will be set to non-modal temporarily during active download to allow confirmation dialogs
        self.setModal(True)
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
                border-radius: 0px;
                padding: 4px;
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

        # GPU Pack download section (middle, hidden initially)
        # Horizontal layout for flavor selector + download button
        gpu_download_layout = QHBoxLayout()
        gpu_download_layout.setSpacing(5)

        # CUDA flavor selector (combo box)
        self.flavor_combo = QComboBox()
        self.flavor_combo.addItem("CUDA 12.1 (Recommended)", "cu121")
        self.flavor_combo.addItem("CUDA 12.4 (Alternative)", "cu124")
        self.flavor_combo.setToolTip(
            "Select CUDA version:\n"
            "• CUDA 12.1 - Most compatible (driver ≥531)\n"
            "• CUDA 12.4 - Newer, may work better for some systems (driver ≥550)"
        )
        self.flavor_combo.setVisible(False)
        self.flavor_combo.setMinimumWidth(180)
        gpu_download_layout.addWidget(self.flavor_combo)

        # Download GPU Pack button
        self.download_btn = QPushButton("Download GPU Pack")
        self.download_btn.setVisible(False)
        self.download_btn.clicked.connect(lambda: on_download_clicked(self))
        gpu_download_layout.addWidget(self.download_btn)

        button_layout.addLayout(gpu_download_layout)

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
                self.log("")
                # Show GPU and system details
                if self.capabilities.gpu_name:
                    self.log(f"  GPU: {self.capabilities.gpu_name}")
                if self.capabilities.cuda_version:
                    self.log(f"  CUDA: {self.capabilities.cuda_version}")
                if self.capabilities.torch_version:
                    self.log(f"  PyTorch: {self.capabilities.torch_version}")
                self.log("")
                # Show important paths
                if self.config:
                    import os
                    from utils.files import get_localappdata_dir, get_demucs_models_dir
                    data_dir = get_localappdata_dir()
                    models_dir = get_demucs_models_dir(self.config)
                    self.log("Configuration:")
                    self.log(f"  • Data directory: {data_dir}")
                    self.log(f"  • Models directory: {models_dir}")
                    if hasattr(self.config, 'gpu_pack_path') and self.config.gpu_pack_path:
                        self.log(f"  • GPU Pack: {self.config.gpu_pack_path}")
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

                    # Show download controls (button + flavor selector)
                    self.download_btn.setVisible(True)
                    self.flavor_combo.setVisible(True)

                    # Set default flavor based on driver or config
                    if self.config and hasattr(self.config, "gpu_flavor") and self.config.gpu_flavor:
                        # Restore user's previous choice
                        idx = self.flavor_combo.findData(self.config.gpu_flavor)
                        if idx >= 0:
                            self.flavor_combo.setCurrentIndex(idx)
                    else:
                        # Check driver version from capability probe
                        cap = gpu_bootstrap.capability_probe()
                        driver_version = cap.get("driver_version") if cap else None

                        if driver_version and driver_version >= "550.00":
                            # Driver supports both cu121 and cu124 - default to cu121 (more compatible)
                            self.flavor_combo.setCurrentIndex(0)  # cu121
                        else:
                            # Driver only supports cu121 or unknown
                            self.flavor_combo.setCurrentIndex(0)  # cu121
                            # Disable cu124 option if driver too old
                            if driver_version and driver_version < "550.00":
                                self.flavor_combo.model().item(1).setEnabled(False)
                                self.flavor_combo.setItemData(1, "Requires driver ≥550.00", Qt.ItemDataRole.ToolTipRole)
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

    def accept(self):
        """Override accept to show warning when download is active."""
        # Check if download is running before allowing acceptance
        if self._download_worker and self._download_worker.isRunning():
            reply = QMessageBox.question(
                self,
                "Download in Progress",
                "GPU Pack download is in progress.\n\n"
                "Do you want to abort the download?\n\n"
                "Note: Partial download will be deleted. You'll need to restart the download from the beginning.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            if reply == QMessageBox.StandardButton.No:
                return  # Don't accept, keep dialog open

            # Cancel download
            if self._download_worker.cancel_token:
                self._download_worker.cancel_token.cancel()
                self.log("Download cancelled by user")
            self._download_worker.wait(2000)  # Wait up to 2 seconds

            # Clean up partial download files
            if self._download_worker.dest_zip:
                cleanup_download_files(self._download_worker.dest_zip, self.log)

        # Now proceed with standard acceptance
        super().accept()

    def reject(self):
        """Override reject to show warning when download is active."""
        # Check if download is running before allowing rejection
        if self._download_worker and self._download_worker.isRunning():
            reply = QMessageBox.question(
                self,
                "Download in Progress",
                "GPU Pack download is in progress.\n\n"
                "Do you want to abort the download?\n\n"
                "Note: Partial download will be deleted. You'll need to restart the download from the beginning.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            if reply == QMessageBox.StandardButton.No:
                return  # Don't reject, keep dialog open

            # Cancel download
            if self._download_worker.cancel_token:
                self._download_worker.cancel_token.cancel()
                self.log("Download cancelled by user")
            self._download_worker.wait(2000)  # Wait up to 2 seconds

            # Clean up partial download files
            if self._download_worker.dest_zip:
                cleanup_download_files(self._download_worker.dest_zip, self.log)

        # Now proceed with standard rejection
        super().reject()

    def closeEvent(self, event):
        """Handle dialog close event."""
        # Cancel download if running
        if self._download_worker and self._download_worker.isRunning():
            reply = QMessageBox.question(
                self,
                "Download in Progress",
                "GPU Pack download is in progress.\n\n"
                "Do you want to abort the download?\n\n"
                "Note: Partial download will be deleted. You'll need to restart the download from the beginning.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return

            # Cancel download - it will NOT continue in background
            if self._download_worker.cancel_token:
                self._download_worker.cancel_token.cancel()
                self.log("Download cancelled by user")
            self._download_worker.wait(2000)  # Wait up to 2 seconds

            # Clean up partial/corrupted download files
            # This is CRITICAL: cancelled downloads leave corrupt .part files
            # that cause "invalid block type" errors on extraction
            if self._download_worker:
                try:
                    dest_zip = self._download_worker.dest_zip
                    part_file = dest_zip.with_suffix(".part")
                    meta_file = dest_zip.with_suffix(".meta")

                    # Delete all partial download artifacts
                    if part_file.exists():
                        part_file.unlink()
                        logger.info(f"Deleted partial download: {part_file}")
                        self.log("Partial download deleted")
                    if meta_file.exists():
                        meta_file.unlink()
                        logger.info(f"Deleted download metadata: {meta_file}")

                    # Also delete the final ZIP if it exists (might be corrupt)
                    if dest_zip.exists():
                        dest_zip.unlink()
                        logger.info(f"Deleted potentially corrupt download: {dest_zip}")

                except Exception as e:
                    logger.warning(f"Failed to clean up download files: {e}")
                    # Non-critical, continue with close

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
        Modal to prevent UI freezing during downloads/extraction.

        Args:
            parent: Parent widget (main window)
            config: Application config
        """
        dialog = StartupDialog(parent=parent, config=config, startup_mode=False)
        dialog.exec()  # Modal: blocks interaction during downloads
        return dialog.capabilities
