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
from utils.gpu.download_cleanup import cleanup_download_files, cleanup_download_files_safe
from utils.gpu_bootstrap import capability_probe
from utils.gpu import manifest as gpu_manifest
from utils.version import get_version

logger = logging.getLogger(__name__)


def on_download_clicked(dialog):
    """Handle Download GPU Pack button click."""
    # Safety check: ensure dialog and its widgets are still valid
    if not _is_dialog_alive(dialog):
        return

    # Check if a download is already running
    if _is_download_running(dialog):
        logger.warning("Download already in progress, ignoring button click")
        return

    # Ensure previous finished worker is cleaned
    _cleanup_previous_worker(dialog)

    # Prepare UI
    _prepare_download_ui(dialog)

    dialog.log("Preparing GPU Pack download...")

    try:
        chosen_manifest, selected_flavor = _choose_manifest(dialog)
        if not chosen_manifest:
            QMessageBox.critical(
                dialog,
                "GPU Pack Not Available",
                (
                    "No GPU Pack manifest available for your system.\n\n"
                    "This could mean:\n"
                    "• GPU Pack is not yet available for your Python version\n"
                    "• Your system is not compatible\n\n"
                    "Please check the documentation for supported configurations."
                ),
            )
            _reset_download_ui(dialog)
            return

        pack_dir, dest_zip = _prepare_paths(dialog, chosen_manifest)

        # Force fresh download (resume disabled)
        cleanup_download_files(dest_zip, dialog.log)

        # Log destinations
        logger.info("GPU Pack download destination: %s", pack_dir)
        logger.info("Download ZIP location: %s", dest_zip)
        dialog.log(f"Download destination: {pack_dir}")
        dialog.log("Starting fresh download (resume disabled for reliability)")

        _save_flavor_preference(dialog, selected_flavor)

        # Start download worker (dialog non-modal during download)
        _start_download_worker(dialog, chosen_manifest, pack_dir, dest_zip)

    except Exception as e:
        logger.error("Failed to start GPU Pack download: %s", e, exc_info=True)
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
        _handle_download_success(dialog)
    else:
        _handle_download_failure(dialog, message)


def _reset_download_ui(dialog):
    """Reset download UI elements."""
    dialog.progress_bar.setVisible(False)
    dialog.progress_label.setVisible(False)
    dialog.download_btn.setEnabled(True)
    if dialog.start_btn:
        dialog.start_btn.setEnabled(True)


# ==========================
# Internal helper functions
# ==========================


def _is_dialog_alive(dialog) -> bool:
    try:
        if not dialog:
            return False
        _ = dialog.download_btn.isEnabled()  # Touch C++ object to ensure alive
        return True
    except (AttributeError, RuntimeError):
        return False


def _is_download_running(dialog) -> bool:
    return bool(dialog._download_worker and dialog._download_worker.isRunning())


def _cleanup_previous_worker(dialog) -> None:
    if dialog._download_worker:
        dialog._download_worker.wait(5000)  # up to 5s for thread to finish
        dialog._download_worker = None


def _prepare_download_ui(dialog) -> None:
    dialog.download_btn.setEnabled(False)
    if dialog.start_btn:
        dialog.start_btn.setEnabled(False)
    dialog.progress_bar.setVisible(True)
    dialog.progress_label.setVisible(True)
    dialog.progress_bar.setValue(0)


def _choose_manifest(dialog):
    app_version = get_version()

    manifests = gpu_manifest.load_local_manifest(app_version)
    cap = capability_probe()

    # Flavor from UI or config
    selected_flavor = dialog.flavor_combo.currentData() if dialog.flavor_combo.isVisible() else None
    has_cfg = bool(dialog.config and dialog.config.gpu_flavor)
    config_flavor = dialog.config.gpu_flavor if has_cfg else None
    flavor_override = selected_flavor or config_flavor

    chosen_manifest = gpu_manifest.choose_pack(manifests, cap.get("driver_version") if cap else None, flavor_override)
    return chosen_manifest, selected_flavor


def _prepare_paths(dialog, chosen_manifest):
    pack_dir = Path(dialog.config.get_gpu_pack_dir(chosen_manifest.torch_version))
    pack_dir.mkdir(parents=True, exist_ok=True)
    torch_version_normalized = chosen_manifest.torch_version.replace("+", "-")
    dest_zip = pack_dir.parent / f"gpu_pack_{torch_version_normalized}.zip"
    return pack_dir, dest_zip


