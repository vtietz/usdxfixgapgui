"""
GPU Bootstrap Module for USDXFixGap

Handles GPU Pack runtime activation, CUDA validation, and environment setup.
Ensures PyTorch with CUDA is loaded correctly before any provider imports.
"""

import os
import sys
import subprocess
import logging
from typing import Dict, Optional, Tuple, List, Any
from pathlib import Path

logger = logging.getLogger(__name__)

# Module-level list to track DLL directories added for diagnostics
ADDED_DLL_DIRS: List[str] = []


def _check_vcruntime() -> None:
    """
    Check for Microsoft Visual C++ Redistributable DLLs on Windows.
    Logs a warning with download URL if they're missing.
    """
    if sys.platform != 'win32':
        return

    try:
        import ctypes

        # Try to load critical VC++ runtime DLLs
        required_dlls = ['vcruntime140_1.dll', 'msvcp140.dll']
        missing_dlls = []

        for dll_name in required_dlls:
            try:
                ctypes.WinDLL(dll_name)
            except (OSError, FileNotFoundError):
                missing_dlls.append(dll_name)

        if missing_dlls:
            logger.warning(
                f"Microsoft Visual C++ Redistributable DLLs missing: {', '.join(missing_dlls)}. "
                "Install Visual Studio 2015-2022 (x64) runtime from: "
                "https://aka.ms/vs/17/release/vc_redist.x64.exe"
            )
    except Exception as e:
        logger.debug(f"Could not check VC++ runtime: {e}")


def resolve_pack_dir(app_version: str, flavor: str = "cu121") -> Path:
    """
    Resolve the GPU Pack installation directory.

    Args:
        app_version: Application version (e.g., "1.4.0")
        flavor: CUDA flavor (cu121 or cu124)

    Returns:
        Path to GPU Pack directory
    """
    local_app_data = os.getenv('LOCALAPPDATA')
    if not local_app_data:
        # Fallback for non-Windows or missing env var
        local_app_data = os.path.expanduser('~/.local/share')

    pack_dir = Path(local_app_data) / 'USDXFixGap' / 'gpu_runtime' / f'v{app_version}-{flavor}'
    return pack_dir


def find_installed_pack_dirs() -> List[Dict[str, Any]]:
    """
    Scan GPU runtime root for existing GPU Pack installations.

    Returns:
        List of dictionaries with keys: path, app_version, flavor, has_install_json
    """
    import json
    import re

    local_app_data = os.getenv('LOCALAPPDATA')
    if not local_app_data:
        local_app_data = os.path.expanduser('~/.local/share')

    runtime_root = Path(local_app_data) / 'USDXFixGap' / 'gpu_runtime'

    if not runtime_root.exists():
        return []

    candidates = []
    version_pattern = re.compile(r'^v([\d.]+)-(cu\d+)$')

    try:
        for item in runtime_root.iterdir():
            if not item.is_dir():
                continue

            # Try to parse folder name (e.g., v1.4.0-cu121)
            match = version_pattern.match(item.name)
            app_version = None
            flavor = None
            has_install_json = False

            if match:
                app_version = match.group(1)
                flavor = match.group(2)

            # Check for install.json
            install_json_path = item / 'install.json'
            if install_json_path.exists():
                has_install_json = True
                try:
                    with open(install_json_path, 'r') as f:
                        install_data = json.load(f)
                        # Override with install.json data if available
                        if 'app_version' in install_data:
                            app_version = install_data['app_version']
                        if 'flavor' in install_data:
                            flavor = install_data['flavor']
                except Exception as e:
                    logger.debug(f"Could not parse install.json in {item}: {e}")

            # Add candidate if we have at least a version or install.json
            if app_version or has_install_json:
                candidates.append({
                    'path': item,
                    'app_version': app_version,
                    'flavor': flavor,
                    'has_install_json': has_install_json
                })

    except Exception as e:
        logger.debug(f"Error scanning GPU runtime directory: {e}")

    return candidates


