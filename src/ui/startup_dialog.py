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
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont

from common.constants import APP_NAME
from services.system_capabilities import SystemCapabilities, check_system_capabilities
from utils.gpu_bootstrap import capability_probe, detect_existing_gpu_pack, activate_existing_gpu_pack
from utils.download_cleanup import cleanup_download_files
from ui.workers.gpu_download_worker import GpuDownloadWorker
from ui.handlers.gpu_download_handler import on_download_clicked

logger = logging.getLogger(__name__)


class StartupDialog(QDialog):
    """Unified startup and about dialog.

    Responsibilities:
    - Build static UI chrome (header, log area, buttons)
    - Run system capability probe and render results
    - Offer GPU Pack activation / download when appropriate
    - Provide static convenience factories ``show_startup`` / ``show_about``

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

    def _setup_ui(self):  # High-level orchestration only; detailed pieces in helpers
        self._configure_window()
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)
        self._build_header(layout)
        self._build_log_area(layout)
        self._build_progress_area(layout)
        self._build_skip_checkbox(layout)
        self._build_buttons(layout)

    # --------------------------- UI BUILD HELPERS ---------------------------
    def _configure_window(self) -> None:
        self.setWindowTitle(f"{APP_NAME} - Starting..." if self.startup_mode else f"{APP_NAME} - About")
        self.setModal(True)
        self.setFixedSize(700, 450)
        if self.startup_mode:
            self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(Qt.WindowType.Dialog)
        self._drag_position = None

    def _read_version(self) -> str:
        from utils.files import resource_path

        version_paths = [
            resource_path("VERSION"),
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "VERSION"),
            "VERSION",
        ]
        for version_file in version_paths:
            try:
                if os.path.exists(version_file):
                    with open(version_file, "r", encoding="utf-8") as f:
                        content = f.read().strip()
                        if content:
                            return content
            except Exception as e:  # Non-critical
                logger.debug("Failed reading VERSION at %s: %s", version_file, e)
        return "unknown"

    def _build_header(self, layout: QVBoxLayout) -> None:
        version = self._read_version()
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

        self.status_label = QLabel("Checking system requirements...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("color: #999;")
        layout.addWidget(self.status_label)

    def _build_log_area(self, layout: QVBoxLayout) -> None:
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
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

    def _build_progress_area(self, layout: QVBoxLayout) -> None:
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(True)
        layout.addWidget(self.progress_bar)
        self.progress_label = QLabel("")
        self.progress_label.setVisible(False)
        self.progress_label.setStyleSheet("color: #999; font-size: 9pt;")
        layout.addWidget(self.progress_label)

    def _build_skip_checkbox(self, layout: QVBoxLayout) -> None:
        if self.startup_mode:
            self.dont_show_checkbox = QCheckBox("Don't show this check again (skip if system is healthy)")
            self.dont_show_checkbox.setStyleSheet("color: #999;")
            layout.addWidget(self.dont_show_checkbox)

    def _build_buttons(self, layout: QVBoxLayout) -> None:
        button_layout = QHBoxLayout()
        if self.startup_mode:
            self.start_btn = QPushButton("Start App")
            self.start_btn.clicked.connect(self._on_start_clicked)
            self.start_btn.setDefault(True)
            button_layout.addWidget(self.start_btn)
        else:
            self.close_btn = QPushButton("Close")
            self.close_btn.clicked.connect(self.accept)
            self.close_btn.setDefault(True)
            button_layout.addWidget(self.close_btn)
        button_layout.addStretch()
        self._build_download_controls(button_layout)
        if self.startup_mode:
            self.close_app_btn = QPushButton("Close App")
            self.close_app_btn.setToolTip("Exit application")
            self.close_app_btn.clicked.connect(self._on_close_app_clicked)
            button_layout.addWidget(self.close_app_btn)
        layout.addLayout(button_layout)

    def _build_download_controls(self, parent_layout: QHBoxLayout) -> None:
        gpu_download_layout = QHBoxLayout()
        gpu_download_layout.setSpacing(5)
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
        self.download_btn = QPushButton("Download GPU Pack")
        self.download_btn.setVisible(False)
        self.download_btn.clicked.connect(lambda: on_download_clicked(self))
        gpu_download_layout.addWidget(self.download_btn)
        parent_layout.addLayout(gpu_download_layout)

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

    def _update_ui_for_results(self):  # After health check completes
        if not self.capabilities:
            logger.error("No capabilities detected")
            return
        if not self.capabilities.can_detect:
            self._render_failure_state()
            return
        mode = self.capabilities.get_detection_mode()
        if mode == "gpu":
            self._render_gpu_ready()
        elif mode == "cpu":
            self._render_cpu_mode()

    # ---- Rendering helpers ----
    def _render_gpu_ready(self) -> None:
        self.log("✅ Gap detection ready (GPU acceleration enabled)")
        self.log("")
        self._log_system_details()
        self.status_label.setText("✅ System Ready (GPU Mode)")
        self.status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
        if hasattr(self, "dont_show_checkbox"):
            self.dont_show_checkbox.setChecked(True)

    def _render_cpu_mode(self) -> None:
        # GPU hardware present but CUDA not enabled?
        if self.capabilities.gpu_name and not self.capabilities.has_cuda:
            existing_pack = detect_existing_gpu_pack(self.config)
            if existing_pack:
                self._render_activation_flow(existing_pack)
            else:
                self._render_download_flow()
            self._select_default_flavor()
        else:
            self.log("✅ System ready (CPU mode)")
            self.log("")
            self._log_system_details()
            self.status_label.setText("✅ System Ready (CPU Mode)")
            if hasattr(self, "dont_show_checkbox"):
                self.dont_show_checkbox.setChecked(True)
        self.status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")

    def _render_activation_flow(self, existing_pack):
        self.log("⚡ GPU Pack Detected (Not Activated)")
        self.log(f"  • Hardware detected: {self.capabilities.gpu_name}")
        self.log(f"  • GPU Pack found at: {existing_pack}")
        self.log("  • Current mode: CPU")
        self.log("")
        self.log("A GPU Pack is already installed but not activated.")
        self.log("")
        self.log("Benefits of activating:")
        self.log("  • 5-10x faster gap detection")
        self.log("  • Process songs in 10-30 seconds (vs 2-3 minutes)")
        self.log("  • No download required - activation is instant")
        self.log("")
        self.log("→ Click 'Activate GPU Pack' button below to enable GPU acceleration")
        self.status_label.setText("✅ System Ready (CPU Mode - GPU Pack Available)")
        self.download_btn.setText("Activate GPU Pack")
        self.download_btn.setVisible(True)
        self.flavor_combo.setVisible(False)
        self._existing_pack_path = existing_pack
        try:
            self.download_btn.clicked.disconnect()
        except Exception:
            pass
        self.download_btn.clicked.connect(self._on_activate_gpu_pack)

    def _render_download_flow(self):
        self.log("⚡ GPU Pack Available for Download")
        self.log(f"  • Hardware detected: {self.capabilities.gpu_name}")
        self.log("  • Current mode: CPU (GPU Pack not installed)")
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
        self.download_btn.setText("Download GPU Pack")
        self.download_btn.setVisible(True)
        self.flavor_combo.setVisible(True)

    def _select_default_flavor(self) -> None:
        # Restore previous choice if available
        if self.config and getattr(self.config, "gpu_flavor", None):
            idx = self.flavor_combo.findData(self.config.gpu_flavor)
            if idx >= 0:
                self.flavor_combo.setCurrentIndex(idx)
                return
        cap = capability_probe()
        driver_version = cap.get("driver_version") if cap else None
        self.flavor_combo.setCurrentIndex(0)  # cu121 default
        if driver_version and driver_version < "550.00":
            # Disable cu124 if driver too old
            try:
                self.flavor_combo.model().item(1).setEnabled(False)
                self.flavor_combo.setItemData(1, "Requires driver ≥550.00", Qt.ItemDataRole.ToolTipRole)
            except Exception:
                pass

    def _render_failure_state(self) -> None:
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

    def _log_system_details(self):
        """Log comprehensive system information (for About dialog and detailed startup info)."""
        from utils.files import resource_path
        import os

        # Get version from VERSION file
        app_version = "unknown"
        try:
            version_file = resource_path("VERSION")
            if os.path.exists(version_file):
                with open(version_file, "r") as f:
                    app_version = f.read().strip()
        except Exception:
            pass

        # Get Qt version
        try:
            from PySide6 import __version__ as pyside_version
        except Exception:
            pyside_version = "unknown"

        # System Components
        self.log("System Components:")
        self.log(f"  • Application: {app_version}")
        self.log(f"  • Qt Framework: {pyside_version}")

        # PyTorch & GPU
        if self.capabilities.torch_version:
            self.log(f"  • PyTorch: {self.capabilities.torch_version}")
        if self.capabilities.has_cuda and self.capabilities.cuda_version:
            self.log(f"  • CUDA: {self.capabilities.cuda_version}")
        if self.capabilities.gpu_name:
            self.log(f"  • GPU: {self.capabilities.gpu_name}")

        # Audio Processing
        if self.capabilities.ffmpeg_version:
            self.log(f"  • FFmpeg: {self.capabilities.ffmpeg_version}")
        if self.capabilities.has_ffprobe:
            self.log("  • FFprobe: Available")

        # Check Python libraries
        try:
            import librosa

            self.log(f"  • librosa: {librosa.__version__}")
        except Exception:
            pass

        try:
            import soundfile

            self.log(f"  • soundfile: {soundfile.__version__}")
        except Exception:
            pass

        self.log("")

        # Configuration Paths
        if self.config:
            try:
                from utils.files import get_localappdata_dir, get_demucs_models_dir

                data_dir = get_localappdata_dir()
                models_dir = get_demucs_models_dir(self.config)

                self.log("Configuration:")
                self.log(f"  • Data directory: {data_dir}")
                self.log(f"  • Models directory: {models_dir}")
                if hasattr(self.config, "gpu_pack_path") and self.config.gpu_pack_path:
                    self.log(f"  • GPU Pack: {self.config.gpu_pack_path}")
            except Exception:
                # Skip path display if config is mocked or paths unavailable
                pass

        self.log("")

    def _on_activate_gpu_pack(self):
        """Handle Activate GPU Pack button click."""
        if not hasattr(self, "_existing_pack_path"):
            logger.error("No existing pack path stored")
            return

        pack_path = self._existing_pack_path

        self.log("")
        self.log(f"Activating GPU Pack at {pack_path}...")

        # Disable button during activation
        self.download_btn.setEnabled(False)
        self.download_btn.setText("Activating...")

        # Activate the pack
        success = activate_existing_gpu_pack(self.config, pack_path)

        if success:
            self.log("✅ GPU Pack activated successfully!")
            self.log("")
            self.log("⚠️ Please restart the application for changes to take effect.")
            self.log("")
            self.status_label.setText("✅ GPU Pack Activated (Restart Required)")
            self.status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")

            # Change button to close/restart prompt
            self.download_btn.setText("Restart App")
            self.download_btn.setEnabled(True)
            self.download_btn.clicked.disconnect()
            self.download_btn.clicked.connect(self._on_restart_for_gpu)
        else:
            self.log("❌ Failed to activate GPU Pack")
            self.log("")
            self.status_label.setText("❌ Activation Failed")
            self.status_label.setStyleSheet("color: #f44336; font-weight: bold;")

            # Re-enable button
            self.download_btn.setText("Activate GPU Pack")
            self.download_btn.setEnabled(True)

    def _on_restart_for_gpu(self):
        """Handle restart request after GPU Pack activation."""
        from PySide6.QtWidgets import QMessageBox

        reply = QMessageBox.question(
            self,
            "Restart Required",
            "GPU Pack has been activated. The application needs to restart to use GPU acceleration.\n\n" "Restart now?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )

        if reply == QMessageBox.StandardButton.Yes:
            logger.info("User confirmed restart after GPU Pack activation")
            import sys
            import os

            # Use sys.executable to restart Python interpreter with same script
            os.execl(sys.executable, sys.executable, *sys.argv)
        else:
            # User chose not to restart - close dialog
            if self.startup_mode:
                self.completed.emit(self.capabilities)
            self.accept()

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

    # --------------------------- Download guarding ---------------------------
    def _confirm_abort_active_download(self) -> bool:
        if not (self._download_worker and self._download_worker.isRunning()):
            return True
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
            return False
        # Cancel + cleanup
        if self._download_worker.cancel_token:
            self._download_worker.cancel_token.cancel()
            self.log("Download cancelled by user")
        self._download_worker.wait(2000)
        if getattr(self._download_worker, "dest_zip", None):
            cleanup_download_files(self._download_worker.dest_zip, self.log)
        return True

    def accept(self):
        if not self._confirm_abort_active_download():
            return
        super().accept()

    def reject(self):
        if not self._confirm_abort_active_download():
            return
        super().reject()

    def closeEvent(self, event):
        """Handle dialog close event."""
        if self._download_worker and self._download_worker.isRunning():
            if not self._confirm_abort_active_download():
                event.ignore()
                return
            # Extra deep cleanup of artefacts (partial *.part, *.meta, corrupt zip)
            try:
                dest_zip = self._download_worker.dest_zip
                part_file = dest_zip.with_suffix(".part")
                meta_file = dest_zip.with_suffix(".meta")
                for f in (part_file, meta_file, dest_zip):
                    if f.exists():
                        f.unlink()
                        logger.info("Deleted download artefact %s", f)
                        if f is part_file:
                            self.log("Partial download deleted")
            except Exception as e:
                logger.debug("Cleanup artefact removal non-critical error: %s", e)

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

            # Check if there's an existing GPU Pack that needs activation
            # (this takes precedence over health check - user should be prompted)
            if capabilities and capabilities.can_detect:
                existing_pack = detect_existing_gpu_pack(config)
                if existing_pack:
                    logger.info(
                        f"GPU Pack detected at {existing_pack} but not enabled - "
                        "showing startup dialog to prompt activation"
                    )
                    # Fall through to show dialog
                else:
                    logger.info("Health check passed - skipping startup dialog (splash_dont_show_health=True)")
                    return capabilities
            else:
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
