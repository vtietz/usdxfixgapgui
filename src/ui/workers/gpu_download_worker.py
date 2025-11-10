"""
GPU Pack Download Worker

Background thread for downloading and extracting GPU Pack.
Extracted from startup_dialog.py to reduce file size and improve modularity.
"""

import logging
from pathlib import Path
from PySide6.QtCore import QThread, Signal

from utils import gpu_downloader

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
                # Note: Partial files will be cleaned up by closeEvent handler
                self.finished.emit(False, "Download cancelled by user.")
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

            # Clean up the .zip file after successful extraction
            try:
                self.dest_zip.unlink()
                logger.info(f"Deleted GPU Pack .zip file after extraction: {self.dest_zip}")
            except Exception as e:
                logger.warning(f"Could not delete .zip file (non-critical): {e}")

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
