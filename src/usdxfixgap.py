import sys
import os
import logging
import argparse
import traceback

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


def attach_console():
    """
    Attach to parent console or allocate new console for CLI output.
    Required for windowed executables (console=False) to show CLI output.

    This allows a single executable to behave as both:
    - GUI application (no console) when launched normally
    - CLI tool (with console output) when run with flags like --version or --health-check

    Works by:
    - Attaching to parent console if run from cmd/PowerShell/CI
    - Allocating temporary console if run via double-click
    - Rebinding stdout/stderr to the console device
    """
    if sys.platform == "win32":
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32

            # Try to attach to parent console (cmd, PowerShell, CI environment)
            # ATTACH_PARENT_CONSOLE = -1
            if not kernel32.AttachConsole(-1):
                # No parent console exists - allocate a new one (double-click scenario)
                kernel32.AllocConsole()

            # Rebind stdout/stderr/stdin to the console device
            # This is necessary because windowed apps have null streams by default
            try:
                sys.stdout = open("CONOUT$", "w", encoding="utf-8")
                sys.stderr = open("CONOUT$", "w", encoding="utf-8")
                sys.stdin = open("CONIN$", "r", encoding="utf-8")
            except OSError:
                # Console binding failed - continue anyway
                pass
        except Exception:
            # If console attachment fails, continue without it
            # CLI output will be invisible but app won't crash
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
        print(f"\n{'='*60}", file=sys.stderr)
        print(f"CRITICAL ERROR: {title}", file=sys.stderr)
        print(f"{'='*60}", file=sys.stderr)
        print(message, file=sys.stderr)
        if details:
            print(f"\nDetails:\n{details}", file=sys.stderr)
        print(f"{'='*60}\n", file=sys.stderr)


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
    Lightweight health check using metadata only.
    Avoids importing heavy modules (torch, PySide6) to keep startup fast.
    Perfect for CI/CD validation - completes in <1 second.
    Returns exit code: 0 = success, 1 = failure
    """
    import importlib.metadata
    import subprocess

    print(f"{APP_NAME} Health Check")
    print("=" * 50)

    errors = []

    # Check PyTorch (metadata only - NO IMPORT, instant check)
    try:
        torch_version = importlib.metadata.version("torch")
        print(f"✓ {'PyTorch':20} ({torch_version})")
    except Exception:
        print(f"✗ {'PyTorch':20} Not installed")
        errors.append("PyTorch")

    # Check PySide6 (metadata only - NO IMPORT, instant check)
    try:
        pyside_version = importlib.metadata.version("PySide6")
        print(f"✓ {'Qt Framework':20} (PySide6 {pyside_version})")
    except Exception:
        print(f"✗ {'Qt Framework':20} Not installed")
        errors.append("Qt Framework")

    # Check FFmpeg (subprocess - lightweight, already optimized)
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        if result.returncode == 0:
            first_line = result.stdout.split("\n")[0]
            version = first_line.split("version")[1].split()[0] if "version" in first_line else "unknown"
            print(f"✓ {'FFmpeg':20} ({version})")
        else:
            print(f"✗ {'FFmpeg':20} Command failed")
            errors.append("FFmpeg")
    except FileNotFoundError:
        print(f"✗ {'FFmpeg':20} Not found in PATH")
        errors.append("FFmpeg")
    except Exception as e:
        print(f"✗ {'FFmpeg':20} {str(e)}")
        errors.append("FFmpeg")

    # Check other critical modules (metadata with fallback to import for frozen exes)
    other_modules = [
        ("librosa", "Audio Processing"),
        ("soundfile", "Audio I/O"),
    ]

    for module_name, description in other_modules:
        try:
            # Try metadata first (fast)
            version = importlib.metadata.version(module_name)
            print(f"✓ {description:20} ({module_name} {version})")
        except Exception:
            # Fallback: try to import module (works in frozen exes)
            try:
                module = __import__(module_name)
                version = getattr(module, "__version__", "installed")
                print(f"✓ {description:20} ({module_name} {version})")
            except Exception:
                print(f"✗ {description:20} Not installed")
                errors.append(description)

    # Check VERSION file exists
    try:
        version = get_version()
        if version != "unknown":
            print(f"✓ {'Version File':20} ({version})")  # Already has 'v' prefix
        else:
            print(f"⚠ {'Version File':20} Not found, using 'unknown'")
    except Exception as e:
        print(f"✗ {'Version File':20} {str(e)}")
        errors.append("VERSION file")

    # Check assets directory
    try:
        from utils.files import resource_path

        assets_dir = resource_path("assets")
        if os.path.exists(assets_dir):
            print(f"✓ {'Assets Directory':20} Found")
        else:
            print(f"⚠ {'Assets Directory':20} Not found")
    except Exception as e:
        print(f"⚠ {'Assets Directory':20} {str(e)}")

    print("=" * 50)

    if errors:
        print(f"\n❌ Health check FAILED - {len(errors)} critical issue(s)")
        for error in errors:
            print(f"   - {error}")
        return 1
    else:
        print("\n✅ Health check PASSED - All checks successful")
        return 0


def main():
    """Main entry point for USDXFixGap application"""
    log_file_path = None

    try:
        # Parse CLI arguments
        args = parse_arguments()

        # Attach console for CLI flags (makes output visible in windowed exe)
        if args.version or args.health_check:
            attach_console()

        # Handle --version flag (exit early)
        if args.version:
            print_version_info()
            sys.exit(0)

        # Handle --health-check flag (exit early, before any heavy imports)
        if args.health_check:
            exit_code = health_check()
            sys.exit(exit_code)

        # Now import the rest of the modules (after early exit flags are handled)
        from app.app_data import Config
        from cli.gpu_cli_handler import handle_gpu_cli_flags
        from utils import gpu_bootstrap
        from common.utils.async_logging import setup_async_logging
        from utils.files import get_localappdata_dir
        from utils.gpu_startup_logger import log_gpu_status
        from utils.model_paths import setup_model_paths

        # Create config
        config = Config()

        # Validate config and auto-fix critical errors
        from utils.config_validator import validate_config, print_validation_report

        is_valid, validation_errors = validate_config(config, auto_fix=True)
        if validation_errors:
            print_validation_report(validation_errors)
            if not is_valid:
                error_msg = "Critical configuration errors detected!\n\nPlease review and fix config.ini, then restart the application."
                error_details = "\n".join([f"- {err}" for err in validation_errors])
                show_error_dialog("Configuration Error", error_msg, error_details)
                sys.exit(1)

        # Setup async logging EARLY (before GPU bootstrap so we can log it)
        log_file_path = os.path.join(get_localappdata_dir(), APP_LOG_FILENAME)
        setup_async_logging(
            log_level=config.log_level, log_file_path=log_file_path, max_bytes=10 * 1024 * 1024, backup_count=3  # 10MB
        )

        logger = logging.getLogger(__name__)
        logger.info(f"Application started with log level: {config.log_level_str}")

        # Log configuration file location now that logging is ready
        config.log_config_location()

        # Bootstrap GPU Pack BEFORE setup_model_paths (which imports torch!)
        # This ensures torch imports from GPU Pack instead of venv
        gpu_enabled = gpu_bootstrap.bootstrap_and_maybe_enable_gpu(config)
        logger.info(f"GPU bootstrap completed: enabled={gpu_enabled}")

        # Setup model paths AFTER GPU bootstrap but BEFORE other imports
        # This ensures Demucs and Spleeter download models to our centralized location
        # Note: setup_model_paths imports torch, so GPU bootstrap must happen first!
        setup_model_paths(config)

        # Handle GPU CLI flags (may exit early)
        if any([args.setup_gpu, args.setup_gpu_zip, args.gpu_enable, args.gpu_disable, args.gpu_diagnostics]):
            should_exit = handle_gpu_cli_flags(args, config)
            if should_exit:
                # Cleanup asyncio if it was started
                from utils.run_async import shutdown_asyncio

                shutdown_asyncio()
                sys.exit(0)

        # Create QApplication BEFORE splash (needed for Qt dialogs)
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        # Enable dark mode BEFORE showing splash
        from utils.enable_darkmode import enable_dark_mode

        enable_dark_mode(app)

        # Show startup dialog and run system capability checks
        from ui.startup_dialog import StartupDialog

        capabilities = StartupDialog.show_startup(parent=None, config=config)

        # If dialog returned no capabilities, fall back to auto-detection
        if capabilities is None:
            logger.warning("Startup dialog returned no capabilities; proceeding with auto-detected capabilities")
            from services.system_capabilities import check_system_capabilities

            capabilities = check_system_capabilities()

        logger.info(
            f"System capabilities: torch={capabilities.has_torch}, "
            f"cuda={capabilities.has_cuda}, ffmpeg={capabilities.has_ffmpeg}, "
            f"can_detect={capabilities.can_detect}"
        )

        # GPU Status Logging (Console Only)
        log_gpu_status(config, gpu_enabled, show_gui_dialog=False)

        # Import and start GUI (pass capabilities)
        from ui.main_window import create_and_run_gui

        exit_code = create_and_run_gui(config, gpu_enabled, log_file_path, capabilities)

        sys.exit(exit_code)

    except Exception as e:
        # Critical startup failure - show error dialog and log
        error_msg = f"A critical error occurred during application startup:\n\n{str(e)}"
        error_details = traceback.format_exc()

        # Try to log to file if path is available
        if log_file_path:
            try:
                with open(log_file_path, "a", encoding="utf-8") as f:
                    f.write(f"\n{'='*60}\n")
                    f.write(f"CRITICAL STARTUP ERROR\n")
                    f.write(f"{'='*60}\n")
                    f.write(error_details)
                    f.write(f"\n{'='*60}\n\n")
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
