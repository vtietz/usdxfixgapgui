"""
GPU Pack Utility Functions

Provides utilities for managing GPU Pack installations:
- Resolving pack directories
- Finding installed packs
- Selecting best pack
- Auto-recovering pack configuration

This module is frozen-safe and works in both dev and bundled contexts.
"""

import os
import json
import re
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


def resolve_pack_dir(app_version: str, flavor: str = "cu121") -> Path:
    """
    Resolve the GPU Pack installation directory.

    Args:
        app_version: Application version (e.g., "1.4.0")
        flavor: CUDA flavor (cu121 or cu124)

    Returns:
        Path to GPU Pack directory
    """
    local_app_data = os.getenv("LOCALAPPDATA")
    if not local_app_data:
        # Fallback for non-Windows or missing env var
        local_app_data = os.path.expanduser("~/.local/share")

    pack_dir = Path(local_app_data) / "USDXFixGap" / "gpu_runtime" / f"v{app_version}-{flavor}"
    return pack_dir


def find_installed_pack_dirs() -> List[Dict[str, Any]]:
    """
    Scan GPU runtime root for existing GPU Pack installations.

    Returns:
        List of dictionaries with keys: path, app_version, flavor, has_install_json
    """
    # Use portable-aware path detection
    try:
        from utils.files import get_localappdata_dir

        local_app_data = get_localappdata_dir()
    except ImportError:
        # Fallback if utils.files not available
        local_app_data = os.getenv("LOCALAPPDATA")
        if not local_app_data:
            local_app_data = os.path.expanduser("~/.local/share")

    runtime_root = Path(local_app_data) / "gpu_runtime"

    if not runtime_root.exists():
        return []

    candidates = []
    # Match both old format (v1.4.0-cu121) and new format (torch-2.4.1-cu121)
    old_pattern = re.compile(r"^v([\d.]+)-(cu\d+)$")
    new_pattern = re.compile(r"^torch-([\d.]+)-(cu\d+)$")

    try:
        for item in runtime_root.iterdir():
            if not item.is_dir():
                continue

            # Try to parse folder name
            match = new_pattern.match(item.name)
            if not match:
                match = old_pattern.match(item.name)

            app_version = None
            flavor = None
            has_install_json = False

            if match:
                app_version = match.group(1)
                flavor = match.group(2)

            # Check for install.json
            install_json_path = item / "install.json"
            if install_json_path.exists():
                has_install_json = True
                try:
                    with open(install_json_path, "r") as f:
                        install_data = json.load(f)
                        # Override with install.json data if available
                        if "app_version" in install_data:
                            app_version = install_data["app_version"]
                        if "flavor" in install_data:
                            flavor = install_data["flavor"]
                except Exception as e:
                    logger.debug(f"Could not parse install.json in {item}: {e}")

            # Add candidate if we have at least a version or install.json
            if app_version or has_install_json:
                candidates.append(
                    {"path": item, "app_version": app_version, "flavor": flavor, "has_install_json": has_install_json}
                )

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
        flavor_matches = [c for c in candidates if c.get("flavor") == config_flavor]
        if flavor_matches:
            candidates = flavor_matches

    # Prefer packs with install.json
    with_install = [c for c in candidates if c["has_install_json"]]
    if with_install:
        candidates = with_install

    # Sort by version (most recent first)
    def version_key(candidate):
        ver = candidate.get("app_version")
        if ver:
            try:
                parts = [int(p) for p in ver.split(".")]
                return tuple(parts)
            except Exception:
                # Ignore non-numeric version parts; treat as lowest priority
                return (0, 0, 0)
        return (0, 0, 0)

    candidates.sort(key=version_key, reverse=True)

    return candidates[0]["path"] if candidates else None


def detect_existing_gpu_pack(config) -> Optional[Path]:
    """
    Detect if GPU Pack exists on disk without enabling it.

    Args:
        config: Application config object

    Returns:
        Path to GPU Pack if found AND not enabled, None otherwise
    """
    # If GPU is already enabled, no need to detect/activate
    if getattr(config, "gpu_opt_in", False):
        return None

    # Check if pack path is already set and valid
    pack_path = getattr(config, "gpu_pack_path", "")
    if pack_path and Path(pack_path).exists():
        return Path(pack_path)

    # Scan for existing packs
    candidates = find_installed_pack_dirs()
    if not candidates:
        return None

    # Select best pack
    config_flavor = getattr(config, "gpu_flavor", None)
    best_pack = select_best_existing_pack(candidates, config_flavor)

    return best_pack


def activate_existing_gpu_pack(config, pack_path: Path) -> bool:
    """
    Activate an existing GPU Pack by updating config.

    Args:
        config: Application config object
        pack_path: Path to the GPU Pack to activate

    Returns:
        True if activation succeeded, False otherwise
    """
    if not pack_path.exists():
        logger.error(f"GPU Pack path does not exist: {pack_path}")
        return False

    logger.info(f"Activating existing GPU Pack at {pack_path}")

    # Update config with pack path
    config.gpu_pack_path = str(pack_path)

    # Try to read install.json for metadata
    install_json_path = pack_path / "install.json"
    if install_json_path.exists():
        try:
            with open(install_json_path, "r") as f:
                install_data = json.load(f)
                if "app_version" in install_data:
                    config.gpu_pack_installed_version = install_data["app_version"]
                if "flavor" in install_data:
                    config.gpu_flavor = install_data["flavor"]
                logger.debug(
                    f"Loaded installation metadata: version={install_data.get('app_version')}, "
                    f"flavor={install_data.get('flavor')}"
                )
        except Exception as e:
            logger.debug(f"Could not read install.json: {e}")

    # Enable GPU
    config.gpu_opt_in = True
    logger.info("GPU Pack enabled in config")

    # Save config
    try:
        config.save_config()
        logger.info("Config updated and saved")
        return True
    except Exception as e:
        logger.error(f"Failed to save config: {e}")
        return False


def auto_recover_gpu_pack_config(config) -> bool:
    """
    Auto-detect and recover GPU Pack configuration if pack exists on disk.

    DEPRECATED: This function auto-enables GPU Pack without user consent.
    Use detect_existing_gpu_pack() + activate_existing_gpu_pack() instead
    to prompt user first.

    If config.gpu_pack_path is empty but a valid pack is found on disk,
    this function will update the config and optionally enable GPU.

    Args:
        config: Application config object

    Returns:
        True if recovery was performed, False otherwise
    """
    # Only recover if pack path is not set
    pack_path = getattr(config, "gpu_pack_path", "")
    if pack_path:
        return False

    logger.debug("GPU Pack path empty in config, scanning for existing installations...")

    # Detect existing pack
    best_pack = detect_existing_gpu_pack(config)
    if not best_pack:
        logger.debug("No suitable GPU Pack found")
        return False

    # Activate the pack (auto-enable without prompt - deprecated behavior)
    logger.info(f"Auto-recovery: Found existing GPU Pack at {best_pack}")
    return activate_existing_gpu_pack(config, best_pack)
