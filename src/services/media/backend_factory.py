"""
Media backend factory.

Selects the best available backend based on OS and capabilities.
"""

import logging
import sys
import os
from typing import Optional
from pathlib import Path

from services.media.backend import MediaBackend
from services.media.qt_backend import QtBackendAdapter

logger = logging.getLogger(__name__)


def _setup_local_vlc_runtime():
    """
    Setup local VLC runtime if available (dev/bundled mode).

    Searches for vlc_runtime/ directory and adds DLL path on Windows.
    Sets VLC_PLUGIN_PATH and PYTHON_VLC_LIB_PATH environment variables.

    Returns:
        True if local VLC runtime was set up, False otherwise
    """
    # Find project root (4 levels up from this file: media/ -> services/ -> src/ -> project/)
    project_root = Path(__file__).parent.parent.parent.parent
    vlc_runtime_dir = project_root / "vlc_runtime"

    if not vlc_runtime_dir.exists():
        return False

    # Find VLC installation (e.g., vlc-3.0.21)
    vlc_dirs = [d for d in vlc_runtime_dir.iterdir() if d.is_dir() and d.name.startswith("vlc-")]
    if not vlc_dirs:
        return False

    # Use newest version (sort descending)
    vlc_dir = sorted(vlc_dirs, reverse=True)[0]

    # Check for required DLLs (Windows) or libs (Linux/macOS)
    if sys.platform == "win32":
        libvlc_dll = vlc_dir / "libvlc.dll"
        if not libvlc_dll.exists():
            return False

        # Set PYTHON_VLC_LIB_PATH to FULL PATH to libvlc.dll (not just directory)
        os.environ["PYTHON_VLC_LIB_PATH"] = str(libvlc_dll)

        # Also add to PATH so dependent DLLs can be found
        current_path = os.environ.get("PATH", "")
        os.environ["PATH"] = str(vlc_dir) + os.pathsep + current_path

        # And add to DLL directory (Python 3.8+)
        try:
            os.add_dll_directory(str(vlc_dir))
            logger.debug(f"Added local VLC DLL directory: {vlc_dir}")
        except (AttributeError, OSError) as e:
            logger.warning(f"Failed to add VLC DLL directory: {e}")

    # Set VLC_PLUGIN_PATH for all platforms
    plugins_dir = vlc_dir / "plugins"
    if plugins_dir.exists():
        os.environ["VLC_PLUGIN_PATH"] = str(plugins_dir)
        logger.debug(f"Set VLC_PLUGIN_PATH: {plugins_dir}")

    logger.info(f"Using local VLC runtime: {vlc_dir}")
    return True


# Setup local VLC runtime BEFORE trying to import vlc module
_local_vlc_setup = _setup_local_vlc_runtime()


def _is_vlc_available() -> bool:
    """Check if VLC backend is available."""
    try:
        import vlc  # noqa: F401
        return True
    except ImportError:
        return False


def _warn_wmf_fallback() -> None:
    """Show warning dialog about WMF fallback."""
    # Import here to avoid circular dependency
    from PySide6.QtWidgets import QMessageBox

    msg = QMessageBox()
    msg.setIcon(QMessageBox.Icon.Warning)
    msg.setWindowTitle("Media Backend Warning")
    msg.setText(
        "Using Windows Media Foundation (WMF) backend.\n\n"
        "WMF may cause UI freezes during playback. "
        "For best results, install VLC:\n\n"
        "pip install python-vlc\n\n"
        "and restart the application."
    )
    msg.setStandardButtons(QMessageBox.StandardButton.Ok)
    msg.exec()


def create_backend(warn_on_wmf_fallback: bool = True) -> MediaBackend:
    """
    Create the best available media backend for this platform.

    Selection policy:
    - Windows: VLC (preferred) → Qt/WMF (with warning)
    - macOS: Qt/AVFoundation (stable, native)
    - Linux: Qt/GStreamer (stable with system codecs) → VLC (fallback)

    Args:
        warn_on_wmf_fallback: Show warning dialog if forced to use WMF on Windows

    Returns:
        MediaBackend instance
    """
    platform = sys.platform
    vlc_available = _is_vlc_available()

    logger.info(f"Selecting media backend for platform: {platform}")
    logger.debug(f"VLC available: {vlc_available}")

    # Windows: prefer VLC to avoid WMF deadlocks
    if platform == 'win32':
        if vlc_available:
            from services.media.vlc_backend import VlcBackendAdapter
            backend = VlcBackendAdapter()
            version = backend.get_backend_version() or "unknown"
            logger.info(f"Selected VLC backend (version: {version})")
            return backend
        else:
            # Fallback to Qt/WMF with warning
            logger.warning("VLC not available on Windows - falling back to Qt/WMF")
            logger.warning("This may cause UI freezes. Install python-vlc for best results.")

            if warn_on_wmf_fallback:
                _warn_wmf_fallback()

            backend = QtBackendAdapter()
            logger.info(f"Selected Qt backend (WMF) - {backend.get_backend_name()}")
            return backend

    # macOS: use Qt/AVFoundation (native, stable)
    elif platform == 'darwin':
        backend = QtBackendAdapter()
        logger.info(f"Selected Qt backend (AVFoundation) - {backend.get_backend_name()}")
        return backend

    # Linux: prefer Qt/GStreamer, fallback to VLC
    elif platform.startswith('linux'):
        # Try Qt first (uses GStreamer if codecs installed)
        backend = QtBackendAdapter()
        backend_name = backend.get_backend_name()

        # Check if it's GStreamer
        if 'GStreamer' in backend_name:
            logger.info(f"Selected Qt backend (GStreamer) - {backend_name}")
            return backend

        # If VLC available, prefer it over Qt/unknown
        if vlc_available:
            logger.info("Qt backend not using GStreamer, switching to VLC")
            from services.media.vlc_backend import VlcBackendAdapter
            backend = VlcBackendAdapter()
            version = backend.get_backend_version() or "unknown"
            logger.info(f"Selected VLC backend (version: {version})")
            return backend

        # Fallback to Qt anyway
        logger.warning(f"Using Qt backend without GStreamer: {backend_name}")
        logger.info(f"Selected Qt backend - {backend_name}")
        return backend

    # Unknown platform: try Qt
    else:
        logger.warning(f"Unknown platform '{platform}' - using Qt backend")
        backend = QtBackendAdapter()
        logger.info(f"Selected Qt backend - {backend.get_backend_name()}")
        return backend


def get_backend_info() -> dict[str, str]:
    """
    Get information about available backends without creating instances.

    Returns:
        Dict with 'platform', 'vlc_available', 'recommended' keys
    """
    platform = sys.platform
    vlc_available = _is_vlc_available()

    # Determine recommended backend
    if platform == 'win32':
        recommended = 'VLC' if vlc_available else 'Qt/WMF (not recommended)'
    elif platform == 'darwin':
        recommended = 'Qt/AVFoundation'
    elif platform.startswith('linux'):
        recommended = 'Qt/GStreamer' if not vlc_available else 'Qt/GStreamer or VLC'
    else:
        recommended = 'Qt (unknown)'

    return {
        'platform': platform,
        'vlc_available': str(vlc_available),
        'recommended': recommended
    }