def select_best_existing_pack(candidates: List[Dict[str, Any]], config_flavor: Optional[str] = None) -> Optional[Path]:
    """
    Select the best GPU Pack from candidates.

    Preference order:
    1. Matches config.gpu_flavor if provided
    2. Has valid install.json
    3. Most recent version

    Args:
        candidates: List of candidate pack dictionaries
        config_flavor: Optional preferred flavor from config

    Returns:
        Path to best pack or None
    """
    if not candidates:
        return None

    # Filter by flavor if specified
    if config_flavor:
        flavor_matches = [c for c in candidates if c.get('flavor') == config_flavor]
        if flavor_matches:
            candidates = flavor_matches

    # Prefer packs with install.json
    with_install = [c for c in candidates if c['has_install_json']]
    if with_install:
        candidates = with_install

    # Sort by version (most recent first)
    def version_key(candidate):
        ver = candidate.get('app_version')
        if ver:
            try:
                parts = [int(p) for p in ver.split('.')]
                return tuple(parts)
            except:
                pass
        return (0, 0, 0)

    candidates.sort(key=version_key, reverse=True)

    return candidates[0]['path'] if candidates else None


def auto_recover_gpu_pack_config(config) -> bool:
    """
    Auto-detect and recover GPU Pack configuration if pack exists on disk.

    If config.gpu_pack_path is empty but a valid pack is found on disk,
    this function will update the config and optionally enable GPU.

    Args:
        config: Application config object

    Returns:
        True if recovery was performed, False otherwise
    """
    import json

    # Only recover if pack path is not set
    pack_path = getattr(config, 'gpu_pack_path', '')
    if pack_path:
        return False

    logger.debug("GPU Pack path empty in config, scanning for existing installations...")

    # Scan for existing packs
    candidates = find_installed_pack_dirs()
    if not candidates:
        logger.debug("No existing GPU Pack installations found")
        return False

    # Select best pack
    config_flavor = getattr(config, 'gpu_flavor', None)
    best_pack = select_best_existing_pack(candidates, config_flavor)

    if not best_pack:
        logger.debug("No suitable GPU Pack found")
        return False

    logger.info(f"Auto-recovery: Found existing GPU Pack at {best_pack}")

    # Update config with found pack
    config.gpu_pack_path = str(best_pack)

    # Try to read install.json for version info
    install_json_path = best_pack / 'install.json'
    if install_json_path.exists():
        try:
            with open(install_json_path, 'r') as f:
                install_data = json.load(f)
                if 'app_version' in install_data:
                    config.gpu_pack_installed_version = install_data['app_version']
                if 'flavor' in install_data and not config_flavor:
                    config.gpu_flavor = install_data['flavor']
                logger.debug(f"Loaded installation metadata: version={install_data.get('app_version')}, "
                           f"flavor={install_data.get('flavor')}")
        except Exception as e:
            logger.debug(f"Could not read install.json: {e}")

    # Auto-enable GPU if pack is found (silent recovery)
    # This ensures bootstrap proceeds to validate CUDA
    config.gpu_opt_in = True
    logger.info("Auto-recovery: Enabled GPU opt-in for existing pack")

    # Save config
    try:
        config.save_config()
        logger.info("Auto-recovery: Config updated and saved")
        return True
    except Exception as e:
        logger.error(f"Failed to save recovered config: {e}")
        return False


def probe_nvml() -> Optional[Tuple[List[str], str]]:
    """
    Probe GPU information using pynvml library.

    Returns:
        Tuple of (gpu_names, driver_version) or None if pynvml not available
    """
    try:
        import pynvml
        pynvml.nvmlInit()

        driver_version = pynvml.nvmlSystemGetDriverVersion()
        if isinstance(driver_version, bytes):
            driver_version = driver_version.decode('utf-8')

        device_count = pynvml.nvmlDeviceGetCount()
        gpu_names = []

        for i in range(device_count):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            name = pynvml.nvmlDeviceGetName(handle)
            if isinstance(name, bytes):
                name = name.decode('utf-8')
            gpu_names.append(name)

        pynvml.nvmlShutdown()
        return (gpu_names, driver_version)

    except (ImportError, Exception) as e:
        logger.debug(f"pynvml not available: {e}")
        return None


