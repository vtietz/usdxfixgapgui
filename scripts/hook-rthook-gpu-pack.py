"""
PyInstaller Runtime Hook for GPU Pack Support (Hybrid CPU/GPU Runtime)

This hook runs VERY EARLY during PyInstaller startup, BEFORE torch is imported.

Architecture:
- CPU torch/torchaudio bundled in EXE (works out-of-the-box for all users)
- Optional GPU Pack: when present and enabled, intercepts torch/torchaudio imports
  and redirects to external GPU Pack using a MetaPathFinder (beats FrozenImporter)

Portable Mode (Strict):
- Portable build: one-folder with _internal/ subdirectory
- In portable mode: uses app directory for config/GPU Pack (not user profile)
- Keeps portable build self-contained and predictable
- Override: USDXFIXGAP_GPU_PACK_DIR env var for explicit external pack path

This must be registered in the .spec file as a runtime_hook.
"""

import sys
import os
from pathlib import Path
import importlib.util
import importlib.machinery


def is_portable_mode():
    """Detect if running in portable mode (one-folder build).

    Portable detection: app has _internal/ subdirectory next to executable.
    This is minimal detection without importing project code.

    Returns:
        True if portable mode detected, False otherwise
    """
    if not hasattr(sys, "_MEIPASS"):
        return False  # Not frozen

    try:
        app_dir = Path(sys.executable).parent
        internal_dir = app_dir / "_internal"
        return internal_dir.is_dir()
    except Exception:
        return False


def get_config_dir():
    """Get config directory (portable-aware).

    In portable mode: returns app directory (next to executable)
    In regular mode: returns platform-specific user profile directory
    Override: Honors USDXFIXGAP_DATA_DIR env var if set
    """
    # Priority 1: Explicit override via env var
    data_dir_override = os.environ.get("USDXFIXGAP_DATA_DIR")
    if data_dir_override:
        return Path(data_dir_override)

    # Priority 2: Portable mode - use app directory
    if is_portable_mode():
        try:
            return Path(sys.executable).parent
        except Exception:
            pass  # Fall through to default

    # Priority 3: Platform-specific user profile directories
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", ""), "USDXFixGap")
    elif sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "USDXFixGap"
    else:  # Linux
        xdg_config = os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))
        return Path(xdg_config) / "usdxfixgap"


def find_gpu_pack_in_default_location():
    """Auto-discover GPU Pack in default location (portable-aware).

    Portable mode: Looks in <app_dir>/gpu_runtime/ only
    Regular mode: Looks in <config_dir>/gpu_runtime/ (user profile)

    Searches for any subfolder containing torch/ directory.
    Prefers packs matching CUDA flavor (cu124 > cu121 > others) and newer versions.

    Only works in frozen (EXE) mode - prevents test pollution in development.

    Returns:
        Path to GPU Pack if found, None otherwise
    """
    # Only auto-discover in frozen mode (prevents finding test artifacts)
    if not hasattr(sys, "_MEIPASS"):
        return None

    config_dir = get_config_dir()
    gpu_runtime_dir = config_dir / "gpu_runtime"

    if not gpu_runtime_dir.exists():
        return None

    # Collect all valid GPU Packs (any subfolder with torch/)
    candidates = []
    try:
        for entry in gpu_runtime_dir.iterdir():
            if entry.is_dir() and (entry / "torch").exists():
                candidates.append(entry)
    except Exception:
        return None

    if not candidates:
        return None

    # Sort candidates: prefer cu124 > cu121 > others, then by version descending
    # Expected format: v{version}-{flavor} (e.g., v2.0.0-cu121)
    def sort_key(path):
        name = path.name.lower()

        # Extract CUDA flavor (cu121, cu124, etc.)
        flavor_priority = 0
        if "cu124" in name:
            flavor_priority = 3
        elif "cu121" in name:
            flavor_priority = 2
        elif "cu" in name:  # Other CUDA flavors
            flavor_priority = 1
        # CPU-only packs get priority 0

        # Extract version for secondary sort (use lexicographic on name)
        # This handles v2.0.0 > v1.4.0 naturally
        return (flavor_priority, name)

    candidates.sort(key=sort_key, reverse=True)
    return candidates[0]


