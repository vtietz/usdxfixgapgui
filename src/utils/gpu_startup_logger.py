"""
GPU Startup Logger for USDXFixGap

Provides informative console output about GPU/CUDA status on application startup,
including helpful guidance for enabling GPU acceleration.
"""

import sys
import os
from pathlib import Path
from utils.gpu_utils import is_gpu_pack_installed, get_gpu_pack_info


def log_gpu_status(config, gpu_enabled, show_gui_dialog=True):
    """
    Print comprehensive GPU status information on startup to console.
    Provides helpful guidance for enabling GPU acceleration.
    Optionally shows GUI dialog if NVIDIA GPU detected but pack not installed.
    
    Args:
        config: Application config object
        gpu_enabled: Boolean indicating if GPU bootstrap succeeded
        show_gui_dialog: Whether to show GUI dialog for GPU Pack installation prompt
    """
    from utils import gpu_bootstrap
    
    print("=" * 70)
    print("GPU ACCELERATION STATUS")
    print("=" * 70)
    
    # Probe for NVIDIA GPU
    cap = gpu_bootstrap.capability_probe()
    
    if cap['has_nvidia']:
        _log_nvidia_gpu_detected(cap, config, gpu_enabled, show_gui_dialog)
    else:
        _log_no_nvidia_gpu()
    
    print("=" * 70)


def _log_nvidia_gpu_detected(cap, config, gpu_enabled, show_gui_dialog):
    """Log status when NVIDIA GPU is detected."""
    print(f"✓ NVIDIA GPU detected: {', '.join(cap['gpu_names'])}")
    print(f"✓ Driver version: {cap['driver_version']}")
    
    # Check if GPU is actually working (either GPU Pack or system CUDA)
    if gpu_enabled:
        # GPU is working - check if it's from GPU Pack or system CUDA
        if is_gpu_pack_installed(config):
            _log_gpu_pack_installed(config, gpu_enabled)
        else:
            # GPU is working but no GPU Pack - must be system CUDA
            _log_system_cuda_detected()
    else:
        # GPU not working - check if GPU Pack is installed but failed
        if is_gpu_pack_installed(config):
            _log_gpu_pack_installed(config, gpu_enabled)
        else:
            # No GPU Pack and GPU not working - offer to install
            _log_gpu_pack_not_installed(show_gui_dialog)


def _log_gpu_pack_installed(config, gpu_enabled):
    """Log status when GPU Pack is installed."""
    pack_info = get_gpu_pack_info(config)
    if pack_info:
        version, path = pack_info
        print(f"✓ GPU Pack installed: {version}")
        print(f"  Location: {path}")
    else:
        # Shouldn't happen, but handle gracefully
        print("✓ GPU Pack installed")
    
    # Check if GPU is enabled
    if config.gpu_opt_in:
        if gpu_enabled:
            _log_gpu_active()
        else:
            _log_gpu_bootstrap_failed(config)
    else:
        _log_gpu_disabled()


def _log_gpu_active():
    """Log status when GPU is active and ready."""
    print("✓ GPU acceleration: ENABLED and ACTIVE")
    
    # Try to verify CUDA availability
    try:
        import torch
        if torch.cuda.is_available():
            print(f"✓ CUDA available: {torch.version.cuda}")
            print(f"✓ PyTorch device count: {torch.cuda.device_count()}")
            device_name = torch.cuda.get_device_name(0)
            print(f"✓ Primary GPU: {device_name}")
            print("✓ GPU acceleration ready for processing!")
        else:
            print("⚠ GPU Pack loaded but torch.cuda.is_available() = False")
            print("  Processing will fall back to CPU")
    except ImportError:
        print("⚠ GPU Pack loaded but PyTorch not importable")
        print("  Processing will fall back to CPU")
    except Exception as e:
        print(f"⚠ Error checking CUDA status: {e}")


def _log_gpu_bootstrap_failed(config):
    """Log status when GPU bootstrap failed."""
    exe_name = _get_executable_name()
    print("⚠ GPU acceleration enabled but bootstrap failed")
    print("  Check GpuLastError in config for details")
    if config.gpu_last_error:
        print(f"  Last error: {config.gpu_last_error}")
    print("  Troubleshooting:")
    print(f"    1. Run: {exe_name} --gpu-diagnostics")
    print("    2. Check logs for detailed error information")
    print(f"    3. Try reinstalling GPU Pack: {exe_name} --setup-gpu")