def probe_nvidia_smi() -> Optional[Tuple[List[str], str]]:
    """
    Fallback GPU probe using nvidia-smi command.

    Returns:
        Tuple of (gpu_names, driver_version) or None if nvidia-smi not available
    """
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=name,driver_version', '--format=csv,noheader'],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode != 0:
            return None

        lines = result.stdout.strip().split('\n')
        if not lines or not lines[0]:
            return None

        gpu_names = []
        driver_version = None

        for line in lines:
            parts = [p.strip() for p in line.split(',')]
            if len(parts) >= 2:
                gpu_names.append(parts[0])
                if driver_version is None:
                    driver_version = parts[1]

        return (gpu_names, driver_version) if gpu_names and driver_version else None

    except (FileNotFoundError, subprocess.TimeoutExpired, Exception) as e:
        logger.debug(f"nvidia-smi not available: {e}")
        return None


def capability_probe() -> Dict[str, Any]:
    """
    Probe NVIDIA GPU capability and driver information.

    Returns:
        Dictionary with keys: has_nvidia, driver_version, gpu_names
    """
    # Try pynvml first, fallback to nvidia-smi
    result = probe_nvml()
    if result is None:
        result = probe_nvidia_smi()

    if result is None:
        return {
            'has_nvidia': False,
            'driver_version': None,
            'gpu_names': []
        }

    gpu_names, driver_version = result
    return {
        'has_nvidia': True,
        'driver_version': driver_version,
        'gpu_names': gpu_names
    }


def enable_gpu_runtime(pack_dir: Path, config=None) -> bool:
    """
    Enable GPU Pack runtime by modifying sys.path and DLL search paths.

    Args:
        pack_dir: Path to GPU Pack installation
        config: Optional config object (unused, kept for compatibility)

    Returns:
        True if successful, False otherwise
    """
    global ADDED_DLL_DIRS

    # Use GPU bootstrap orchestrator
    from utils.gpu_bootstrap import enable_runtime
    logger.debug("Using GPU bootstrap")
    success, added_dirs = enable_runtime(pack_dir)
    if success:
        ADDED_DLL_DIRS = added_dirs
    return success


def detect_system_pytorch_cuda() -> Optional[Dict[str, str]]:
    """
    Detect if system has usable PyTorch with CUDA support.

    Checks if PyTorch is already available in the system/environment
    (not from GPU Pack) and has CUDA support enabled.

    Returns:
        Dict with torch_version, cuda_version, device_name if usable
        None if PyTorch not available or CUDA not supported
    """
    try:
        import torch

        # Check if CUDA is available
        if not torch.cuda.is_available():
            logger.debug("System PyTorch found but CUDA not available")
            return None

        # Check minimum PyTorch version (2.0+)
        version = torch.__version__
        try:
            major = int(version.split('.')[0].replace('+', ''))  # Handle version like "2.7.1+cpu"
            if major < 2:
                logger.debug(f"System PyTorch version too old: {version} (need 2.0+)")
                return None
        except (ValueError, IndexError):
            logger.debug(f"Could not parse PyTorch version: {version}")
            return None

        # Get CUDA version
        cuda_version = torch.version.cuda
        if cuda_version is None:
            logger.debug("System PyTorch has no CUDA version")
            return None

        # Get device name
        try:
            device_name = torch.cuda.get_device_name(0)
        except Exception as e:
            logger.debug(f"Could not get CUDA device name: {e}")
            device_name = "Unknown GPU"

        return {
            'torch_version': version,
            'cuda_version': cuda_version,
            'device_name': device_name
        }

    except ImportError:
        logger.debug("System PyTorch not available (ImportError)")
        return None
    except Exception as e:
        logger.debug(f"Error detecting system PyTorch: {e}")
        return None


