import sys
import os
import logging
import argparse
from pathlib import Path

from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout
from PySide6.QtCore import __version__
from PySide6.QtMultimedia import QMediaDevices
from PySide6.QtGui import QIcon


from actions import Actions
from app.app_data import AppData, Config
from common.database import initialize_song_cache
from common.utils.async_logging import setup_async_logging, shutdown_async_logging

from utils.enable_darkmode import enable_dark_mode
from utils.check_dependencies import check_dependencies
from utils.files import get_app_dir, resource_path

from ui.menu_bar import MenuBar
from ui.song_status import SongsStatusVisualizer
from ui.mediaplayer import MediaPlayerComponent
from ui.songlist.songlist_widget import SongListWidget
from ui.task_queue_viewer import TaskQueueViewer
from ui.log_viewer import LogViewerWidget


def get_app_version():
    """Read application version from VERSION file"""
    try:
        version_file = resource_path("VERSION")
        if os.path.exists(version_file):
            with open(version_file, 'r') as f:
                return f.read().strip().lstrip('v')
        return "1.0.0"  # Fallback
    except Exception:
        return "1.0.0"


def handle_gpu_cli_flags(args, config):
    """Handle GPU-related CLI flags and exit if needed
    
    Returns True if we should exit, False if we should continue to GUI
    """
    from utils import gpu_bootstrap, gpu_manifest, gpu_downloader
    
    should_exit = False
    
    # --gpu-enable
    if args.gpu_enable:
        config.gpu_opt_in = True
        config.save_config()
        print("GPU acceleration enabled (GpuOptIn=true)")
        should_exit = True
    
    # --gpu-disable
    if args.gpu_disable:
        config.gpu_opt_in = False
        config.save_config()
        print("GPU acceleration disabled (GpuOptIn=false)")
        should_exit = True
    
    # --gpu-diagnostics
    if args.gpu_diagnostics:
        print("=== GPU Diagnostics ===")
        
        # Probe GPU
        cap = gpu_bootstrap.capability_probe()
        print(f"NVIDIA GPU detected: {cap['has_nvidia']}")
        if cap['has_nvidia']:
            print(f"Driver version: {cap['driver_version']}")
            print(f"GPU(s): {', '.join(cap['gpu_names'])}")
        
        # Check installed pack using utility
        from utils.gpu_utils import is_gpu_pack_installed, get_gpu_pack_info
        app_version = get_app_version()
        
        if is_gpu_pack_installed(config):
            pack_info = get_gpu_pack_info(config)
            if pack_info:
                version, path = pack_info
                print(f"GPU Pack installed: {version}")
                print(f"GPU Pack path: {path}")
                
                # Validate installation details
                pack_dir = Path(path)
                install_json = pack_dir / "install.json"
                if install_json.exists():
                    import json
                    with open(install_json, 'r') as f:
                        info = json.load(f)
                    print(f"Installed on: {info.get('install_timestamp', 'unknown')}")
                    print(f"CUDA version: {info.get('cuda_version', 'unknown')}")
                    print(f"PyTorch version: {info.get('torch_version', 'unknown')}")
        else:
            print("GPU Pack: Not installed")
            if config.gpu_pack_path:
                print(f"WARNING: Config has GPU Pack path but it doesn't exist: {config.gpu_pack_path}")
        
        print(f"GPU Opt-in: {config.gpu_opt_in}")
        print(f"GPU Flavor: {config.gpu_flavor}")
        print(f"Last health check: {config.gpu_last_health or 'Never'}")
        if config.gpu_last_error:
            print(f"Last error: {config.gpu_last_error}")
        
        # Write to file
        diag_file = Path(get_app_dir()) / "gpu_diagnostics.txt"
        with open(diag_file, 'w') as f:
            f.write("=== GPU Diagnostics ===\n")
            f.write(f"NVIDIA GPU detected: {cap['has_nvidia']}\n")
            if cap['has_nvidia']:
                f.write(f"Driver version: {cap['driver_version']}\n")
                f.write(f"GPU(s): {', '.join(cap['gpu_names'])}\n")
            f.write(f"GPU Pack installed: {config.gpu_pack_installed_version or 'No'}\n")
            f.write(f"GPU Pack path: {config.gpu_pack_path or 'N/A'}\n")
            f.write(f"GPU Opt-in: {config.gpu_opt_in}\n")
            f.write(f"GPU Flavor: {config.gpu_flavor}\n")
            f.write(f"Last health check: {config.gpu_last_health or 'Never'}\n")
            if config.gpu_last_error:
                f.write(f"Last error: {config.gpu_last_error}\n")
        
        print(f"\nDiagnostics written to: {diag_file}")
        should_exit = True
    
    # --setup-gpu
    if args.setup_gpu:
        print("Setting up GPU Pack...")
        
        app_version = get_app_version()
        cap = gpu_bootstrap.capability_probe()
        
        if not cap['has_nvidia']:
            print("ERROR: No NVIDIA GPU detected. GPU Pack requires NVIDIA GPU with compatible driver.")
            return True
        
        print(f"Detected driver version: {cap['driver_version']}")
        
        # Load manifests
        try:
            manifests = gpu_manifest.load_local_manifest(app_version)
        except Exception as e:
            print(f"WARNING: Could not load local manifest: {e}")
            # Use default manifests
            from typing import Dict
            manifests: Dict[str, 'gpu_manifest.GpuPackManifest'] = {}
            for flavor, manifest_data in gpu_manifest.DEFAULT_MANIFESTS.items():
                manifest_data_copy = manifest_data.copy()
                manifest_data_copy['app_version'] = app_version
                manifests[flavor] = gpu_manifest.GpuPackManifest.from_dict(manifest_data_copy)
        
        # Choose pack
        flavor_override = config.gpu_flavor if config.gpu_flavor else None
        chosen = gpu_manifest.choose_pack(manifests, cap['driver_version'], flavor_override)
        
        if not chosen:
            print("ERROR: No compatible GPU Pack found for your driver version.")
            print(f"Your driver: {cap['driver_version']}")
            print("Required: ≥531.xx (cu121) or ≥550.xx (cu124)")
            return True
        
        print(f"Selected GPU Pack: {chosen.flavor} (CUDA {chosen.cuda_version})")
        print(f"Size: ~{chosen.size / (1024**3):.1f} GB")
        print(f"PyTorch version: {chosen.torch_version}")
        
        # Download
        pack_dir = gpu_bootstrap.resolve_pack_dir(app_version, chosen.flavor)
        dest_zip = pack_dir.parent / f"{pack_dir.name}.zip"
        
        try:
            print(f"Downloading to: {dest_zip}")
            
            def progress_cb(downloaded, total):
                pct = (downloaded / total * 100) if total > 0 else 0
                print(f"Progress: {pct:.1f}% ({downloaded / (1024**2):.1f} MB / {total / (1024**2):.1f} MB)", end='\r')
            
            gpu_downloader.download_with_resume(
                url=chosen.url,
                dest_zip=dest_zip,
                expected_sha256=chosen.sha256,
                expected_size=chosen.size,
                progress_cb=progress_cb
            )
            print("\nDownload complete. Extracting...")
            
            # Extract
            gpu_downloader.extract_zip(dest_zip, pack_dir)
            gpu_downloader.write_install_record(pack_dir, chosen)
            
            # Update config
            config.gpu_pack_installed_version = chosen.app_version
            config.gpu_pack_path = str(pack_dir)
            config.gpu_opt_in = True  # Auto-enable on successful install
            config.save_config()
            
            print(f"\nGPU Pack installed successfully to: {pack_dir}")
            print("GPU acceleration enabled (GpuOptIn=true)")
            
            # Clean up zip
            if dest_zip.exists():
                dest_zip.unlink()
            part_file = Path(str(dest_zip) + ".part")
            if part_file.exists():
                part_file.unlink()
            meta_file = Path(str(dest_zip) + ".meta")
            if meta_file.exists():
                meta_file.unlink()
            
        except Exception as e:
            print(f"\nERROR: GPU Pack installation failed: {e}")
            import traceback
            traceback.print_exc()
        
        should_exit = True
    
    # --setup-gpu-zip
    if args.setup_gpu_zip:
        print(f"Installing GPU Pack from: {args.setup_gpu_zip}")
        
        zip_path = Path(args.setup_gpu_zip)
        if not zip_path.exists():
            print(f"ERROR: File not found: {zip_path}")
            return True
        
        app_version = get_app_version()
        
        # Try to infer flavor from filename (e.g., "usdxfixgap-gpu-cu121-v1.0.0.zip")
        flavor = None
        if 'cu121' in zip_path.name.lower():
            flavor = 'cu121'
        elif 'cu124' in zip_path.name.lower():
            flavor = 'cu124'
        else:
            # Default to config flavor
            flavor = config.gpu_flavor if config.gpu_flavor else 'cu121'
        
        print(f"Detected flavor: {flavor}")
        
        pack_dir = gpu_bootstrap.resolve_pack_dir(app_version, flavor)
        
        try:
            print(f"Extracting to: {pack_dir}")
            gpu_downloader.extract_zip(zip_path, pack_dir)
            
            # Create minimal install record (no manifest info available)
            import json
            from datetime import datetime
            install_info = {
                'app_version': app_version,
                'flavor': flavor,
                'install_timestamp': datetime.utcnow().isoformat() + 'Z',
                'source': 'offline_zip'
            }
            install_json = pack_dir / "install.json"
            with open(install_json, 'w') as f:
                json.dump(install_info, f, indent=2)
            
            # Update config
            config.gpu_pack_installed_version = app_version
            config.gpu_pack_path = str(pack_dir)
            config.gpu_opt_in = True
            config.save_config()
            
            print(f"\nGPU Pack installed successfully from ZIP")
            print("GPU acceleration enabled (GpuOptIn=true)")
            
        except Exception as e:
            print(f"\nERROR: GPU Pack installation from ZIP failed: {e}")
            import traceback
            traceback.print_exc()
        
        should_exit = True
    
    return should_exit