def read_gpu_pack_path(config_file):
    """Read GPU Pack path from config, environment, or auto-discover.

    Priority:
    1. USDXFIXGAP_GPU_PACK_DIR environment variable (for testing/advanced users)
    2. config.ini gpu_pack_path setting (explicit user configuration)
    3. Auto-discovery in <config_dir>/gpu_runtime/ (convenience, no config needed)

    Returns:
        Path object if GPU Pack is enabled and found, None otherwise
    """
    # Priority 1: Environment variable
    env_pack_dir = os.environ.get("USDXFIXGAP_GPU_PACK_DIR")
    if env_pack_dir:
        pack_path = Path(env_pack_dir)
        if pack_path.exists() and (pack_path / "torch").exists():
            return pack_path

    # Priority 2: Config file
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            config_text = f.read()
    except Exception:
        config_text = ""

    # Early exit: GPU explicitly disabled
    if config_text and "gpu_opt_in = false" in config_text.lower():
        return None

    # Check for explicit path in config
    if config_text:
        for line in config_text.split("\n"):
            if not line.strip().startswith("gpu_pack_path"):
                continue

            parts = line.split("=", 1)
            if len(parts) != 2:
                continue

            pack_path_str = parts[1].strip().strip('"').strip("'")
            if pack_path_str:
                path_obj = Path(pack_path_str)
                if path_obj.exists() and (path_obj / "torch").exists():
                    return path_obj

    # Priority 3: Auto-discovery (convenience - no config editing needed)
    return find_gpu_pack_in_default_location()


def add_dll_directory(lib_dir):
    """Add DLL directory using platform-specific method.

    Args:
        lib_dir: Path to library directory
    """
    if sys.platform == "win32" and hasattr(os, "add_dll_directory"):
        try:
            os.add_dll_directory(str(lib_dir))

            # Also prepend to PATH for DLLs that aren't found via add_dll_directory
            current_path = os.environ.get("PATH", "")
            lib_dir_str = str(lib_dir)
            if lib_dir_str not in current_path:
                os.environ["PATH"] = f"{lib_dir_str}{os.pathsep}{current_path}"
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


class GPUPackImportFinder:
    """MetaPathFinder to redirect torch/torchaudio imports to GPU Pack.

    This finder beats PyInstaller's FrozenImporter by being inserted at
    sys.meta_path[0], ensuring GPU Pack modules are loaded instead of
    bundled CPU-only versions when GPU Pack is enabled.
    """

    def __init__(self, pack_dir, redirected_modules=None):
        """Initialize with GPU Pack directory.

        Args:
            pack_dir: Path to GPU Pack root directory
            redirected_modules: Set of module names to redirect (default: {"torch", "torchaudio"})
        """
        self.pack_dir = Path(pack_dir)
        self.redirected_modules = redirected_modules or {"torch", "torchaudio"}

    def find_spec(self, fullname, path, target=None):
        """Find module spec for torch/torchaudio from GPU Pack.

        Args:
            fullname: Full module name (e.g., 'torch', 'torch.nn')
            path: Module search path
            target: Module target (unused)

        Returns:
            ModuleSpec if found in GPU Pack, None otherwise
        """
        # Only intercept top-level torch/torchaudio imports
        top_module = fullname.split(".")[0]
        if top_module not in self.redirected_modules:
            return None

        # Use PathFinder with GPU Pack directory
        try:
            search_path = [str(self.pack_dir)]
            spec = importlib.machinery.PathFinder.find_spec(fullname, search_path)
            if spec is not None:
                return spec
        except Exception:
            pass

        # Not found in GPU Pack - let other finders handle it
        return None

    def invalidate_caches(self):
        """Invalidate import caches (required by import protocol)."""
        pass


