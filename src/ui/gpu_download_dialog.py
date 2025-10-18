"""
GPU Pack Download Dialog with Progress

Provides an enhanced dialog for downloading and installing GPU Pack
with progress visualization and GPU information display.
"""

import logging
from pathlib import Path
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QProgressBar, QTextEdit, QMessageBox, QCheckBox)
from PySide6.QtCore import QThread, Signal

from utils import gpu_bootstrap, gpu_manifest, gpu_downloader
from utils.files import resource_path

logger = logging.getLogger(__name__)


class GpuDownloadWorker(QThread):
    """Background worker for GPU Pack download"""

    progress = Signal(int, str)  # (percentage, status_message)
    finished = Signal(bool, str)  # (success, message)

    def __init__(self, config, chosen_manifest, pack_dir, dest_zip):
        super().__init__()
        self.config = config
        self.chosen = chosen_manifest
        self.pack_dir = pack_dir
        self.dest_zip = dest_zip

    def run(self):
        try:
            # Download with progress
            def progress_cb(downloaded, total):
                pct = int((downloaded / total * 100)) if total > 0 else 0
                mb_down = downloaded / (1024**2)
                mb_total = total / (1024**2)
                msg = f"Downloading: {mb_down:.1f} MB / {mb_total:.1f} MB"
                self.progress.emit(pct, msg)

            self.progress.emit(0, "Starting download...")

            # Download - returns False on failure, raises on network errors
            try:
                download_success = gpu_downloader.download_with_resume(
                    url=self.chosen.url,
                    dest_zip=self.dest_zip,
                    expected_sha256=self.chosen.sha256,
                    expected_size=self.chosen.size,
                    progress_cb=progress_cb
                )

                if not download_success:
                    # Download failed (checksum, size, or cancelled)
                    error_msg = (
                        f"❌ Download verification failed\n\n"
                        f"The downloaded file failed verification checks:\n"
                        f"• File may be corrupted\n"
                        f"• Checksum mismatch detected\n"
                        f"• Download was cancelled\n\n"
                        f"Please check the logs for details and try again."
                    )
                    logger.error("GPU Pack download failed verification")
                    self.finished.emit(False, error_msg)
                    return

            except Exception as download_error:
                # Network error or other exception
                error_str = str(download_error)

                # Check if it's a 404 error (file not available yet)
                if "404" in error_str or "Not Found" in error_str:
                    error_msg = (
                        f"❌ GPU Pack download not available yet\n\n"
                        f"The GPU Pack files have not been uploaded to GitHub releases yet.\n\n"
                        f"Alternative installation methods:\n\n"
                        f"1. CLI with offline ZIP:\n"
                        f"   • Download the GPU Pack ZIP manually\n"
                        f"   • Run: usdxfixgap.exe --setup-gpu-zip <path-to-zip>\n\n"
                        f"2. Use system-wide CUDA:\n"
                        f"   • If you have CUDA 12.1 or 12.4 installed system-wide,\n"
                        f"     the app will detect and use it automatically\n\n"
                        f"Attempted URL:\n{self.chosen.url}"
                    )
                else:
                    error_msg = (
                        f"❌ Download failed:\n\n{error_str}\n\n"
                        f"Possible causes:\n"
                        f"• Network connectivity issues\n"
                        f"• GPU Pack not available for your version\n"
                        f"• Server temporarily unavailable\n\n"
                        f"Please try again later or check your internet connection."
                    )

                logger.error(f"GPU Pack download failed: {download_error}", exc_info=True)
                self.finished.emit(False, error_msg)
                return

            self.progress.emit(100, "Download complete. Extracting...")

            # Verify downloaded file exists before extraction
            if not self.dest_zip.exists():
                error_msg = (
                    f"❌ Downloaded file not found\n\n"
                    f"Expected file: {self.dest_zip}\n\n"
                    f"The download may have failed or been cancelled.\n"
                    f"Please try again."
                )
                logger.error(f"Downloaded file not found: {self.dest_zip}")
                self.finished.emit(False, error_msg)
                return

            # Extract
            try:
                gpu_downloader.extract_zip(self.dest_zip, self.pack_dir)
                gpu_downloader.write_install_record(self.pack_dir, self.chosen)
            except Exception as extract_error:
                # Extraction failed - report it
                error_msg = f"❌ Extraction failed:\n\n{str(extract_error)}\n\nThe downloaded file may be corrupted. Please try again."
                logger.error(f"GPU Pack extraction failed: {extract_error}", exc_info=True)
                self.finished.emit(False, error_msg)
                return

            # Update config
            self.config.gpu_pack_installed_version = self.chosen.app_version
            self.config.gpu_pack_path = str(self.pack_dir)
            self.config.gpu_opt_in = True
            self.config.save_config()

            # Clean up zip files
            if self.dest_zip.exists():
                self.dest_zip.unlink()
            part_file = Path(str(self.dest_zip) + ".part")
            if part_file.exists():
                part_file.unlink()
            meta_file = Path(str(self.dest_zip) + ".meta")
            if meta_file.exists():
                meta_file.unlink()

            # Verify installation by checking CUDA
            try:
                # Bootstrap the newly installed pack
                gpu_bootstrap.enable_gpu_runtime(self.pack_dir, self.config)

                # Validate CUDA
                expected_cuda = "12.1" if self.chosen.flavor == "cu121" else "12.4"
                success, error_msg = gpu_bootstrap.validate_cuda_torch(expected_cuda)

                if success:
                    import torch
                    cuda_version = torch.version.cuda
                    pytorch_version = torch.__version__
                    device_name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "Unknown"

                    msg = (f"✅ Installation successful!\n\n"
                           f"GPU Pack Details:\n"
                           f"  • CUDA Version: {cuda_version}\n"
                           f"  • PyTorch Version: {pytorch_version}\n"
                           f"  • GPU Device: {device_name}\n"
                           f"  • Installation Path: {self.pack_dir}\n\n"
                           f"GPU acceleration is now enabled!")

                    logger.info(f"GPU Pack installed successfully: CUDA {cuda_version}, PyTorch {pytorch_version}, Device: {device_name}")
                    self.finished.emit(True, msg)
                else:
                    msg = f"⚠️ Installation completed but CUDA validation failed:\n{error_msg}\n\nYou may need to restart the application."
                    logger.warning(f"GPU Pack installed but validation failed: {error_msg}")
                    self.finished.emit(True, msg)
            except Exception as e:
                msg = f"✅ Installation completed!\n\nGPU Pack installed to: {self.pack_dir}\n\nPlease restart the application to use GPU acceleration."
                logger.info(f"GPU Pack installed successfully to: {self.pack_dir}")
                self.finished.emit(True, msg)

        except Exception as e:
            # Unexpected error - this shouldn't happen anymore but keep as safety net
            error_msg = f"❌ Installation failed:\n\n{str(e)}\n\nPlease check the logs for more details."
            logger.error(f"GPU Pack installation failed with unexpected error: {e}", exc_info=True)
            self.finished.emit(False, error_msg)