def _log_system_cuda_detected():
    """Log status when system-wide CUDA is detected."""
    print("✓ System-wide CUDA detected (no GPU Pack needed)")
    
    # Try to show CUDA details
    try:
        import torch
        if torch.cuda.is_available():
            print(f"✓ CUDA version: {torch.version.cuda}")
            print(f"✓ PyTorch version: {torch.__version__}")
            print(f"✓ GPU device count: {torch.cuda.device_count()}")
            device_name = torch.cuda.get_device_name(0)
            print(f"✓ Primary GPU: {device_name}")
            print("✓ GPU acceleration: ENABLED and ACTIVE")
            print("  GPU acceleration ready for processing!")
        else:
            print("⚠ PyTorch loaded but CUDA not available")
    except Exception as e:
        print(f"⚠ Error querying CUDA details: {e}")


def _log_gpu_disabled():
    """Log status when GPU is disabled."""
    exe_name = _get_executable_name()
    print("ℹ GPU acceleration: DISABLED (GpuOptIn=false)")
    print("  GPU Pack is installed but not enabled.")
    print("  To enable:")
    print("    • GUI: Settings → GPU Acceleration → Enable")
    print(f"    • CLI: {exe_name} --gpu-enable")
    print("  Expected speedup: 5-10x faster processing")


def _log_gpu_pack_not_installed(show_gui_dialog):
    """Log status when GPU Pack is not installed."""
    exe_name = _get_executable_name()
    print("ℹ GPU Pack: NOT INSTALLED")
    print("  Your system supports GPU acceleration!")
    print("  Benefits:")
    print("    • 5-10x faster AI vocal separation")
    print("    • Process songs in 10-30 seconds (vs 2-3 minutes)")
    print("  To install GPU Pack (~1GB download):")
    print("    • GUI: Settings → Download GPU Pack")
    print(f"    • CLI: {exe_name} --setup-gpu")
    print("  See docs/gpu-acceleration.md for details")
    
    # Show GUI dialog if requested
    if show_gui_dialog:
        _show_gpu_pack_dialog(exe_name)


def _log_no_nvidia_gpu():
    """Log status when no NVIDIA GPU is detected."""
    print("ℹ No NVIDIA GPU detected")
    print("  GPU acceleration requires:")
    print("    • NVIDIA GPU with CUDA support (RTX 20/30/40 series recommended)")
    print("    • Driver version ≥531.xx (for CUDA 12.1) or ≥550.xx (for CUDA 12.4)")
    print("  Processing will use CPU (slower but fully functional)")
    print("  CPU processing time: ~2-3 minutes per song")


def _get_executable_name():
    """Get the name of the current executable or script."""
    if hasattr(sys, '_MEIPASS'):
        # Running as PyInstaller bundle
        return os.path.basename(sys.executable)
    # Running as script
    return "usdxfixgap.exe"


def _show_gpu_pack_dialog(exe_name):
    """Show GUI dialog informing user about GPU Pack availability."""
    try:
        from PySide6.QtWidgets import QMessageBox
        
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setWindowTitle("GPU Acceleration Available")
        msg.setText("🚀 Your system supports GPU acceleration!")
        msg.setInformativeText(
            f"Benefits:\n"
            f"  • 5-10x faster AI vocal separation\n"
            f"  • Process songs in 10-30 seconds (vs 2-3 minutes)\n\n"
            f"To enable GPU acceleration:\n"
            f"  • GUI: Settings → Download GPU Pack\n"
            f"  • Command line: {exe_name} --setup-gpu\n\n"
            f"GPU Pack download size: ~1GB"
        )
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()
    except Exception as e:
        # Silently fail if GUI not available (CLI mode)
        print(f"  Note: Could not show GUI dialog: {e}")


def show_gpu_pack_dialog_if_needed(config, gpu_enabled):
    """
    Show GPU Pack installation dialog if appropriate.
    Should be called AFTER QApplication is created.
    
    Args:
        config: Application config object
        gpu_enabled: Boolean indicating if GPU bootstrap succeeded
    """
    import logging
    from utils import gpu_bootstrap
    from ui.gpu_download_dialog import GpuPackDownloadDialog
    
    logger = logging.getLogger(__name__)
    
    # Check if user has chosen to not show dialog
    if config.gpu_pack_dialog_dont_show:
        logger.debug("GPU Pack dialog suppressed by user preference (GpuPackDialogDontShow=true)")
        return
    
    # Only show if NVIDIA GPU detected but GPU not working
    cap = gpu_bootstrap.capability_probe()
    if cap['has_nvidia'] and not gpu_enabled:
        # GPU detected but not working - check if GPU Pack is installed
        if not is_gpu_pack_installed(config):
            logger.info("NVIDIA GPU detected but no GPU acceleration available - showing download dialog")
            try:
                dialog = GpuPackDownloadDialog(config)
                result = dialog.exec()
                if result:  # User downloaded and installed
                    logger.info("GPU Pack installation completed via dialog")
                else:
                    logger.info("User declined GPU Pack installation")
            except Exception as e:
                logger.error(f"Error showing GPU download dialog: {e}", exc_info=True)
        else:
            logger.debug("GPU Pack installed but GPU bootstrap failed - not showing dialog")