def write_hook_diagnostics(pack_dir, finder_inserted, dll_added, path_modified):
    """Write runtime hook diagnostics to log file.

    Args:
        pack_dir: Path to GPU Pack directory
        finder_inserted: Whether MetaPathFinder was inserted
        dll_added: Whether DLL directory was added
        path_modified: Whether PATH was modified
    """
    try:
        config_dir = get_config_dir()
        log_file = config_dir / "hook_diagnostics.log"
        config_dir.mkdir(parents=True, exist_ok=True)

        with open(log_file, "w", encoding="utf-8") as f:
            f.write("=== GPU Pack Runtime Hook Diagnostics ===\n\n")
            f.write(f"Frozen mode (sys._MEIPASS): {hasattr(sys, '_MEIPASS')}\n")
            if hasattr(sys, "_MEIPASS"):
                f.write(f"_MEIPASS path: {sys._MEIPASS}\n")
            f.write(f"Portable mode: {is_portable_mode()}\n")
            f.write(f"Config directory: {config_dir}\n\n")

            f.write(f"Pack directory: {pack_dir}\n")
            f.write(f"Pack/torch exists: {(pack_dir / 'torch').exists()}\n")
            f.write(f"Pack/torchaudio exists: {(pack_dir / 'torchaudio').exists()}\n")
            f.write(f"Pack/torch/lib exists: {(pack_dir / 'torch' / 'lib').exists()}\n\n")

            f.write(f"MetaPathFinder inserted: {finder_inserted}\n")
            f.write(f"DLL directory added: {dll_added}\n")
            f.write(f"PATH modified: {path_modified}\n\n")

            f.write(f"sys.meta_path[0]: {sys.meta_path[0] if sys.meta_path else 'empty'}\n")
            f.write(f"sys.path[0]: {sys.path[0] if sys.path else 'empty'}\n\n")

            # Platform-specific ABI checks
            py_version = f"cp{sys.version_info.major}{sys.version_info.minor}"
            f.write(f"Platform: {sys.platform}\n")
            f.write(f"Python version: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro} ({py_version})\n")

            if sys.platform == "win32":
                torch_c = pack_dir / "torch" / f"_C.{py_version}-win_amd64.pyd"
                f.write(f"torch/_C.{py_version}-win_amd64.pyd exists: {torch_c.exists()}\n")
            elif sys.platform.startswith("linux"):
                f.write(f"torch/lib/libtorch_cpu.so exists: {(pack_dir / 'torch' / 'lib' / 'libtorch_cpu.so').exists()}\n")
                f.write(f"torch/lib/libc10.so exists: {(pack_dir / 'torch' / 'lib' / 'libc10.so').exists()}\n")
            elif sys.platform == "darwin":
                f.write(f"torch/lib/libtorch_cpu.dylib exists: {(pack_dir / 'torch' / 'lib' / 'libtorch_cpu.dylib').exists()}\n")
                f.write(f"torch/lib/libc10.dylib exists: {(pack_dir / 'torch' / 'lib' / 'libc10.dylib').exists()}\n")

        # Write simple status file for GUI startup logger
        status_file = config_dir / "gpu_pack_hook_status.txt"
        with open(status_file, "w", encoding="utf-8") as f:
            if finder_inserted:
                f.write(f"ACTIVE|{pack_dir}")
            else:
                f.write(f"FAILED|{pack_dir}")

    except Exception as e:
        # Don't break startup on diagnostic failure
        pass


