import sys
import os
import logging
import argparse

from app.app_data import Config
from cli.gpu_cli_handler import handle_gpu_cli_flags
from utils import gpu_bootstrap
from common.utils.async_logging import setup_async_logging
from utils.files import get_localappdata_dir
from utils.gpu_startup_logger import log_gpu_status
from utils.model_paths import setup_model_paths


def parse_arguments():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(description='USDXFixGap - UltraStar Deluxe Gap Detection')
    parser.add_argument('--setup-gpu', action='store_true',
                       help='Download and install GPU Pack for CUDA acceleration')
    parser.add_argument('--setup-gpu-zip', type=str, metavar='PATH',
                       help='Install GPU Pack from offline ZIP file')
    parser.add_argument('--gpu-enable', action='store_true',
                       help='Enable GPU acceleration (set GpuOptIn=true)')
    parser.add_argument('--gpu-disable', action='store_true',
                       help='Disable GPU acceleration (set GpuOptIn=false)')
    parser.add_argument('--gpu-diagnostics', action='store_true',
                       help='Show GPU status and write diagnostics to file')

    return parser.parse_args()


def main():
    """Main entry point for USDXFixGap application"""

    # Parse CLI arguments
    args = parse_arguments()

    # Create config
    config = Config()

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


if __name__ == "__main__":
    main()