def validate_cuda_torch(expected_cuda: str = "12.1") -> Tuple[bool, str]:
    """
    Validate that PyTorch with CUDA is properly loaded and functional.

    Args:
        expected_cuda: Expected CUDA version (e.g., "12.1" for exact match, "12" for any 12.x)

    Returns:
        Tuple of (success, error_message)
    """
    try:
        import torch

        # Check if CUDA is available
        if not torch.cuda.is_available():
            return (False, "torch.cuda.is_available() returned False")

        # Check CUDA version match
        torch_cuda_version = torch.version.cuda
        if torch_cuda_version is None:
            return (False, "torch.version.cuda is None")

        # Compare versions
        expected_parts = expected_cuda.split('.')
        actual_parts = torch_cuda_version.split('.')

        # If only major version specified (e.g., "12"), accept any minor version
        compare_parts = len(expected_parts)
        if expected_parts[:compare_parts] != actual_parts[:compare_parts]:
            return (False, f"CUDA version mismatch: expected {expected_cuda}.x, got {torch_cuda_version}")

        # Smoke test: create tensor on GPU and perform operation
        try:
            device = torch.device('cuda:0')
            x = torch.randn(100, 100, device=device)
            y = torch.randn(100, 100, device=device)
            z = torch.matmul(x, y)

            # Ensure computation completed
            torch.cuda.synchronize()

            if z.device.type != 'cuda':
                return (False, "Smoke test failed: result not on GPU")

        except Exception as e:
            return (False, f"Smoke test failed: {str(e)}")

        logger.info(f"CUDA validation successful: PyTorch {torch.__version__}, CUDA {torch_cuda_version}")
        return (True, "")

    except ImportError as e:
        return (False, f"Failed to import torch: {str(e)}")
    except Exception as e:
        return (False, f"Unexpected error during validation: {str(e)}")


def validate_torch_cpu() -> Tuple[bool, str]:
    """
    Validate that PyTorch is available for CPU-only operation.
    Does not check CUDA availability - only verifies torch can be imported.

    Returns:
        Tuple of (success, error_message)
    """
    try:
        import torch

        # Basic smoke test on CPU
        try:
            x = torch.randn(10, 10)
            y = torch.randn(10, 10)
            z = torch.matmul(x, y)

            if z.shape != (10, 10):
                return (False, "CPU smoke test failed: unexpected result shape")
        except Exception as e:
            return (False, f"CPU smoke test failed: {str(e)}")

        logger.info(f"CPU-only torch validation successful: PyTorch {torch.__version__}")
        return (True, "")

    except ImportError as e:
        return (False, f"Failed to import torch: {str(e)}")
    except Exception as e:
        return (False, f"Unexpected error during CPU validation: {str(e)}")


