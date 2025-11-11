import sys
import os
import logging
import argparse
import traceback
from typing import Optional, Tuple, Any

# Import only the minimal constants needed for early execution
from common.constants import APP_NAME, APP_DESCRIPTION, APP_LOG_FILENAME

# Defer other imports until after health check / version check
# from app.app_data import Config  # Moved to main()
# from cli.gpu_cli_handler import handle_gpu_cli_flags  # Moved to main()
# from utils import gpu_bootstrap  # Moved to main()
# from common.utils.async_logging import setup_async_logging  # Moved to main()
# from utils.files import get_localappdata_dir  # Moved to main()
# from utils.gpu_startup_logger import log_gpu_status  # Moved to main()
# from utils.model_paths import setup_model_paths  # Moved to main()


def hide_console_window_on_gui_mode():
    """
    Hide the console window when running in GUI mode on Windows.

    This allows a single console=True executable to work as both:
    - CLI tool (console visible, output captured)
    - GUI application (console hidden immediately)

    Only hides the console if it was created for this process (not inherited
    from a parent console like cmd.exe or PowerShell).

    Platform-specific:
    - Windows: Uses Windows API to hide the console window
    - Linux/macOS: No action (standard terminal behavior)
    """
    if os.name != "nt":
        return  # Only on Windows

    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32

        # Get console window handle
        hwnd = kernel32.GetConsoleWindow()
        if not hwnd:
            return  # No console window

        # Check if console was created for this process (not inherited)
        # GetConsoleProcessList returns the number of processes attached
        process_list = (ctypes.c_uint32 * 4)()
        process_count = kernel32.GetConsoleProcessList(process_list, 4)

        # If only 1 process attached, this console was created for us
        # If multiple processes, we inherited an existing console (cmd/PowerShell)
        if process_count == 1:
            # SW_HIDE = 0
            ctypes.windll.user32.ShowWindow(hwnd, 0)
    except Exception:
        # Best effort - continue even if hiding fails
        pass


def show_error_dialog(title, message, details=None):
    """Show error dialog for critical startup failures (even before Qt is initialized)"""
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox

        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Icon.Critical)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        if details:
            msg_box.setDetailedText(details)
        msg_box.exec()
    except Exception:
        # If GUI fails, print to stderr (visible if run from console)
        print(f"\n{'=' * 60}", file=sys.stderr)
        print(f"CRITICAL ERROR: {title}", file=sys.stderr)
        print(f"{'=' * 60}", file=sys.stderr)
        print(message, file=sys.stderr)
        if details:
            print(f"\nDetails:\n{details}", file=sys.stderr)
        print(f"{'=' * 60}\n", file=sys.stderr)


def parse_arguments():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(description=f"{APP_NAME} - {APP_DESCRIPTION}")

    # Version info
    parser.add_argument("--version", action="store_true", help="Show version information and exit")
    parser.add_argument("--health-check", action="store_true", help="Verify application can start (for CI/testing)")

    # GPU management
    parser.add_argument("--setup-gpu", action="store_true", help="Download and install GPU Pack for CUDA acceleration")
    parser.add_argument("--setup-gpu-zip", type=str, metavar="PATH", help="Install GPU Pack from offline ZIP file")
    parser.add_argument("--gpu-enable", action="store_true", help="Enable GPU acceleration (set gpu_opt_in=true)")
    parser.add_argument("--gpu-disable", action="store_true", help="Disable GPU acceleration (set gpu_opt_in=false)")
    parser.add_argument("--gpu-diagnostics", action="store_true", help="Show GPU status and write diagnostics to file")

    return parser.parse_args()


def get_version():
    """Read version from VERSION file"""
    try:
        from utils.files import resource_path

        version_file = resource_path("VERSION")
        if os.path.exists(version_file):
            with open(version_file, "r") as f:
                return f.read().strip()
    except Exception:
        pass
    return "unknown"


