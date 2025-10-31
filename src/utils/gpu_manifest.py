"""
GPU Pack Manifest Module for USDXFixGap

Handles GPU Pack metadata, version management, and pack selection logic.
"""

import json
import logging
import sys
from dataclasses import dataclass, asdict
from typing import Optional, Dict
from pathlib import Path
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)


@dataclass
class GpuPackManifest:
    """GPU Pack metadata and download information."""

    app_version: str
    torch_version: str
    cuda_version: str
    url: str
    sha256: str
    size: int
    min_driver: str
    flavor: str  # cu121 or cu124

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> "GpuPackManifest":
        """Create from dictionary."""
        return cls(**data)


# Embedded default manifests for offline operation
#
# These use official PyTorch wheel URLs from download.pytorch.org.
# PyTorch wheels bundle CUDA/cuDNN - only a compatible NVIDIA driver is needed.
# Wheels are downloaded, extracted to data directory (LOCALAPPDATA on Windows,
# ~/.local/share on Linux), and loaded via sys.path at runtime.
#
# Python version detection: sys.version_info to determine cp310/cp311/cp312
# Platform detection: sys.platform to determine win_amd64 vs linux_x86_64
# The app_version field is metadata only - GPU Pack is versioned by PyTorch/CUDA version.

# Detect platform and Python version for wheel selection
_PLATFORM_SUFFIX = "win_amd64" if sys.platform == "win32" else "linux_x86_64"
_PYTHON_VERSION = f"cp{sys.version_info.major}{sys.version_info.minor}"  # e.g., cp312 for Python 3.12

# Python version specific wheel metadata
# SHA256 and size vary by Python version, so we define them per version
_WHEEL_METADATA = {
    "cu121": {
        "cp38": {
            "sha256": "a48b991cd861266523cbed4705f89bef09669d5d2bbfa2524486156f74a222a8",
            "size": 2444894201,  # ~2.44GB
        },
        "cp312": {
            "sha256": "TBD",  # Will be computed on first successful download
            "size": 2444846875,  # Actual size of torch-2.4.1+cu121-cp312-cp312-win_amd64.whl
        },
    },
    "cu124": {
        "cp38": {"sha256": "TBD", "size": 2444894201},
        "cp312": {"sha256": "TBD", "size": 2444894201},  # Approximate, will be corrected on first download
    },
}


# Get metadata for current Python version, fallback to cp38 if unavailable
def _get_wheel_metadata(flavor: str) -> Dict:
    """Get wheel metadata for current Python version."""
    flavor_meta = _WHEEL_METADATA.get(flavor, {})
    py_meta = flavor_meta.get(_PYTHON_VERSION)

    if not py_meta:
        # Fallback to cp38 if current Python version not explicitly defined
        logger.warning(f"No wheel metadata for {_PYTHON_VERSION}, using cp38 metadata as fallback")
        py_meta = flavor_meta.get("cp38", {"sha256": "TBD", "size": 2444894201})

    return py_meta


DEFAULT_MANIFESTS = {
    "cu121": {
        "app_version": "1.0.0",  # Metadata only
        "torch_version": "2.4.1+cu121",
        "cuda_version": "12.1",
        "url": f"https://download.pytorch.org/whl/cu121/torch-2.4.1%2Bcu121-{_PYTHON_VERSION}-{_PYTHON_VERSION}-{_PLATFORM_SUFFIX}.whl",
        **_get_wheel_metadata("cu121"),
        "min_driver": "531.00",
        "flavor": "cu121",
    },
    "cu124": {
        "app_version": "1.0.0",  # Metadata only
        "torch_version": "2.4.1+cu124",
        "cuda_version": "12.4",
        "url": f"https://download.pytorch.org/whl/cu124/torch-2.4.1%2Bcu124-{_PYTHON_VERSION}-{_PYTHON_VERSION}-{_PLATFORM_SUFFIX}.whl",
        **_get_wheel_metadata("cu124"),
        "min_driver": "550.00",
        "flavor": "cu124",
    },
}