def bootstrap_and_maybe_enable_gpu(config) -> bool:
    """
    Orchestrate GPU Pack activation and validation.
    Tries multiple approaches in order:
    1. If prefer_system_pytorch=true: Try system PyTorch+CUDA first
    2. Use GPU Pack if installed and enabled
    3. Auto-detect system-wide CUDA/PyTorch if available (fallback)
    4. Fall back to CPU-only torch (if torch already importable)
    5. Fall back to no torch (FFmpeg only)

    Args:
        config: Application config object

    Returns:
        True if GPU is enabled and validated, False otherwise
    """
    global ADDED_DLL_DIRS

    try:
        # Auto-recover GPU Pack config if pack exists on disk but config is empty
        auto_recover_gpu_pack_config(config)

        # Check if user has explicitly disabled GPU
        gpu_opt_in = getattr(config, 'gpu_opt_in', None)
        if gpu_opt_in is False:
            logger.debug("GPU acceleration explicitly disabled (GpuOptIn=false)")
            return False

        # STEP 1: Try system PyTorch+CUDA first if enabled
        prefer_system = getattr(config, 'prefer_system_pytorch', True)
        if prefer_system and gpu_opt_in is not False:
            logger.debug("Checking for system PyTorch with CUDA...")
            system_pytorch = detect_system_pytorch_cuda()
            
            if system_pytorch:
                logger.info(f"Found system PyTorch {system_pytorch['torch_version']} "
                           f"with CUDA {system_pytorch['cuda_version']} "
                           f"({system_pytorch['device_name']})")
                
                # Validate it works properly
                try:
                    success, error_msg = validate_cuda_torch(expected_cuda="12")  # Accept CUDA 12.x
                    if success:
                        logger.info("✓ System PyTorch validated successfully - using it instead of GPU Pack")
                        config.gpu_last_health = "healthy (system)"
                        config.gpu_last_error = ""
                        config.save_config()
                        return True
                    else:
                        logger.warning(f"System PyTorch validation failed: {error_msg}")
                        logger.info("Falling back to GPU Pack...")
                except Exception as e:
                    logger.warning(f"System PyTorch validation error: {e}")
                    logger.info("Falling back to GPU Pack...")
            else:
                logger.debug("System PyTorch with CUDA not found, trying GPU Pack...")

        # STEP 2: Try GPU Pack if configured
        pack_path = getattr(config, 'gpu_pack_path', '')
        pack_dir = None
        gpu_flavor = getattr(config, 'gpu_flavor', 'cu121')
        expected_cuda = "12.1" if gpu_flavor == "cu121" else "12.4"

        if pack_path:
            pack_dir = Path(pack_path)

            # Check if GPU Pack directory exists before trying to enable it
            if not pack_dir.exists():
                logger.debug(f"GPU Pack path configured but directory not found: {pack_dir}")
                logger.debug("Will attempt to detect system-wide CUDA installation...")
            else:
                # Enable GPU runtime
                if enable_gpu_runtime(pack_dir, config):
                    # Validate CUDA
                    success, error_msg = validate_cuda_torch(expected_cuda)

                    if success:
                        config.gpu_last_health = "healthy"
                        config.gpu_last_error = ""
                        config.save_config()
                        logger.info("GPU Pack activated successfully")
                        return True
                    else:
                        logger.warning(f"GPU Pack validation failed: {error_msg}")
                        # Compose detailed diagnostic message
                        diagnostic_info = _build_diagnostic_message(pack_dir, gpu_flavor, expected_cuda, error_msg)
                        config.gpu_last_error = diagnostic_info
                        config.gpu_last_health = "failed"
                        config.save_config()
                        # GPU Pack failed - don't try CPU fallback with broken GPU Pack in sys.path
                        # User needs to fix or remove GPU Pack
                        return False
                else:
                    logger.debug(f"Could not enable GPU runtime from {pack_dir}, trying system CUDA...")

        # STEP 3: If GPU Pack not available or failed, try system-wide CUDA/PyTorch (fallback)
        if gpu_opt_in is not False:  # None or True means try auto-detection
            logger.debug("Attempting to detect system-wide CUDA/PyTorch...")
            success, error_msg = validate_cuda_torch(expected_cuda="12")  # Accept CUDA 12.x

            if success:
                logger.info("System-wide CUDA/PyTorch detected and validated successfully")
                config.gpu_last_health = "healthy (system)"
                config.gpu_last_error = ""
                config.save_config()
                return True
            else:
                logger.debug(f"System CUDA not available or validation failed: {error_msg}")

        # No GPU available - final state
        logger.info("GPU not available. Application will use CPU-only providers or FFmpeg fallback.")
        config.gpu_last_health = "unavailable"
        config.gpu_last_error = ""
        config.save_config()
        return False

    except Exception as e:
        error_msg = f"Unexpected error during GPU bootstrap: {str(e)}"
        logger.error(error_msg, exc_info=True)
        try:
            config.gpu_last_health = "failed"
            config.gpu_last_error = error_msg
            config.save_config()
        except:
            pass
        return False


def _build_diagnostic_message(pack_dir: Optional[Path], flavor: str, expected_cuda: str, error_msg: str) -> str:
    """Build detailed diagnostic message for GPU bootstrap failure."""
    lines = [f"GPU Pack validation failed: {error_msg}"]

    if pack_dir:
        lines.append(f"Pack path: {pack_dir}")
    lines.append(f"Pack flavor: {flavor}")
    lines.append(f"Expected CUDA: {expected_cuda}")

    if ADDED_DLL_DIRS:
        lines.append(f"DLL directories added: {', '.join(ADDED_DLL_DIRS)}")
    else:
        lines.append("No DLL directories were added")

    env_pack_dir = os.environ.get('USDXFIXGAP_GPU_PACK_DIR', 'Not set')
    lines.append(f"USDXFIXGAP_GPU_PACK_DIR: {env_pack_dir}")

    lines.append("Run --gpu-diagnostics for detailed information")

    return " | ".join(lines)


def child_process_min_bootstrap():
    """
    Minimal bootstrap for child processes.
    Replicates GPU Pack activation using environment variable.
    """
    pack_dir_str = os.environ.get('USDXFIXGAP_GPU_PACK_DIR')
    if pack_dir_str:
        pack_dir = Path(pack_dir_str)
        if pack_dir.exists():
            enable_gpu_runtime(pack_dir)
            logger.debug(f"Child process: GPU Pack activated from {pack_dir}")