def print_version_info():
    """Print version and dependency information"""
    version = get_version()
    print(f"{APP_NAME} {version}")  # VERSION file already contains 'v' prefix
    print(f"Python: {sys.version.split()[0]}")

    try:
        from PySide6 import __version__ as pyside_version

        print(f"PySide6: {pyside_version}")
    except Exception:
        print("PySide6: not available")

    try:
        import torch

        print(f"PyTorch: {torch.__version__}")
    except Exception:
        print("PyTorch: not available")

    try:
        import librosa

        print(f"librosa: {librosa.__version__}")
    except Exception:
        print("librosa: not available")


def health_check():
    """
    Ultra-minimal health check - just verify the executable runs.

    This is NOT the detailed system check shown in the startup dialog.
    For detailed checks, see services/system_capabilities.py

    Returns exit code: 0 = success, 1 = failure
    """
    print(f"{APP_NAME} Health Check")
    print("=" * 50)

    try:
        # Ultra-minimal: just read VERSION directly without any imports
        version = "unknown"
        try:
            if os.path.exists("VERSION"):
                with open("VERSION", "r") as f:
                    version = f.read().strip()
        except Exception:
            pass

        print("✓ Executable runs successfully")
        print(f"✓ Version: {version}")

        print("=" * 50)
        print("\n✅ Health check PASSED")
        sys.exit(0)

    except Exception as e:
        print("=" * 50)
        print(f"\n❌ Health check FAILED: {e}")
    sys.exit(1)


def _has_cli_flags(args: argparse.Namespace) -> bool:
    """Return True if any CLI-only flags are active."""
    return any(
        [
            args.version,
            args.health_check,
            args.setup_gpu,
            args.setup_gpu_zip is not None,
            args.gpu_enable,
            args.gpu_disable,
            args.gpu_diagnostics,
        ]
    )


def _create_and_validate_config() -> Any:
    """Create Config and validate it, showing a dialog and exiting on critical errors."""
    from app.app_data import Config
    from utils.config_validator import validate_config, print_validation_report

    config = Config()
    is_valid, validation_errors = validate_config(config, auto_fix=True)
    if validation_errors:
        print_validation_report(validation_errors)
        if not is_valid:
            error_msg = (
                "Critical configuration errors detected!\n\n"
                "Please review and fix config.ini, then restart the application."
            )
            error_details = "\n".join([f"- {err}" for err in validation_errors])
            show_error_dialog("Configuration Error", error_msg, error_details)
            sys.exit(1)
    return config


def _setup_logging_early(config: Any) -> Tuple[str, logging.Logger]:
    """Setup async logging and return (log_file_path, logger)."""
    from common.utils.async_logging import setup_async_logging
    from utils.files import get_localappdata_dir

    log_file_path = os.path.join(get_localappdata_dir(), APP_LOG_FILENAME)
    setup_async_logging(
        log_level=config.log_level,
        log_file_path=log_file_path,
        max_bytes=10 * 1024 * 1024,
        backup_count=3,
    )
    logger = logging.getLogger(__name__)
    logger.info(f"Application started with log level: {config.log_level_str}")
    # Log configuration file location now that logging is ready
    config.log_config_location()
    return log_file_path, logger


def _bootstrap_gpu_and_models(config: Any, logger: logging.Logger) -> bool:
    """Bootstrap GPU pack, then configure model paths. Returns whether GPU is enabled."""
    from utils.gpu_bootstrap import bootstrap_and_maybe_enable_gpu
    from utils.model_paths import setup_model_paths

    gpu_enabled = bootstrap_and_maybe_enable_gpu(config)
    logger.info(f"GPU bootstrap completed: enabled={gpu_enabled}")
    # Note: setup_model_paths may import torch — perform after GPU bootstrap
    setup_model_paths(config)
    return gpu_enabled


