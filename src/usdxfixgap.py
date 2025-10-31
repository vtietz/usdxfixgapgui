import sys
import os
import logging
import argparse
import traceback

from app.app_data import Config
from cli.gpu_cli_handler import handle_gpu_cli_flags
from utils import gpu_bootstrap
from common.utils.async_logging import setup_async_logging
from utils.files import get_localappdata_dir
from utils.gpu_startup_logger import log_gpu_status
from utils.model_paths import setup_model_paths


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
    parser = argparse.ArgumentParser(description='USDXFixGap - UltraStar Deluxe Gap Detection')

    # Version info
    parser.add_argument('--version', action='store_true',
                       help='Show version information and exit')
    parser.add_argument('--health-check', action='store_true',
                       help='Verify application can start (for CI/testing)')

    # GPU management
    parser.add_argument('--setup-gpu', action='store_true',
                       help='Download and install GPU Pack for CUDA acceleration')
    parser.add_argument('--setup-gpu-zip', type=str, metavar='PATH',
                       help='Install GPU Pack from offline ZIP file')
    parser.add_argument('--gpu-enable', action='store_true',
                       help='Enable GPU acceleration (set gpu_opt_in=true)')
    parser.add_argument('--gpu-disable', action='store_true',
                       help='Disable GPU acceleration (set gpu_opt_in=false)')
    parser.add_argument('--gpu-diagnostics', action='store_true',
                       help='Show GPU status and write diagnostics to file')

    return parser.parse_args()


def get_version():
    """Read version from VERSION file"""
    try:
        from utils.files import resource_path
        version_file = resource_path('VERSION')
        if os.path.exists(version_file):
            with open(version_file, 'r') as f:
                return f.read().strip()
    except Exception:
        pass
    return "unknown"


