"""
GPU Pack Download Handlers

This module contains all download event handlers extracted from StartupDialog.
It provides callbacks for download button clicks, progress updates, and completion events.

Pattern:
    Each handler is a free function that takes the dialog instance as first parameter,
    plus any event-specific parameters. This allows testing handlers in isolation
    while keeping them separate from the main dialog logic.

Example:
    # In dialog __init__:
    self.download_btn.clicked.connect(lambda: on_download_clicked(self))

    # In worker setup:
    worker.progress.connect(lambda p, m: on_download_progress(self, p, m))
    worker.finished.connect(lambda s, m: on_download_finished(self, s, m))

Note:
    Handlers access dialog state (config, worker, UI elements) via the dialog parameter.
    They do not store state themselves - they're pure functions with side effects.
"""

import os
import logging
from pathlib import Path
from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import QTimer

from ui.workers.gpu_download_worker import GpuDownloadWorker
from utils.download_cleanup import cleanup_download_files, cleanup_download_files_safe
from utils import gpu_bootstrap, gpu_manifest

logger = logging.getLogger(__name__)


def on_download_clicked(dialog):
    """Handle Download GPU Pack button click."""
    # Safety check: ensure dialog and its widgets are still valid
    try:
        if not dialog or not hasattr(dialog, "download_btn"):
            return
        # Quick test to ensure C++ object is still alive
        _ = dialog.download_btn.isEnabled()
    except RuntimeError:
        # C++ object deleted (happens in tests after dialog close)
        return

    # Check if a download is already running
    if dialog._download_worker and dialog._download_worker.isRunning():
        logger.warning("Download already in progress, ignoring button click")
        return

    # If there's a previous worker that finished, ensure it's cleaned up
    if dialog._download_worker:
        dialog._download_worker.wait(5000)  # Wait up to 5 seconds for thread to finish
        dialog._download_worker = None

    # Disable buttons during download
    dialog.download_btn.setEnabled(False)
    if hasattr(dialog, "start_btn"):
        dialog.start_btn.setEnabled(False)

    # Show progress UI
    dialog.progress_bar.setVisible(True)
    dialog.progress_label.setVisible(True)
    dialog.progress_bar.setValue(0)

    dialog.log("Preparing GPU Pack download...")

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

        # Get selected flavor from combo box
        selected_flavor = dialog.flavor_combo.currentData() if dialog.flavor_combo.isVisible() else None

        # Use selected flavor or fall back to config
        flavor_override = selected_flavor
        if not flavor_override and dialog.config and hasattr(dialog.config, "gpu_flavor") and dialog.config.gpu_flavor:
            flavor_override = dialog.config.gpu_flavor

        chosen_manifest = gpu_manifest.choose_pack(
            manifests, cap.get("driver_version") if cap else None, flavor_override
        )

        if not chosen_manifest:
            QMessageBox.critical(
                dialog,
                "GPU Pack Not Available",
                "No GPU Pack manifest available for your system.\n\n"
                "This could mean:\n"
                "• GPU Pack is not yet available for your Python version\n"
                "• Your system is not compatible\n\n"
                "Please check the documentation for supported configurations.",
            )
            _reset_download_ui(dialog)
            return

        # Prepare paths using config (centralized path management)
        # Use config to get GPU Pack directory (respects user config and provides defaults)
        pack_dir = Path(dialog.config.get_gpu_pack_dir(chosen_manifest.torch_version))
        pack_dir.mkdir(parents=True, exist_ok=True)

        # Store ZIP in parent directory (gpu_runtime/)
        torch_version_normalized = chosen_manifest.torch_version.replace("+", "-")
        dest_zip = pack_dir.parent / f"gpu_pack_{torch_version_normalized}.zip"

        # CRITICAL: Clean up ALL download files to force fresh download from zero
        # Resume has proven unreliable (SSL errors, corruption), so we always start fresh
        # This prevents "Bad magic number" errors and ensures clean downloads
        cleanup_download_files(dest_zip, dialog.log)

        # Log download destination (both to file and UI)
        logger.info(f"GPU Pack download destination: {pack_dir}")
        logger.info(f"Download ZIP location: {dest_zip}")
        dialog.log(f"Download destination: {pack_dir}")
        dialog.log(f"Starting fresh download (resume disabled for reliability)")

        # Save selected flavor to config for future use
        if selected_flavor and dialog.config:
            dialog.config.gpu_flavor = selected_flavor
            try:
                dialog.config.save_config()
                logger.info(f"Saved selected GPU flavor: {selected_flavor}")
            except Exception as e:
                logger.warning(f"Failed to save flavor preference: {e}")

        # Make dialog non-modal during download to allow confirmation dialogs
        # This is needed for retry confirmations to work properly
        dialog.setModal(False)

        # Start download worker
        dialog._download_worker = GpuDownloadWorker(
            config=dialog.config, chosen_manifest=chosen_manifest, pack_dir=pack_dir, dest_zip=dest_zip
        )
        dialog._download_worker.progress.connect(lambda p, m: on_download_progress(dialog, p, m))
        dialog._download_worker.finished.connect(lambda s, m: on_download_finished(dialog, s, m))
        dialog._download_worker.log_message.connect(dialog.log)  # Connect log signal to UI
        dialog._download_worker.start()

    except Exception as e:
        logger.error(f"Failed to start GPU Pack download: {e}", exc_info=True)
        QMessageBox.critical(dialog, "Download Failed", f"Failed to start GPU Pack download:\n\n{str(e)}")
        _reset_download_ui(dialog)