def _maybe_handle_gpu_cli(args: argparse.Namespace, config: Any) -> Optional[int]:
    """Handle GPU CLI flags; return exit code if we should exit, else None."""
    if not any([args.setup_gpu, args.setup_gpu_zip, args.gpu_enable, args.gpu_disable, args.gpu_diagnostics]):
        return None
    from cli.gpu_cli_handler import handle_gpu_cli_flags
    from utils.run_async import shutdown_asyncio

    should_exit = handle_gpu_cli_flags(args, config)
    if should_exit:
        shutdown_asyncio()
        return 0
    return None


def _init_qt_and_capabilities(config: Any, logger: logging.Logger) -> Any:
    """Initialize Qt app, enable dark mode, and return system capabilities from startup dialog or fallback."""
    from PySide6.QtWidgets import QApplication
    from utils.enable_darkmode import enable_dark_mode
    from ui.startup_dialog import StartupDialog
    from services.system_capabilities import check_system_capabilities

    app = QApplication.instance() or QApplication(sys.argv)
    enable_dark_mode(app)

    capabilities = StartupDialog.show_startup(parent=None, config=config)
    if capabilities is None:
        logger.warning("Startup dialog returned no capabilities; proceeding with auto-detected capabilities")
        capabilities = check_system_capabilities()

    logger.info(
        f"System capabilities: torch={capabilities.has_torch}, "
        f"cuda={capabilities.has_cuda}, ffmpeg={capabilities.has_ffmpeg}, "
        f"can_detect={capabilities.can_detect}"
    )
    return capabilities


def _run_gui(config: Any, gpu_enabled: bool, log_file_path: str, capabilities: Any) -> int:
    """Start the main window and return the GUI exit code."""
    from ui.main_window import create_and_run_gui

    return create_and_run_gui(config, gpu_enabled, log_file_path, capabilities)


def main():
    """Main entry point for USDXFixGap application"""
    log_file_path: Optional[str] = None

    try:
        args = parse_arguments()

        # Hide console window for pure GUI usage
        if not _has_cli_flags(args):
            hide_console_window_on_gui_mode()

        # Early exits
        if args.version:
            print_version_info()
            sys.exit(0)
        if args.health_check:
            sys.exit(health_check())

        # Config + logging
        config = _create_and_validate_config()
        log_file_path, logger = _setup_logging_early(config)

        # GPU + models
        gpu_enabled = _bootstrap_gpu_and_models(config, logger)

        # Optional GPU CLI flow (may exit)
        maybe_exit = _maybe_handle_gpu_cli(args, config)
        if maybe_exit is not None:
            sys.exit(maybe_exit)

        # Capabilities and GUI
        from utils.gpu_startup_logger import log_gpu_status

        capabilities = _init_qt_and_capabilities(config, logger)
        log_gpu_status(config, gpu_enabled, show_gui_dialog=False)
        sys.exit(_run_gui(config, gpu_enabled, log_file_path, capabilities))

    except Exception as e:
        # Critical startup failure - show error dialog and log
        error_msg = f"A critical error occurred during application startup:\n\n{str(e)}"
        error_details = traceback.format_exc()

        if log_file_path:
            try:
                with open(log_file_path, "a", encoding="utf-8") as f:
                    f.write("\n" + "=" * 60 + "\n")
                    f.write("CRITICAL STARTUP ERROR\n")
                    f.write("=" * 60 + "\n")
                    f.write(error_details)
                    f.write("\n" + "=" * 60 + "\n\n")
                error_msg += f"\n\nError details have been logged to:\n{log_file_path}"
            except Exception:
                pass

        show_error_dialog("Critical Startup Error", error_msg, error_details)

        # Cleanup threads before exit
        try:
            from utils.run_async import shutdown_asyncio
            from common.utils.async_logging import shutdown_async_logging

            shutdown_asyncio()
            shutdown_async_logging()
        except Exception:
            pass  # Best effort cleanup

        sys.exit(1)


if __name__ == "__main__":
    main()