def print_version_info():
    """Print version and dependency information"""
    version = get_version()
    print(f"USDXFixGap {version}")  # VERSION file already contains 'v' prefix
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
    Perform basic health check to verify app can start.
    Uses SystemCapabilities service for consistent capability detection.
    Returns exit code: 0 = success, 1 = failure
    """
    print("USDXFixGap Health Check")
    print("=" * 50)

    errors = []

    # Check Qt Framework
    try:
        __import__('PySide6.QtCore')
        print(f"✓ {'Qt Framework':20} (PySide6.QtCore)")
    except Exception as e:
        print(f"✗ {'Qt Framework':20} (PySide6.QtCore): {str(e)}")
        errors.append("Qt Framework (PySide6.QtCore)")

    # Check system capabilities using centralized service
    try:
        from services.system_capabilities import check_system_capabilities
        caps = check_system_capabilities()

        # PyTorch
        if caps.has_torch:
            print(f"✓ {'PyTorch':20} ({caps.torch_version})")
            # CUDA/GPU
            if caps.has_cuda:
                print(f"✓ {'CUDA':20} ({caps.cuda_version} - {caps.gpu_name})")
            else:
                print(f"⚠ {'CUDA':20} (not available, CPU mode)")
        else:
            print(f"✗ {'PyTorch':20} {caps.torch_error}")
            errors.append("PyTorch")

        # FFmpeg
        if caps.has_ffmpeg:
            print(f"✓ {'FFmpeg':20} ({caps.ffmpeg_version})")
        else:
            print(f"✗ {'FFmpeg':20} (not found in PATH)")
            errors.append("FFmpeg")

        # FFprobe
        if caps.has_ffprobe:
            print(f"✓ {'FFprobe':20} (found)")
        else:
            print(f"⚠ {'FFprobe':20} (not found)")

        # Detection capability
        if caps.can_detect:
            mode = "GPU" if caps.has_cuda else "CPU"
            print(f"✓ {'Gap Detection':20} (available - {mode} mode)")
        else:
            print(f"✗ {'Gap Detection':20} (unavailable)")
            errors.append("Gap Detection")

    except Exception as e:
        print(f"✗ {'System Capabilities':20} {str(e)}")
        errors.append("System Capabilities Check")

    # Check other critical modules
    other_modules = [
        ('librosa', 'Audio Processing'),
        ('soundfile', 'Audio I/O'),
    ]

    for module_name, description in other_modules:
        try:
            __import__(module_name)
            print(f"✓ {description:20} ({module_name})")
        except Exception as e:
            print(f"✗ {description:20} ({module_name}): {str(e)}")
            errors.append(f"{description} ({module_name})")

    # Check VERSION file exists
    try:
        version = get_version()
        if version != "unknown":
            print(f"✓ {'Version File':20} ({version})")  # Already has 'v' prefix
        else:
            print(f"⚠ {'Version File':20} (not found, using 'unknown')")
    except Exception as e:
        print(f"✗ {'Version File':20} {str(e)}")
        errors.append("VERSION file")

    # Check assets directory
    try:
        from utils.files import resource_path
        assets_dir = resource_path('assets')
        if os.path.exists(assets_dir):
            print(f"✓ {'Assets Directory':20} ({assets_dir})")
        else:
            print(f"⚠ {'Assets Directory':20} (not found)")
    except Exception as e:
        print(f"⚠ {'Assets Directory':20} {str(e)}")

    print("=" * 50)

    if errors:
        print(f"\n❌ Health check FAILED - {len(errors)} critical issue(s)")
        for error in errors:
            print(f"   - {error}")
        return 1
    else:
        print("\n✅ Health check PASSED - Application ready")
        return 0


def main():
    """Main entry point for USDXFixGap application"""
    log_file_path = None

    try:
        # Parse CLI arguments
        args = parse_arguments()

        # Handle --version flag (exit early)
        if args.version:
            print_version_info()
            sys.exit(0)

        # Handle --health-check flag (exit early)
        if args.health_check:
            exit_code = health_check()
            sys.exit(exit_code)

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

        # Setup model paths BEFORE importing any AI libraries (PyTorch, TensorFlow, etc.)
        # This ensures Demucs and Spleeter download models to our centralized location
        setup_model_paths(config)

        # Handle GPU CLI flags (may exit early)
        if any([args.setup_gpu, args.setup_gpu_zip, args.gpu_enable, args.gpu_disable, args.gpu_diagnostics]):
            should_exit = handle_gpu_cli_flags(args, config)
            if should_exit:
                # Cleanup asyncio if it was started
                from utils.run_async import shutdown_asyncio
                shutdown_asyncio()
                sys.exit(0)

        # Setup async logging BEFORE splash screen
        log_file_path = os.path.join(get_localappdata_dir(), 'usdxfixgap.log')
        setup_async_logging(
            log_level=config.log_level,
            log_file_path=log_file_path,
            max_bytes=10*1024*1024,  # 10MB
            backup_count=3
        )

        logger = logging.getLogger(__name__)
        logger.info(f"Application started with log level: {config.log_level_str}")

        # Log configuration file location now that logging is ready
        config.log_config_location()

        # Create QApplication BEFORE splash (needed for Qt dialogs)
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        # Show startup splash wizard and run system capability checks
        from ui.splash_screen import StartupSplash
        capabilities = StartupSplash.run(parent=None, config=config)

        # If splash was closed without capabilities, exit
        if capabilities is None:
            logger.warning("Splash screen closed without completing checks")
            # Cleanup threads in proper order: asyncio first, then logging
            from utils.run_async import shutdown_asyncio
            from common.utils.async_logging import shutdown_async_logging
            shutdown_asyncio()
            shutdown_async_logging()
            sys.exit(0)

        logger.info(f"System capabilities: torch={capabilities.has_torch}, "
                   f"cuda={capabilities.has_cuda}, ffmpeg={capabilities.has_ffmpeg}, "
                   f"can_detect={capabilities.can_detect}")

        # Bootstrap GPU Pack if needed (based on capabilities and config)
        gpu_enabled = gpu_bootstrap.bootstrap_and_maybe_enable_gpu(config)

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
                with open(log_file_path, 'a', encoding='utf-8') as f:
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
