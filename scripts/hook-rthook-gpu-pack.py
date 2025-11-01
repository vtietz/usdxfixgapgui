"""
PyInstaller Runtime Hook for GPU Pack Support

This hook runs VERY EARLY during PyInstaller startup, BEFORE torch is imported.
It manipulates sys.path to prioritize GPU Pack over bundled torch if available.

This must be registered in the .spec file as a runtime_hook.
"""

import sys
import os
from pathlib import Path

# Only run in frozen (PyInstaller) mode
if hasattr(sys, "_MEIPASS"):
    # Check if GPU Pack is installed and user has it enabled
    # Cross-platform config directory detection
    if sys.platform == "win32":
        config_dir = Path(os.environ.get("LOCALAPPDATA", ""), "USDXFixGap")
    elif sys.platform == "darwin":
        config_dir = Path.home() / "Library" / "Application Support" / "USDXFixGap"
    else:  # Linux
        config_dir = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "usdxfixgap"

    gpu_pack_config_file = config_dir / "config.ini"

    if gpu_pack_config_file.exists():
        # Quick parse to check if GPU is enabled and pack exists
        try:
            with open(gpu_pack_config_file, "r", encoding="utf-8") as f:
                config_text = f.read()

            # Check if gpu_opt_in is not false
            if "gpu_opt_in = false" not in config_text.lower():
                # Look for gpu_pack_path
                for line in config_text.split("\n"):
                    if line.strip().startswith("gpu_pack_path"):
                        parts = line.split("=", 1)
                        if len(parts) == 2:
                            pack_path = parts[1].strip().strip('"').strip("'")
                            pack_dir = Path(pack_path)

                            if pack_dir.exists() and (pack_dir / "torch").exists():
                                # GPU Pack exists! Add to sys.path BEFORE _MEIPASS
                                # This ensures imports happen from GPU Pack, not bundled torch
                                if str(pack_dir) not in sys.path:
                                    sys.path.insert(0, str(pack_dir))

                                # Add DLL/library directory (platform-specific)
                                lib_dir = pack_dir / "torch" / "lib"
                                if lib_dir.exists():
                                    if sys.platform == "win32" and hasattr(os, "add_dll_directory"):
                                        # Windows: Use add_dll_directory
                                        try:
                                            os.add_dll_directory(str(lib_dir))
                                        except:
                                            pass  # Best effort
                                    elif sys.platform in ("linux", "linux2"):
                                        # Linux: Update LD_LIBRARY_PATH
                                        ld_path = os.environ.get("LD_LIBRARY_PATH", "")
                                        new_ld_path = f"{lib_dir}:{ld_path}" if ld_path else str(lib_dir)
                                        os.environ["LD_LIBRARY_PATH"] = new_ld_path
                                    elif sys.platform == "darwin":
                                        # macOS: Update DYLD_LIBRARY_PATH
                                        dyld_path = os.environ.get("DYLD_LIBRARY_PATH", "")
                                        new_dyld_path = f"{lib_dir}:{dyld_path}" if dyld_path else str(lib_dir)
                                        os.environ["DYLD_LIBRARY_PATH"] = new_dyld_path

                                # Remove _MEIPASS from sys.path to prevent bundled torch from loading
                                meipass = sys._MEIPASS
                                if meipass in sys.path:
                                    sys.path.remove(meipass)
                                # Re-add _MEIPASS at the END so other bundled modules still work
                                sys.path.append(meipass)

                            break
        except Exception:
            pass  # Silent fail - don't break startup if config read fails