def setup_gpu_pack():
    """Main setup function - called only in frozen mode.

    Sets up hybrid CPU/GPU runtime:
    - CPU torch/torchaudio bundled in EXE (default)
    - GPU Pack: when present, intercepts imports via MetaPathFinder
    """
    # Early exit: not frozen
    if not hasattr(sys, "_MEIPASS"):
        return

    # Early exit: force CPU mode (ignore GPU Pack even if present)
    if os.environ.get("USDXFIXGAP_FORCE_CPU", "").lower() in ("1", "true", "yes"):
        return

    # Get config directory
    config_dir = get_config_dir()
    config_file = config_dir / "config.ini"

    # Read GPU Pack path from config/env/default location
    # (returns None if GPU is disabled or pack not found)
    pack_dir = read_gpu_pack_path(config_file)
    if not pack_dir:
        return

    # Early exit: pack directory or torch subdirectory missing
    if not pack_dir.exists():
        return
    if not (pack_dir / "torch").exists():
        return

    # Validate torchaudio presence to avoid ABI mismatch
    # (If torchaudio missing, it falls back to bundled CPU version → crash)
    has_torchaudio = (pack_dir / "torchaudio").exists()

    # Validate ABI compatibility (platform-specific checks)
    abi_compatible = False

    # Detect Python version from bundled interpreter
    py_version = f"cp{sys.version_info.major}{sys.version_info.minor}"  # e.g., cp312

    if sys.platform == "win32":
        # Windows: Check for Python version-specific extension
        torch_c = pack_dir / "torch" / f"_C.{py_version}-win_amd64.pyd"
        abi_compatible = torch_c.exists()

    elif sys.platform.startswith("linux"):
        # Linux: Check for core shared libraries and Python extension
        torch_lib = pack_dir / "torch" / "lib"
        required_libs = [
            torch_lib / "libtorch_cpu.so",
            torch_lib / "libc10.so",
        ]
        # Python extension pattern: _C.cpython-312-x86_64-linux-gnu.so
        torch_extensions = list((pack_dir / "torch").glob(f"_C.cpython-{sys.version_info.major}{sys.version_info.minor}*.so"))
        abi_compatible = all(lib.exists() for lib in required_libs) and len(torch_extensions) > 0

    elif sys.platform == "darwin":
        # macOS: Check for dylibs and Python extension
        torch_lib = pack_dir / "torch" / "lib"
        required_libs = [
            torch_lib / "libtorch_cpu.dylib",
            torch_lib / "libc10.dylib",
        ]
        # Python extension pattern: _C.cpython-312-darwin.so
        torch_extensions = list((pack_dir / "torch").glob(f"_C.cpython-{sys.version_info.major}{sys.version_info.minor}*.so"))
        abi_compatible = all(lib.exists() for lib in required_libs) and len(torch_extensions) > 0

    if not abi_compatible:
        # ABI mismatch - skip GPU Pack and use bundled CPU torch
        write_hook_diagnostics(pack_dir, False, False, False)
        return

    # Conditionally redirect torchaudio based on presence
    # (torch is always redirected; torchaudio only if present in pack)
    redirected_modules = {"torch"}
    if has_torchaudio:
        redirected_modules.add("torchaudio")

    # Disable PyTorch compilation features that cause circular imports in frozen apps
    # This must be done BEFORE torch is imported to prevent einops/dynamo issues
    os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"  # macOS compatibility
    os.environ["TORCH_COMPILE_DISABLE"] = "1"  # Disable torch.compile
    os.environ["TORCHDYNAMO_DISABLE"] = "1"  # Disable dynamo (prevents circular import)

    # Create a stub torch._dynamo module to prevent circular import
    # einops tries to import torch._dynamo.allow_in_graph, which triggers circular import
    # We need to provide a fake module BEFORE einops tries to import it
    import types
    
    # Create fake torch._dynamo module with minimal API
    fake_dynamo = types.ModuleType('torch._dynamo')
    fake_dynamo.allow_in_graph = lambda *args, **kwargs: lambda fn: fn  # No-op decorator
    fake_dynamo.disable = lambda *args, **kwargs: lambda fn: fn  # No-op decorator
    
    # Pre-populate sys.modules to prevent real dynamo from loading
    sys.modules['torch._dynamo'] = fake_dynamo

    # Insert MetaPathFinder at index 0 to beat FrozenImporter
    finder = GPUPackImportFinder(pack_dir, redirected_modules)
    sys.meta_path.insert(0, finder)
    finder_inserted = True

    # Setup sys.path to prioritize GPU Pack (belt-and-suspenders with MetaPathFinder)
    reorder_syspath_for_gpu_pack(pack_dir)

    # Add library directory for DLLs
    dll_added = False
    path_modified = False
    lib_dir = pack_dir / "torch" / "lib"
    if lib_dir.exists():
        add_dll_directory(lib_dir)
        dll_added = True
        path_modified = True

    # Write diagnostics
    write_hook_diagnostics(pack_dir, finder_inserted, dll_added, path_modified)


# Execute setup
setup_gpu_pack()