class GpuPackDownloadDialog(QDialog):
    """Enhanced dialog for GPU Pack download with progress"""

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.worker = None

        self.setWindowTitle("GPU Acceleration Setup")
        self.setModal(True)
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)

        self._setup_ui()
        self._load_gpu_info()

    def _setup_ui(self):
        layout = QVBoxLayout()

        # Title
        title = QLabel("🚀 GPU Acceleration Available!")
        title_font = title.font()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        # GPU Info section
        self.info_text = QTextEdit()
        self.info_text.setReadOnly(True)
        self.info_text.setMaximumHeight(200)
        layout.addWidget(self.info_text)

        # Progress section
        self.progress_label = QLabel("Ready to download")
        layout.addWidget(self.progress_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # "Don't ask again" checkbox
        self.dont_ask_checkbox = QCheckBox("Don't show this dialog again")
        self.dont_ask_checkbox.setToolTip("You can still download GPU Pack from Settings → Download GPU Pack")
        layout.addWidget(self.dont_ask_checkbox)

        # Buttons
        button_layout = QHBoxLayout()

        self.download_btn = QPushButton("Download GPU Pack (~1 GB)")
        self.download_btn.clicked.connect(self._start_download)
        button_layout.addWidget(self.download_btn)

        self.cancel_btn = QPushButton("Later")
        self.cancel_btn.clicked.connect(self._on_later_clicked)
        button_layout.addWidget(self.cancel_btn)

        layout.addLayout(button_layout)
        self.setLayout(layout)

    def _load_gpu_info(self):
        """Load and display GPU information"""
        try:
            cap = gpu_bootstrap.capability_probe()

            if not cap['has_nvidia']:
                self.info_text.setPlainText("⚠️ No NVIDIA GPU detected.\nGPU acceleration requires an NVIDIA GPU with compatible driver.")
                self.download_btn.setEnabled(False)
                return

            # Get app version
            version_file = resource_path("VERSION")
            import os
            if os.path.exists(version_file):
                with open(version_file, 'r') as f:
                    app_version = f.read().strip().lstrip('v')
            else:
                app_version = "1.0.0"

            # Load manifests
            try:
                manifests = gpu_manifest.load_local_manifest(app_version)
            except:
                # Use defaults
                from typing import Dict
                manifests: Dict[str, 'gpu_manifest.GpuPackManifest'] = {}
                for flavor, manifest_data in gpu_manifest.DEFAULT_MANIFESTS.items():
                    manifest_data_copy = manifest_data.copy()
                    manifest_data_copy['app_version'] = app_version
                    manifests[flavor] = gpu_manifest.GpuPackManifest.from_dict(manifest_data_copy)

            # Choose pack
            flavor_override = self.config.gpu_flavor if self.config.gpu_flavor else None
            chosen = gpu_manifest.choose_pack(manifests, cap['driver_version'], flavor_override)

            if not chosen:
                self.info_text.setPlainText(
                    f"⚠️ No compatible GPU Pack found for your driver version.\n\n"
                    f"Your driver: {cap['driver_version']}\n"
                    f"Required: ≥531.xx (CUDA 12.1) or ≥550.xx (CUDA 12.4)\n\n"
                    f"Please update your NVIDIA drivers."
                )
                self.download_btn.setEnabled(False)
                return

            # Store for download
            self.chosen_manifest = chosen
            self.cap = cap

            # Try to get actual file size from HTTP headers
            actual_size = chosen.size  # Fallback to manifest size
            try:
                import urllib.request
                req = urllib.request.Request(chosen.url, method='HEAD')
                req.add_header('User-Agent', 'USDXFixGap/1.0')
                with urllib.request.urlopen(req, timeout=5) as response:
                    content_length = response.getheader('Content-Length')
                    if content_length:
                        actual_size = int(content_length)
                        logger.debug(f"Detected actual file size: {actual_size / (1024**3):.2f} GB")
            except Exception as e:
                logger.debug(f"Could not fetch file size from headers: {e}")

            # Display info
            gpu_names = ', '.join(cap['gpu_names'])
            info_text = f"""
✓ NVIDIA GPU Detected: {gpu_names}
✓ Driver Version: {cap['driver_version']}

Recommended GPU Setup:
  • CUDA Version: {chosen.cuda_version}
  • PyTorch Version: {chosen.torch_version}
  • Download Size: ~{actual_size / (1024**3):.1f} GB
  • Flavor: {chosen.flavor}

Download Source:
  • Official PyTorch wheel from download.pytorch.org
  • Includes bundled CUDA and cuDNN (no separate CUDA install needed)
  • Only requires compatible NVIDIA driver (already detected ✓)
  • URL: {chosen.url}

Benefits of GPU Acceleration:
  • 5-10x faster AI vocal separation
  • Process songs in 10-30 seconds (vs 2-3 minutes on CPU)
  • Better performance for batch processing

Installation Method:
  • Downloads official PyTorch wheel (.whl file)
  • Extracts to %LOCALAPPDATA%/USDXFixGap/gpu_runtime/
  • Loads at runtime via sys.path (no system Python modification)

Click "Download GPU Pack" to download and install from PyTorch.org.
            """
            self.info_text.setPlainText(info_text.strip())

        except Exception as e:
            logger.error(f"Error loading GPU info: {e}", exc_info=True)
            self.info_text.setPlainText(f"⚠️ Error loading GPU information:\n{str(e)}")
            self.download_btn.setEnabled(False)

    def _on_later_clicked(self):
        """Handle Later button click - save preference if checkbox is checked"""
        if self.dont_ask_checkbox.isChecked():
            logger.info("User selected 'Don't show this dialog again'")
            self.config.gpu_pack_dialog_dont_show = True
            self.config.save_config()
        self.reject()

    def _start_download(self):
        """Start GPU Pack download"""
        if not hasattr(self, 'chosen_manifest'):
            QMessageBox.warning(self, "Error", "No GPU Pack selected")
            return

        # Disable buttons
        self.download_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)

        # Show progress
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.progress_label.setText("Preparing download...")

        # Get app version for pack directory
        version_file = resource_path("VERSION")
        import os
        if os.path.exists(version_file):
            with open(version_file, 'r') as f:
                app_version = f.read().strip().lstrip('v')
        else:
            app_version = "1.0.0"

        # Prepare paths
        pack_dir = gpu_bootstrap.resolve_pack_dir(app_version, self.chosen_manifest.flavor)

        # Download as .whl file (PyTorch wheels are ZIP-compatible)
        # URL-decode the filename to handle %2B -> + encoding
        import urllib.parse
        wheel_filename = urllib.parse.unquote(self.chosen_manifest.url.split('/')[-1])
        dest_whl = pack_dir.parent / wheel_filename

        # Start worker
        self.worker = GpuDownloadWorker(self.config, self.chosen_manifest, pack_dir, dest_whl)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_finished)
        self.worker.start()

    def _on_progress(self, percentage, message):
        """Update progress display"""
        self.progress_bar.setValue(percentage)
        self.progress_label.setText(message)

    def _on_finished(self, success, message):
        """Handle download completion"""
        self.progress_bar.setVisible(False)

        if success:
            QMessageBox.information(self, "Success", message)
            self.accept()  # Close dialog with success
        else:
            QMessageBox.critical(self, "Error", message)
            self.download_btn.setEnabled(True)
            self.cancel_btn.setEnabled(True)
            self.progress_label.setText("Download failed. Please try again.")