def on_download_progress(dialog, percentage: int, message: str):
    """Handle download progress update."""
    dialog.progress_bar.setValue(percentage)
    dialog.progress_label.setText(message)


def on_download_finished(dialog, success: bool, message: str):
    """Handle download completion."""
    # Restore modal state after download completes
    dialog.setModal(True)

    if success:
        # Reset failure counter on success
        dialog._download_failure_count = 0

        dialog.log("")
        dialog.log("✅ GPU Pack downloaded successfully!")
        dialog.log("   Restart the application to use GPU acceleration")

        # Save GPU Pack path to config
        if dialog._download_worker and dialog.config:
            pack_dir = dialog._download_worker.pack_dir
            dialog.config.gpu_pack_path = str(pack_dir)
            dialog.config.gpu_opt_in = True  # Enable GPU
            try:
                dialog.config.save_config()
                logger.info(f"Saved GPU Pack path to config: {pack_dir}")
            except Exception as e:
                logger.error(f"Failed to save GPU Pack path: {e}")

        # Update status label to show restart warning
        dialog.status_label.setText("⚠️ GPU Pack Installed - Please Restart Application")
        dialog.status_label.setStyleSheet("color: #FFA500; font-weight: bold;")

        # Hide progress bar and status after successful download
        dialog.progress_bar.setVisible(False)
        dialog.progress_label.setVisible(False)

        # Disable Start App button - user MUST restart
        if hasattr(dialog, "start_btn"):
            dialog.start_btn.setEnabled(False)
            dialog.start_btn.setText("Restart Required")

        # Hide download UI elements (button and flavor selector)
        dialog.download_btn.setVisible(False)
        dialog.flavor_combo.setVisible(False)

        # Clean up worker reference
        dialog._download_worker = None

        QMessageBox.information(
            dialog,
            "Download Complete",
            "GPU Pack downloaded and installed successfully!\n\n"
            "Please restart the application to enable GPU acceleration.\n\n"
            "Click 'Close App' to exit, then start the application again.",
        )
    else:
        # Clean up worker reference
        dialog._download_worker = None

        dialog.log("")
        dialog.log(f"❌ Download failed: {message}")

        # Increment failure counter
        dialog._download_failure_count += 1

        # After 2+ failures with cu121, offer to try cu124
        current_flavor = dialog.config.gpu_flavor if dialog.config and hasattr(dialog.config, "gpu_flavor") else "cu121"

        # Check driver version from capability probe
        cap = gpu_bootstrap.capability_probe()
        driver_version = cap.get("driver_version") if cap else None

        can_switch_flavor = (
            dialog._download_failure_count >= 2
            and current_flavor == "cu121"
            and driver_version
            and driver_version >= "550.00"  # cu124 requires driver >=550
        )

        if can_switch_flavor:
            # Offer flavor switch
            reply = QMessageBox.question(
                dialog,
                "Try Alternative CUDA Version?",
                f"GPU Pack download has failed {dialog._download_failure_count} times with CUDA 12.1.\n\n"
                f"Your driver ({driver_version}) supports CUDA 12.4.\n\n"
                "Would you like to try downloading CUDA 12.4 instead?\n"
                "(This is a different PyTorch build that may work better)",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )

            if reply == QMessageBox.StandardButton.Yes:
                # Switch to cu124
                dialog.log("")
                dialog.log("→ Switching to CUDA 12.4 (cu124) flavor...")
                if dialog.config:
                    dialog.config.gpu_flavor = "cu124"
                    try:
                        dialog.config.save_config()
                        logger.info("Switched GPU flavor to cu124")
                    except Exception as e:
                        logger.warning(f"Failed to save flavor switch: {e}")

                # Clean up and retry with new flavor
                cleanup_download_files_safe(dialog.config)
                _reset_download_ui(dialog)
                QTimer.singleShot(100, lambda: on_download_clicked(dialog))
                return  # Skip the normal retry prompt

        # Normal retry prompt (same flavor)
        # Ask user if they want to retry
        reply = QMessageBox.question(
            dialog,
            "Download Failed",
            f"GPU Pack download failed:\n\n{message}\n\n" "Would you like to retry the download?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )

        if reply == QMessageBox.StandardButton.Yes:
            # Clean up any partial/corrupted download files before retry
            try:
                # Use the same path logic as in on_download_clicked
                if dialog._download_worker and hasattr(dialog._download_worker, "dest_zip"):
                    dest_zip = dialog._download_worker.dest_zip
                    cleanup_download_files(dest_zip, dialog.log)
                else:
                    # Fallback: clean up all .zip files in gpu_runtime
                    cleanup_download_files_safe(dialog.config)
            except Exception as e:
                logger.warning(f"Failed to clean up download files: {e}")

            # Reset UI and retry download
            _reset_download_ui(dialog)
            dialog.log("")
            dialog.log("Cleaning up failed download and retrying...")
            # Small delay to let UI update
            QTimer.singleShot(100, lambda: on_download_clicked(dialog))
        else:
            # User chose not to retry - just reset UI
            _reset_download_ui(dialog)


def _reset_download_ui(dialog):
    """Reset download UI elements."""
    dialog.progress_bar.setVisible(False)
    dialog.progress_label.setVisible(False)
    dialog.download_btn.setEnabled(True)
    if hasattr(dialog, "start_btn"):
        dialog.start_btn.setEnabled(True)