def load_local_manifest(app_version: str) -> Dict[str, GpuPackManifest]:
    """
    Load bundled GPU Pack manifest.

    Args:
        app_version: Application version

    Returns:
        Dictionary of flavor -> GpuPackManifest
    """
    manifests = {}

    # Try to load from bundled JSON file if it exists
    try:
        from utils.files import resource_path

        manifest_path = resource_path("gpu_pack_manifest.json")

        if Path(manifest_path).exists():
            with open(manifest_path, "r") as f:
                data = json.load(f)
                for flavor, manifest_data in data.items():
                    manifests[flavor] = GpuPackManifest.from_dict(manifest_data)
                logger.info(f"Loaded manifest from {manifest_path}")
                return manifests
    except Exception as e:
        logger.debug(f"Could not load bundled manifest: {e}")

    # Fallback to embedded defaults
    for flavor, manifest_data in DEFAULT_MANIFESTS.items():
        manifest_data_copy = manifest_data.copy()
        manifest_data_copy["app_version"] = app_version  # Use current app version
        manifests[flavor] = GpuPackManifest.from_dict(manifest_data_copy)

    logger.debug("Using embedded default manifest")
    return manifests


def fetch_remote_manifest(url: str, timeout: int = 10) -> Optional[Dict[str, GpuPackManifest]]:
    """
    Fetch GPU Pack manifest from remote URL.

    Args:
        url: URL to manifest JSON
        timeout: Request timeout in seconds

    Returns:
        Dictionary of flavor -> GpuPackManifest or None on failure
    """
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "USDXFixGap/1.0"})

        with urllib.request.urlopen(req, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))

            manifests = {}
            for flavor, manifest_data in data.items():
                manifests[flavor] = GpuPackManifest.from_dict(manifest_data)

            logger.info(f"Fetched remote manifest from {url}")
            return manifests

    except urllib.error.URLError as e:
        logger.warning(f"Failed to fetch remote manifest: {e}")
        return None
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse remote manifest JSON: {e}")
        return None
    except Exception as e:
        logger.warning(f"Unexpected error fetching manifest: {e}")
        return None


def compare_driver_version(driver_version: str, min_required: str) -> bool:
    """
    Compare driver versions.

    Args:
        driver_version: Installed driver version (e.g., "531.68")
        min_required: Minimum required version (e.g., "531.00")

    Returns:
        True if driver_version >= min_required
    """
    try:
        driver_parts = [int(x) for x in driver_version.split(".")]
        required_parts = [int(x) for x in min_required.split(".")]

        # Pad to same length
        max_len = max(len(driver_parts), len(required_parts))
        driver_parts += [0] * (max_len - len(driver_parts))
        required_parts += [0] * (max_len - len(required_parts))

        return driver_parts >= required_parts

    except Exception as e:
        logger.warning(f"Failed to compare driver versions: {e}")
        return False


def choose_pack(
    manifests: Dict[str, GpuPackManifest], driver_version: Optional[str] = None, flavor_override: Optional[str] = None
) -> Optional[GpuPackManifest]:
    """
    Choose appropriate GPU Pack based on driver version and preferences.

    Args:
        manifests: Available manifests
        driver_version: Installed NVIDIA driver version
        flavor_override: User-specified flavor override (cu121 or cu124)

    Returns:
        Selected GpuPackManifest or None
    """
    # If user specified a flavor, use it
    if flavor_override:
        if flavor_override in manifests:
            manifest = manifests[flavor_override]

            # Warn if driver doesn't meet minimum requirement
            if driver_version and not compare_driver_version(driver_version, manifest.min_driver):
                logger.warning(
                    f"Driver version {driver_version} may not support {flavor_override} "
                    f"(minimum: {manifest.min_driver})"
                )

            return manifest
        else:
            logger.warning(f"Requested flavor {flavor_override} not available in manifest")
            return None

    # Auto-select based on driver version
    if not driver_version:
        # No driver info, default to cu121 (widest compatibility)
        logger.debug("No driver version available, defaulting to cu121")
        return manifests.get("cu121")

    # Check if driver supports cu124
    if "cu124" in manifests:
        cu124_manifest = manifests["cu124"]
        if compare_driver_version(driver_version, cu124_manifest.min_driver):
            logger.debug(f"Driver {driver_version} supports cu124, selecting cu124")
            return cu124_manifest

    # Fallback to cu121
    if "cu121" in manifests:
        cu121_manifest = manifests["cu121"]
        if compare_driver_version(driver_version, cu121_manifest.min_driver):
            logger.debug(f"Selecting cu121 for driver {driver_version}")
            return cu121_manifest
        else:
            logger.warning(
                f"Driver version {driver_version} does not meet minimum requirement "
                f"for cu121 ({cu121_manifest.min_driver})"
            )
            return None

    logger.warning("No suitable GPU Pack found in manifest")
    return None