def _save_flavor_preference(dialog, selected_flavor) -> None:
    if selected_flavor and dialog.config:
        dialog.config.gpu_flavor = selected_flavor
        try:
            dialog.config.save_config()
            logger.info("Saved selected GPU flavor: %s", selected_flavor)
        except Exception as e:
            logger.warning("Failed to save flavor preference: %s", e)


def _start_download_worker(dialog, chosen_manifest, pack_dir: Path, dest_zip: Path) -> None:
    dialog.setModal(False)
    dialog._download_worker = GpuDownloadWorker(
        config=dialog.config, chosen_manifest=chosen_manifest, pack_dir=pack_dir, dest_zip=dest_zip
    )
    dialog._download_worker.progress.connect(lambda p, m: on_download_progress(dialog, p, m))
    dialog._download_worker.finished.connect(lambda s, m: on_download_finished(dialog, s, m))
    dialog._download_worker.log_message.connect(dialog.log)
    dialog._download_worker.start()


def _handle_download_success(dialog) -> None:
    dialog._download_failure_count = 0

    dialog.log("")
    dialog.log("✅ GPU Pack downloaded successfully!")
    dialog.log("   Restart the application to use GPU acceleration")

    if dialog._download_worker and dialog.config:
        pack_dir = dialog._download_worker.pack_dir
        dialog.config.gpu_pack_path = str(pack_dir)
        dialog.config.gpu_opt_in = True
        try:
            dialog.config.save_config()
            logger.info("Saved GPU Pack path to config: %s", pack_dir)
        except Exception as e:
            logger.error("Failed to save GPU Pack path: %s", e)

    dialog.status_label.setText("⚠️ GPU Pack Installed - Please Restart Application")
    dialog.status_label.setStyleSheet("color: #FFA500; font-weight: bold;")

    dialog.progress_bar.setVisible(False)
    dialog.progress_label.setVisible(False)

    if dialog.start_btn:
        dialog.start_btn.setEnabled(False)
        dialog.start_btn.setText("Restart Required")

    dialog.download_btn.setVisible(False)
    dialog.flavor_combo.setVisible(False)

    dialog._download_worker = None

    QMessageBox.information(
        dialog,
        "Download Complete",
        (
            "GPU Pack downloaded and installed successfully!\n\n"
            "Please restart the application to enable GPU acceleration.\n\n"
            "Click 'Close App' to exit, then start the application again."
        ),
    )


def _handle_download_failure(dialog, message: str) -> None:
    dialog._download_worker = None
    dialog.log("")
    dialog.log(f"❌ Download failed: {message}")
    dialog._download_failure_count += 1

    if _offer_flavor_switch_if_applicable(dialog):
        return

    reply = QMessageBox.question(
        dialog,
        "Download Failed",
        f"GPU Pack download failed:\n\n{message}\n\nWould you like to retry the download?",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.Yes,
    )

    if reply == QMessageBox.StandardButton.Yes:
        _cleanup_failed_download(dialog)
        _reset_download_ui(dialog)
        dialog.log("")
        dialog.log("Cleaning up failed download and retrying...")
        QTimer.singleShot(100, lambda: on_download_clicked(dialog))
    else:
        _reset_download_ui(dialog)


def _offer_flavor_switch_if_applicable(dialog) -> bool:
    current_flavor = dialog.config.gpu_flavor if dialog.config else "cu121"
    cap = capability_probe()
    driver_version = cap.get("driver_version") if cap else None

    can_switch_flavor = (
        dialog._download_failure_count >= 2
        and current_flavor == "cu121"
        and driver_version
        and driver_version >= "550.00"
    )

    if not can_switch_flavor:
        return False

    # Don't prompt - user can manually switch CUDA version in Config if needed
    # Automatic switching often fails for the same reasons (network/mirrors)
    dialog.log("")
    dialog.log(f"ℹ Note: Your driver ({driver_version}) supports CUDA 12.4.")
    dialog.log("  You can try switching CUDA version in Config tab if downloads keep failing.")
    return False
    _reset_download_ui(dialog)
    QTimer.singleShot(100, lambda: on_download_clicked(dialog))
    return True


def _cleanup_failed_download(dialog) -> None:
    try:
        if dialog._download_worker:
            dest_zip = dialog._download_worker.dest_zip
            cleanup_download_files(dest_zip, dialog.log)
        else:
            cleanup_download_files_safe(dialog.config)
    except Exception as e:
        logger.warning("Failed to clean up download files: %s", e)
