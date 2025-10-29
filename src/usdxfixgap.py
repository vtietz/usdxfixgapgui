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


def main():
    """Main entry point for USDXFixGap application"""
    log_file_path = None

    try:
        # Parse CLI arguments
        args = parse_arguments()

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
                sys.exit(0)

        # Bootstrap GPU Pack BEFORE any provider imports
        gpu_enabled = gpu_bootstrap.bootstrap_and_maybe_enable_gpu(config)

        # Setup async logging
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

        # GPU Status Logging (Console Only - dialog shown later)
        log_gpu_status(config, gpu_enabled, show_gui_dialog=False)

        # Import and start GUI
        from ui.main_window import create_and_run_gui
        exit_code = create_and_run_gui(config, gpu_enabled, log_file_path)

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
        sys.exit(1)


if __name__ == "__main__":
    main()
