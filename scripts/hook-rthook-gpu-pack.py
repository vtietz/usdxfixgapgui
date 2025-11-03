"""
PyInstaller Runtime Hook for GPU Pack Support

This hook runs VERY EARLY during PyInstaller startup, BEFORE torch is imported.
It manipulates sys.path to prioritize GPU Pack over bundled torch if available.

This must be registered in the .spec file as a runtime_hook.
"""

import sys
import os
from pathlib import Path


def get_config_dir():
    """Get platform-specific config directory."""
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", ""), "USDXFixGap")
    elif sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "USDXFixGap"
    else:  # Linux
        xdg_config = os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))
        return Path(xdg_config) / "usdxfixgap"


def read_gpu_pack_path(config_file):
    """Read GPU Pack path from config file.

    Returns:
        Path object if GPU Pack is enabled and configured, None otherwise
    """
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            config_text = f.read()
    except Exception:
        return None

    # Early exit: GPU disabled
    if "gpu_opt_in = false" in config_text.lower():
        return None

    # Find gpu_pack_path line
    for line in config_text.split("\n"):
        if not line.strip().startswith("gpu_pack_path"):
            continue

        parts = line.split("=", 1)
        if len(parts) != 2:
            continue

        pack_path = parts[1].strip().strip('"').strip("'")
        if not pack_path:
            continue

        return Path(pack_path)

    return None


def add_dll_directory(lib_dir):
    """Add DLL directory using platform-specific method.

    Args:
        lib_dir: Path to library directory
    """
    if sys.platform == "win32" and hasattr(os, "add_dll_directory"):
        try:
            os.add_dll_directory(str(lib_dir))
        except Exception:
            pass  # Best effort - don't break startup

    elif sys.platform in ("linux", "linux2"):
        ld_path = os.environ.get("LD_LIBRARY_PATH", "")
        new_ld_path = f"{lib_dir}:{ld_path}" if ld_path else str(lib_dir)
        os.environ["LD_LIBRARY_PATH"] = new_ld_path

    elif sys.platform == "darwin":
        dyld_path = os.environ.get("DYLD_LIBRARY_PATH", "")
        new_dyld_path = f"{lib_dir}:{dyld_path}" if dyld_path else str(lib_dir)
        os.environ["DYLD_LIBRARY_PATH"] = new_dyld_path


def reorder_syspath_for_gpu_pack(pack_dir):
    """Reorder sys.path to prioritize GPU Pack over bundled PyTorch.

    Args:
        pack_dir: Path to GPU Pack root directory
    """
    # Add GPU Pack to start of sys.path
    pack_dir_str = str(pack_dir)
    if pack_dir_str not in sys.path:
        sys.path.insert(0, pack_dir_str)

    # Move _MEIPASS directory (not derived paths like base_library.zip) to end
    # This ensures GPU Pack loads before bundled torch, but stdlib still works
    meipass = sys._MEIPASS
    if meipass in sys.path:
        sys.path.remove(meipass)
        sys.path.append(meipass)


def setup_gpu_pack():
    """Main setup function - called only in frozen mode."""
    # Early exit: not frozen
    if not hasattr(sys, "_MEIPASS"):
        return

    # Get config directory
    config_dir = get_config_dir()
    config_file = config_dir / "config.ini"

    # Early exit: config doesn't exist
    if not config_file.exists():
        return

    # Read GPU Pack path from config
    pack_dir = read_gpu_pack_path(config_file)
    if not pack_dir:
        return

    # Early exit: pack directory or torch subdirectory missing
    if not pack_dir.exists():
        return
    if not (pack_dir / "torch").exists():
        return

    # Setup sys.path to prioritize GPU Pack
    reorder_syspath_for_gpu_pack(pack_dir)

    # Add library directory for DLLs
    lib_dir = pack_dir / "torch" / "lib"
    if lib_dir.exists():
        add_dll_directory(lib_dir)


# Execute setup
setup_gpu_pack()
