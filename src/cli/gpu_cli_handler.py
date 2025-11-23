"""
CLI Handler for GPU-related commands

Handles all GPU Pack CLI operations: setup, enable/disable, diagnostics
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict

from utils.gpu_bootstrap import capability_probe, resolve_pack_dir, ADDED_DLL_DIRS
from utils.gpu import manifest as gpu_manifest, downloader as gpu_downloader
from utils.gpu.utils import is_gpu_pack_installed, get_gpu_pack_info
from utils.files import get_app_dir
from utils.version import get_version


def _get_cli_app_version() -> str:
    """Return app version for CLI use, defaulting to semver string."""
    version = get_version().lstrip("v")
    return version if version and version != "unknown" else "1.0.0"


def handle_gpu_enable(config):
    """Enable GPU acceleration"""
    config.gpu_opt_in = True
    config.save_config()
    print("GPU acceleration enabled (gpu_opt_in=true)")


def handle_gpu_disable(config):
    """Disable GPU acceleration"""
    config.gpu_opt_in = False
    config.save_config()
    print("GPU acceleration disabled (gpu_opt_in=false)")


def _print_gpu_pack_info(config):
    """Print GPU Pack installation information."""
    if is_gpu_pack_installed(config):
        pack_info = get_gpu_pack_info(config)
        if pack_info:
            version, path = pack_info
            # Only print version if it's not "unknown"
            if version and version != "unknown":
                print(f"GPU Pack version: {version}")
            else:
                print("GPU Pack: Installed")
            print(f"GPU Pack path: {path}")

            pack_dir = Path(path)
            install_json = pack_dir / "install.json"
            if install_json.exists():
                with open(install_json, "r") as f:
                    info = json.load(f)
                # Only print values that exist
                if info.get("install_timestamp"):
                    print(f"Installed on: {info['install_timestamp']}")
                if info.get("cuda_version"):
                    print(f"CUDA version: {info['cuda_version']}")
                if info.get("torch_version"):
                    print(f"PyTorch version: {info['torch_version']}")
    else:
        print("GPU Pack: Not installed")
        if config.gpu_pack_path:
            print(f"WARNING: Config has GPU Pack path but it doesn't exist: {config.gpu_pack_path}")


def _print_config_status(config):
    """Print GPU configuration status."""
    print(f"GPU Opt-in: {config.gpu_opt_in}")
    print(f"GPU Flavor: {config.gpu_flavor}")
    print(f"Last health check: {config.gpu_last_health or 'Never'}")
    if config.gpu_last_error:
        print(f"Last error: {config.gpu_last_error}")


def _print_dll_diagnostics():
    """Print DLL path diagnostics."""
    print("\n=== DLL Path Diagnostics ===")
    if ADDED_DLL_DIRS:
        print(f"DLL directories added to search path: {len(ADDED_DLL_DIRS)}")
        for dll_dir in ADDED_DLL_DIRS:
            exists = os.path.exists(dll_dir)
            print(f"  - {dll_dir} {'[EXISTS]' if exists else '[MISSING]'}")
    else:
        print("No DLL directories added (GPU Pack not activated)")


def _print_python_path_diagnostics():
    """Print Python path diagnostics for torch-related paths."""
    print("\n=== Python Path (torch-related) ===")
    torch_paths = [p for p in sys.path if "torch" in p.lower() or "cuda" in p.lower()]
    if torch_paths:
        for p in torch_paths:
            print(f"  - {p}")
    else:
        print("  No torch-related paths in sys.path")
    return torch_paths


def _print_environment_variables():
    """Print relevant environment variables."""
    print("\n=== Environment Variables ===")

    # CUDA_PATH - only print if set
    cuda_path = os.environ.get("CUDA_PATH")
    if cuda_path:
        print(f"CUDA_PATH: {cuda_path}")

    # PATH - only print CUDA/torch entries if they exist
    path_value = os.environ.get("PATH", "")
    if path_value:
        path_entries = path_value.split(os.pathsep)
        cuda_paths = [p for p in path_entries if "cuda" in p.lower() or "torch" in p.lower()]
        if cuda_paths:
            print("PATH (CUDA/torch entries):")
            for p in cuda_paths[:5]:
                print(f"  - {p}")

    # GPU Pack specific env var
    gpu_pack_dir = os.environ.get("USDXFIXGAP_GPU_PACK_DIR")
    if gpu_pack_dir:
        print(f"USDXFIXGAP_GPU_PACK_DIR: {gpu_pack_dir}")


def _write_diagnostics_file(config, cap, torch_paths):
    """Write diagnostics information to file."""
    diag_file = Path(get_app_dir()) / "gpu_diagnostics.txt"
    with open(diag_file, "w") as f:
        f.write("=== GPU Diagnostics ===\n")
        f.write(f"NVIDIA GPU detected: {cap['has_nvidia']}\n")
        if cap["has_nvidia"]:
            f.write(f"Driver version: {cap['driver_version']}\n")
            f.write(f"GPU(s): {', '.join(cap['gpu_names'])}\n")
        f.write(f"GPU Pack installed: {config.gpu_pack_installed_version or 'No'}\n")
        f.write(f"GPU Pack path: {config.gpu_pack_path or 'N/A'}\n")
        f.write(f"GPU Opt-in: {config.gpu_opt_in}\n")
        f.write(f"GPU Flavor: {config.gpu_flavor}\n")
        f.write(f"Last health check: {config.gpu_last_health or 'Never'}\n")
        if config.gpu_last_error:
            f.write(f"Last error: {config.gpu_last_error}\n")

        f.write("\n=== DLL Path Diagnostics ===\n")
        if ADDED_DLL_DIRS:
            for dll_dir in ADDED_DLL_DIRS:
                exists = os.path.exists(dll_dir)
                f.write(f"{dll_dir} {'[EXISTS]' if exists else '[MISSING]'}\n")
        else:
            f.write("No DLL directories added\n")

        f.write("\n=== Python Path (torch-related) ===\n")
        if torch_paths:
            for p in torch_paths:
                f.write(f"{p}\n")
        else:
            f.write("No torch-related paths\n")

    print(f"\nDiagnostics written to: {diag_file}")


def handle_gpu_diagnostics(config):
    """Show GPU diagnostics and write to file."""
    print("=== GPU Diagnostics ===\n")

    # Use SystemCapabilities as single source of truth
    from services.system_capabilities import check_system_capabilities

    capabilities = check_system_capabilities()

    # Print system capabilities summary
    print("=== System Status ===")
    print(f"PyTorch: {capabilities.torch_version or 'Not available'}")
    if capabilities.has_torch:
        if capabilities.has_cuda:
            print(f"CUDA: {capabilities.cuda_version}")
            if capabilities.gpu_name:
                print(f"GPU: {capabilities.gpu_name}")
        else:
            print("CUDA: Not available")

    print(f"FFmpeg: {'Available' if capabilities.has_ffmpeg else 'Not available'}")
    print(f"Detection mode: {capabilities.get_detection_mode()}")

    # GPU Pack installation info
    print("\n=== GPU Pack ===")
    _print_gpu_pack_info(config)

    # Configuration status
    print("\n=== Configuration ===")
    _print_config_status(config)

    # Technical details for troubleshooting
    _print_dll_diagnostics()
    torch_paths = _print_python_path_diagnostics()
    _print_environment_variables()

    # Write detailed diagnostics to file
    cap = capability_probe()
    _write_diagnostics_file(config, cap, torch_paths)


def handle_setup_gpu(config):
    """Download and install GPU Pack"""
    print("Setting up GPU Pack...")

    app_version = _get_cli_app_version()
    cap = capability_probe()

    if not cap["has_nvidia"]:
        print("ERROR: No NVIDIA GPU detected. GPU Pack requires NVIDIA GPU with compatible driver.")
        return

    print(f"Detected driver version: {cap['driver_version']}")

    # Load manifests
    try:
        manifests = gpu_manifest.load_local_manifest(app_version)
    except Exception as e:
        print(f"WARNING: Could not load local manifest: {e}")
        # Use default manifests
        manifests: Dict[str, "gpu_manifest.GpuPackManifest"] = {}
        for flavor, manifest_data in gpu_manifest.DEFAULT_MANIFESTS.items():
            manifest_data_copy = manifest_data.copy()
            manifest_data_copy["app_version"] = app_version
            manifests[flavor] = gpu_manifest.GpuPackManifest.from_dict(manifest_data_copy)

    # Choose pack
    flavor_override = config.gpu_flavor if config.gpu_flavor else None
    chosen = gpu_manifest.choose_pack(manifests, cap["driver_version"], flavor_override)

    if not chosen:
        print("ERROR: No compatible GPU Pack found for your driver version.")
        print(f"Your driver: {cap['driver_version']}")
        print("Required: ≥531.xx (cu121) or ≥550.xx (cu124)")
        return

    print(f"Selected GPU Pack: {chosen.flavor} (CUDA {chosen.cuda_version})")
    print(f"Size: ~{chosen.size / (1024**3):.1f} GB")
    print(f"PyTorch version: {chosen.torch_version}")

    # Download
    pack_dir = resolve_pack_dir(app_version, chosen.flavor)
    dest_zip = pack_dir.parent / f"{pack_dir.name}.zip"

    try:
        print(f"Downloading to: {dest_zip}")

        def progress_cb(downloaded, total):
            pct = (downloaded / total * 100) if total > 0 else 0
            print(f"Progress: {pct:.1f}% ({downloaded / (1024**2):.1f} MB / {total / (1024**2):.1f} MB)", end="\r")

        gpu_downloader.download_with_resume(
            url=chosen.url,
            dest_zip=dest_zip,
            expected_sha256=chosen.sha256,
            expected_size=chosen.size,
            progress_cb=progress_cb,
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
        print("GPU acceleration enabled (gpu_opt_in=true)")

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


def handle_setup_gpu_zip(config, zip_path_str):
    """Install GPU Pack from offline ZIP file"""
    print(f"Installing GPU Pack from: {zip_path_str}")

    zip_path = Path(zip_path_str)
    if not zip_path.exists():
        print(f"ERROR: File not found: {zip_path}")
        return

    app_version = _get_cli_app_version()

    # Try to infer flavor from filename (e.g., "usdxfixgap-gpu-cu121-v1.0.0.zip")
    flavor = None
    if "cu121" in zip_path.name.lower():
        flavor = "cu121"
    elif "cu124" in zip_path.name.lower():
        flavor = "cu124"
    else:
        # Default to config flavor
        flavor = config.gpu_flavor if config.gpu_flavor else "cu121"

    print(f"Detected flavor: {flavor}")

    pack_dir = resolve_pack_dir(app_version, flavor)

    try:
        print(f"Extracting to: {pack_dir}")
        gpu_downloader.extract_zip(zip_path, pack_dir)

        # Create minimal install record (no manifest info available)
        install_info = {
            "app_version": app_version,
            "flavor": flavor,
            "install_timestamp": datetime.utcnow().isoformat() + "Z",
            "source": "offline_zip",
        }
        install_json = pack_dir / "install.json"
        with open(install_json, "w") as f:
            json.dump(install_info, f, indent=2)

        # Update config
        config.gpu_pack_installed_version = app_version
        config.gpu_pack_path = str(pack_dir)
        config.gpu_opt_in = True
        config.save_config()

        print("\nGPU Pack installed successfully from ZIP")
        print("GPU acceleration enabled (gpu_opt_in=true)")

    except Exception as e:
        print(f"\nERROR: GPU Pack installation from ZIP failed: {e}")
        import traceback

        traceback.print_exc()


def handle_gpu_cli_flags(args, config):
    """Handle GPU-related CLI flags and exit if needed

    Returns True if we should exit, False if we should continue to GUI
    """
    should_exit = False

    if args.gpu_enable:
        handle_gpu_enable(config)
        should_exit = True

    if args.gpu_disable:
        handle_gpu_disable(config)
        should_exit = True

    if args.gpu_diagnostics:
        handle_gpu_diagnostics(config)
        should_exit = True

    if args.setup_gpu:
        handle_setup_gpu(config)
        should_exit = True

    if args.setup_gpu_zip:
        handle_setup_gpu_zip(config, args.setup_gpu_zip)
        should_exit = True

    return should_exit
