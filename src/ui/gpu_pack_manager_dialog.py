"""
GPU Pack Manager Dialog.

Standalone dialog accessible from Help menu for managing GPU Pack:
- View current GPU status
- Download/Update GPU Pack
- Remove GPU Pack
- View installed models
- Clear cache
"""

import logging
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QTextEdit, QMessageBox, QProgressDialog
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from services.system_capabilities import check_system_capabilities
from ui.gpu_download_dialog import GpuDownloadDialog

logger = logging.getLogger(__name__)


class GpuPackManagerDialog(QDialog):
    """
    GPU Pack Manager dialog.

    Provides centralized interface for all GPU Pack management:
    - Status display
    - Download/update
    - Removal
    - Cache management
    """

    def __init__(self, parent=None, config=None):
        """
        Initialize GPU Pack Manager.

        Args:
            parent: Parent widget
            config: Config object
        """
        super().__init__(parent)
        self.config = config
        self.capabilities = None

        self._setup_ui()
        self._refresh_status()

    def _setup_ui(self):
        """Setup dialog UI."""
        self.setWindowTitle("GPU Pack Manager")
        self.setModal(True)
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)

        # Dark theme
        self.setStyleSheet("""
            QDialog {
                background-color: #353535;
                color: white;
            }
            QLabel {
                color: white;
            }
            QGroupBox {
                color: white;
                border: 1px solid #555;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QPushButton {
                background-color: #2d2d2d;
                color: white;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 8px 16px;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #3d3d3d;
            }
            QPushButton:pressed {
                background-color: #1d1d1d;
            }
            QPushButton:disabled {
                background-color: #2d2d2d;
                color: #666;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Title
        title_label = QLabel("GPU Pack Manager")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)

        # Current Status Section
        status_group = self._create_status_section()
        layout.addWidget(status_group)

        # Actions Section
        actions_group = self._create_actions_section()
        layout.addWidget(actions_group)

        # Info Section
        info_group = self._create_info_section()
        layout.addWidget(info_group)

        layout.addStretch()

        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)

    def _create_status_section(self) -> QGroupBox:
        """Create status display section."""
        group = QGroupBox("Current Status")
        layout = QVBoxLayout(group)
        layout.setSpacing(10)

        # Status labels
        self.pytorch_label = QLabel("PyTorch: Checking...")
        self.pytorch_label.setStyleSheet("font-size: 11pt;")
        layout.addWidget(self.pytorch_label)

        self.cuda_label = QLabel("CUDA: Checking...")
        self.cuda_label.setStyleSheet("font-size: 11pt;")
        layout.addWidget(self.cuda_label)

        self.gpu_label = QLabel("GPU: Checking...")
        self.gpu_label.setStyleSheet("font-size: 11pt;")
        layout.addWidget(self.gpu_label)

        self.performance_label = QLabel("Performance: Checking...")
        self.performance_label.setStyleSheet("font-size: 11pt; font-weight: bold;")
        layout.addWidget(self.performance_label)

        return group

    def _create_actions_section(self) -> QGroupBox:
        """Create actions section."""
        group = QGroupBox("Actions")
        layout = QVBoxLayout(group)
        layout.setSpacing(10)

        # Download button
        self.download_btn = QPushButton("📥 Download GPU Pack")
        self.download_btn.setMinimumHeight(35)
        self.download_btn.clicked.connect(self._on_download_clicked)
        layout.addWidget(self.download_btn)

        # Update button
        self.update_btn = QPushButton("🔄 Update GPU Pack")
        self.update_btn.setMinimumHeight(35)
        self.update_btn.clicked.connect(self._on_update_clicked)
        self.update_btn.setVisible(False)  # Only show if pack installed
        layout.addWidget(self.update_btn)

        # Remove button
        self.remove_btn = QPushButton("🗑️ Remove GPU Pack")
        self.remove_btn.setMinimumHeight(35)
        self.remove_btn.clicked.connect(self._on_remove_clicked)
        self.remove_btn.setVisible(False)  # Only show if pack installed
        layout.addWidget(self.remove_btn)

        # Clear cache button
        clear_cache_btn = QPushButton("🧹 Clear Model Cache")
        clear_cache_btn.setMinimumHeight(35)
        clear_cache_btn.clicked.connect(self._on_clear_cache_clicked)
        layout.addWidget(clear_cache_btn)

        return group

    def _create_info_section(self) -> QGroupBox:
        """Create info display section."""
        group = QGroupBox("Information")
        layout = QVBoxLayout(group)

        self.info_text = QTextEdit()
        self.info_text.setReadOnly(True)
        self.info_text.setMaximumHeight(150)
        self.info_text.setStyleSheet("""
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
        layout.addWidget(self.info_text)

        return group

    def _refresh_status(self):
        """Refresh status display."""
        self.info_text.clear()
        self.info_text.append("Checking system capabilities...")

        # Run capability check
        self.capabilities = check_system_capabilities()

        if not self.capabilities:
            self.pytorch_label.setText("❌ PyTorch: Not available")
            self.cuda_label.setText("❌ CUDA: Not available")
            self.gpu_label.setText("❌ GPU: Not detected")
            self.performance_label.setText("⚠️ Performance: Detection unavailable")
            self.info_text.append("\nSystem capabilities check failed.")
            return

        # Update labels
        if self.capabilities.has_torch:
            self.pytorch_label.setText(f"✅ PyTorch: {self.capabilities.torch_version}")
        else:
            self.pytorch_label.setText("❌ PyTorch: Not available")

        if self.capabilities.has_cuda:
            self.cuda_label.setText(f"✅ CUDA: {self.capabilities.cuda_version}")
        else:
            self.cuda_label.setText("❌ CUDA: Not available")

        if self.capabilities.gpu_name:
            self.gpu_label.setText(f"✅ GPU: {self.capabilities.gpu_name}")
        else:
            self.gpu_label.setText("❌ GPU: Not detected")

        # Performance indicator
        detection_mode = self.capabilities.get_detection_mode()
        if detection_mode == 'gpu':
            self.performance_label.setText("⚡ Performance: GPU Mode (5-10x faster)")
            self.performance_label.setStyleSheet("font-size: 11pt; font-weight: bold; color: #4CAF50;")
            self.download_btn.setEnabled(False)
            self.download_btn.setText("✅ GPU Pack Already Installed")
            self.update_btn.setVisible(True)
            self.remove_btn.setVisible(True)
        elif detection_mode == 'cpu':
            self.performance_label.setText("🐢 Performance: CPU Mode")
            self.performance_label.setStyleSheet("font-size: 11pt; font-weight: bold; color: #FF9800;")
            self.download_btn.setEnabled(True)
            self.update_btn.setVisible(False)
            self.remove_btn.setVisible(False)
        else:
            self.performance_label.setText("⚠️ Performance: Detection unavailable")
            self.performance_label.setStyleSheet("font-size: 11pt; font-weight: bold; color: #f44336;")
            self.download_btn.setEnabled(False)

        # Update info text
        self.info_text.clear()
        self.info_text.append("System Status:")
        self.info_text.append(f"  - Can detect gaps: {'Yes' if self.capabilities.can_detect else 'No'}")
        self.info_text.append(f"  - Detection mode: {detection_mode.upper() if detection_mode else 'None'}")
        self.info_text.append(f"  - FFmpeg: {'Available' if self.capabilities.has_ffmpeg else 'Not available'}")

        if self.config and hasattr(self.config, 'gpu_pack_path') and self.config.gpu_pack_path:
            self.info_text.append(f"\nGPU Pack location:")
            self.info_text.append(f"  {self.config.gpu_pack_path}")

    def _on_download_clicked(self):
        """Handle download button click."""
        if not self.config:
            QMessageBox.warning(self, "Error", "Configuration not available")
            return

        # Show GPU download dialog
        dialog = GpuDownloadDialog(self, self.config)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Refresh status after download
            self._refresh_status()

    def _on_update_clicked(self):
        """Handle update button click."""
        reply = QMessageBox.question(
            self,
            "Update GPU Pack",
            "This will download the latest GPU Pack version.\n\n"
            "Existing GPU Pack will be replaced.\n\n"
            "Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self._on_download_clicked()

    def _on_remove_clicked(self):
        """Handle remove button click."""
        reply = QMessageBox.question(
            self,
            "Remove GPU Pack",
            "This will remove the GPU Pack from your system.\n\n"
            "You will fall back to CPU-only detection.\n\n"
            "Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                # Remove GPU Pack directory
                if self.config and hasattr(self.config, 'gpu_pack_path') and self.config.gpu_pack_path:
                    pack_path = Path(self.config.gpu_pack_path)
                    if pack_path.exists():
                        import shutil
                        shutil.rmtree(pack_path)
                        logger.info(f"Removed GPU Pack from: {pack_path}")

                # Clear config
                if self.config:
                    self.config.gpu_pack_path = ""
                    self.config.gpu_pack_installed_version = ""
                    self.config.save()

                QMessageBox.information(
                    self,
                    "Success",
                    "GPU Pack removed successfully.\n\n"
                    "Application will use CPU mode on next restart."
                )

                self._refresh_status()

            except Exception as e:
                logger.error(f"Failed to remove GPU Pack: {e}")
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Failed to remove GPU Pack:\n\n{str(e)}"
                )

    def _on_clear_cache_clicked(self):
        """Handle clear cache button click."""
        reply = QMessageBox.question(
            self,
            "Clear Model Cache",
            "This will clear the Demucs model cache.\n\n"
            "Models will be re-downloaded when needed.\n\n"
            "Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                from utils.files import get_models_dir
                from pathlib import Path
                import shutil

                models_dir = Path(get_models_dir(self.config))
                if models_dir.exists():
                    shutil.rmtree(models_dir)
                    models_dir.mkdir(parents=True, exist_ok=True)
                    logger.info(f"Cleared model cache: {models_dir}")

                QMessageBox.information(
                    self,
                    "Success",
                    "Model cache cleared successfully."
                )

            except Exception as e:
                logger.error(f"Failed to clear cache: {e}")
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Failed to clear cache:\n\n{str(e)}"
                )