def main():
    # Parse CLI arguments BEFORE anything else
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
    
    args = parser.parse_args()
    
    # First create config to get log level before configuring logging
    config = Config()
    
    # Handle GPU CLI flags (may exit early)
    if any([args.setup_gpu, args.setup_gpu_zip, args.gpu_enable, args.gpu_disable, args.gpu_diagnostics]):
        should_exit = handle_gpu_cli_flags(args, config)
        if should_exit:
            sys.exit(0)
    
    # Bootstrap GPU Pack BEFORE any provider imports
    # This modifies sys.path and DLL search paths if GPU is enabled
    from utils import gpu_bootstrap
    gpu_enabled = gpu_bootstrap.bootstrap_and_maybe_enable_gpu(config)

    # --- Async Logging Setup ---
    log_file_path = os.path.join(get_app_dir(), 'usdxfixgap.log')
    setup_async_logging(
        log_level=config.log_level,
        log_file_path=log_file_path,
        max_bytes=10*1024*1024,  # 10MB
        backup_count=3
    )
    
    logger = logging.getLogger(__name__)
    logger.info(f"Application started with log level: {config.log_level_str}")
    
    # --- GPU Status Logging ---
    from utils.gpu_startup_logger import log_gpu_status
    log_gpu_status(config, gpu_enabled, show_gui_dialog=True)
    # --- End Logging Setup ---

    # Initialize database before creating AppData
    db_path = initialize_song_cache()
    logger.info(f"Song cache database initialized at: {db_path}")

    data = AppData()
    data.config = config  # Make sure AppData uses our already created config
    actions = Actions(data)

    app = QApplication(sys.argv)

    # Example usage - This should now work correctly with the bundled asset
    icon_path = resource_path("assets/usdxfixgap-icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
        logger.info(f"Loaded icon from: {icon_path}")
    else:
        logger.error(f"Icon file not found at expected path: {icon_path}")

    # Create the main window and set its properties
    window = QWidget()
    window.setWindowTitle("USDX Gap Fix Gui")
    window.resize(800, 600)
    window.setMinimumSize(600, 600)

    menuBar = MenuBar(actions, data)
    songStatus = SongsStatusVisualizer(data.songs)
    songListView = SongListWidget(data.songs, actions, data)
    mediaPlayerComponent = MediaPlayerComponent(data, actions)
    taskQueueViewer = TaskQueueViewer(actions.worker_queue)
    logViewer = LogViewerWidget(log_file_path, max_lines=1000)  # Keep last 1000 log lines with scrolling

    app.installEventFilter(mediaPlayerComponent.globalEventFilter)

    # Set up the layout and add your components
    layout = QVBoxLayout()
    layout.addWidget(menuBar)
    layout.addWidget(songStatus)
    layout.addWidget(songListView, 2)  # Adjust stretch factor as needed
    layout.addWidget(mediaPlayerComponent, 1)  # Adjust stretch factor as needed
    layout.addWidget(taskQueueViewer, 1)  # Adjust stretch factor as needed
    layout.addWidget(logViewer)  # Add log viewer at bottom (no stretch - fixed height)

    window.setLayout(layout)

    logger.debug("Runtime PySide6 version: %s", __version__)  # Updated logging
    logger.debug(f"Python Executable: {sys.executable}")
    logger.debug(f"PYTHONPATH: {sys.path}")

    # Example usage
    dependencies = [
        ('spleeter', '--version'),
        ('ffmpeg', '-version'),  # Note that ffmpeg uses '-version' instead of '--version'
    ]
    if(not check_dependencies(dependencies)):
        logger.error("Some dependencies are not installed.")
        #sys.exit(1)

    # Check available audio output devices
    available_audio_outputs = QMediaDevices.audioOutputs()
    if not available_audio_outputs:
        logger.error("No audio output devices available.")
    else:
        logger.debug(f"Available audio outputs: {available_audio_outputs}")

    # Check available multimedia backends
    try:
        supported_mime_types = QMediaDevices.supportedMimeTypes()
        logger.debug(f"Available multimedia backends: {supported_mime_types}")
    except AttributeError:
        logger.warning("Unable to retrieve supported multimedia backends. This feature may not be available in your PySide6 version.")

    # Show the window
    window.show()

    actions.auto_load_last_directory()

    enable_dark_mode(app)

    # Set up proper shutdown
    app.aboutToQuit.connect(shutdown_async_logging)
    app.aboutToQuit.connect(lambda: data.worker_queue.shutdown())
    app.aboutToQuit.connect(logViewer.cleanup)  # Stop log viewer timer

    # Start the event loop
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
