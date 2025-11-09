# Portable Mode - Strict Self-Contained Architecture

**Status:** Implemented in v1.2.0  
**Applies to:** Runtime hook (`hook-rthook-gpu-pack.py`)

---

## Overview

Portable mode ensures that one-folder builds (`onedir`) are truly self-contained, using the application directory for all configuration and GPU Pack files instead of touching the user profile.

This enables:
- **USB stick deployments** - Run from any location without writing to user profile
- **Predictable behavior** - All paths relative to executable
- **Clean uninstall** - Delete folder to remove completely
- **Multi-instance** - Different versions can coexist without conflicts

---

## Detection

### Portable Build
- **Format:** Onedir (one-folder) with `_internal/` subdirectory
- **Detection:** `os.path.exists(os.path.join(app_dir, "_internal"))`
- **Example structure:**
  ```
  USDXFixGap/
  ├── usdxfixgap.exe
  ├── _internal/          ← Portable mode indicator
  │   ├── torch/
  │   ├── torchaudio/
  │   └── ...
  └── gpu_runtime/        ← GPU Pack location in portable mode
      └── torch-2.4.1-cu121/
  ```

### Regular Build
- **Format:** Onefile (single EXE) or installed application
- **Detection:** No `_internal/` directory
- **Behavior:** Uses platform-specific user profile directories

---

## Configuration Directory Behavior

### Priority System (applies to all modes)

1. **`USDXFIXGAP_DATA_DIR` env var** (highest priority)
   - Explicit override for power users
   - Overrides both portable and regular behavior
   - Example: `USDXFIXGAP_DATA_DIR=D:\CustomConfig`

2. **Portable mode detection**
   - If `_internal/` exists → use app directory
   - Returns: `<app_dir>` (directory containing executable)

3. **Platform-specific defaults** (regular mode)
   - Windows: `%LOCALAPPDATA%\USDXFixGap`
   - Linux: `~/.config/usdxfixgap` (or `$XDG_CONFIG_HOME/usdxfixgap`)
   - macOS: `~/Library/Application Support/USDXFixGap`

### Examples

#### Portable Mode (Windows)
```python
# App directory: C:\USDXFixGap\
# Config dir: C:\USDXFixGap\
# GPU Pack location: C:\USDXFixGap\gpu_runtime\torch-2.4.1-cu121\
```

#### Regular Mode (Windows)
```python
# App directory: C:\Program Files\USDXFixGap\
# Config dir: C:\Users\YourName\AppData\Local\USDXFixGap\
# GPU Pack location: C:\Users\YourName\AppData\Local\USDXFixGap\gpu_runtime\torch-2.4.1-cu121\
```

#### With USDXFIXGAP_DATA_DIR Override
```python
# Overrides portable/regular detection
set USDXFIXGAP_DATA_DIR=D:\MyCustomLocation
# Config dir: D:\MyCustomLocation\
# GPU Pack location: D:\MyCustomLocation\gpu_runtime\torch-2.4.1-cu121\
```

---

## GPU Pack Priority System

The runtime hook uses a **3-level priority system** for finding GPU Packs:

### 1. Environment Variable (Highest Priority)
- **`USDXFIXGAP_GPU_PACK_DIR`** - Explicit path to GPU Pack directory
- Use case: Testing, advanced users with custom locations
- Example: `set USDXFIXGAP_GPU_PACK_DIR=E:\GPUPacks\torch-2.4.1-cu121`
- Overrides all other detection methods

### 2. Config File (User Configuration)
- **File:** `<config_dir>/config.ini`
- **Setting:** `gpu_pack_path = /path/to/gpu/pack`
- Use case: User-configured persistent path
- Can be set via GUI Settings dialog

### 3. Auto-Discovery (Convenience)
- **Location:** `<config_dir>/gpu_runtime/`
- **Portable mode:** Searches `<app_dir>/gpu_runtime/`
- **Regular mode:** Searches `<user_profile>/USDXFixGap/gpu_runtime/`
- Use case: Extract GPU Pack and it "just works"
- Smart selection: Prefers cu124 > cu121 > others, newer versions first

---

## Portable Mode Implementation Details

### Hook Functions

#### `is_portable_mode()`
```python
def is_portable_mode():
    """Detect if running in portable mode (one-folder build)."""
    if not hasattr(sys, "_MEIPASS"):
        return False  # Not frozen
    
    try:
        app_dir = Path(sys.executable).parent
        internal_dir = app_dir / "_internal"
        return internal_dir.is_dir()
    except Exception:
        return False
```

#### `get_config_dir()`
```python
def get_config_dir():
    """Get config directory (portable-aware)."""
    # Priority 1: Explicit override
    data_dir_override = os.environ.get("USDXFIXGAP_DATA_DIR")
    if data_dir_override:
        return Path(data_dir_override)
    
    # Priority 2: Portable mode
    if is_portable_mode():
        return Path(sys.executable).parent
    
    # Priority 3: Platform defaults (user profile)
    # ... platform-specific logic
```

### Auto-Discovery in Portable Mode

When portable, `find_gpu_pack_in_default_location()` searches:
- `<app_dir>/gpu_runtime/` (NOT user profile)
- Selects best match using CUDA flavor priority
- CUDA flavor priority: cu124 (3) > cu121 (2) > other (1) > cpu (0)
- Lexicographic version sort (descending)

---

## Testing

### Test Coverage (`tests/test_runtime_hook.py`)

**New test class:** `TestPortableMode`

1. **`test_portable_mode_not_frozen`** - Returns False when not frozen
2. **`test_portable_mode_onedir_detected`** - Detects `_internal/` directory
3. **`test_portable_mode_onefile_not_detected`** - Onefile returns False
4. **`test_get_config_dir_portable_mode`** - Config dir = app dir in portable
5. **`test_get_config_dir_env_override_portable`** - `USDXFIXGAP_DATA_DIR` overrides portable
6. **`test_auto_discovery_portable_mode`** - Finds GPU Pack in `<app_dir>/gpu_runtime/`

**Environment cleanup:** `clean_gpu_env` autouse fixture clears both:
- `USDXFIXGAP_GPU_PACK_DIR`
- `USDXFIXGAP_DATA_DIR`

---

## User Documentation

### For End Users

#### Portable Deployment
1. Download `USDXFixGap-v1.2.0-windows-onedir.zip`
2. Extract to USB stick or any location (e.g., `E:\USDXFixGap\`)
3. (Optional) Extract GPU Pack to `E:\USDXFixGap\gpu_runtime\torch-2.4.1-cu121\`
4. Run `usdxfixgap.exe`
5. All config and cache files stay in `E:\USDXFixGap\`

#### Regular Deployment
1. Download `USDXFixGap-v1.2.0-windows-onefile.exe`
2. Run from any location
3. Config files go to `%LOCALAPPDATA%\USDXFixGap`
4. GPU Pack extracted to `%LOCALAPPDATA%\USDXFixGap\gpu_runtime\`

#### Advanced: Custom Data Location
```bash
# Override config directory (works in both modes)
set USDXFIXGAP_DATA_DIR=D:\MyCustomLocation
usdxfixgap.exe
```

### For Power Users

#### Explicit GPU Pack Path
```bash
# Point to specific GPU Pack (highest priority)
set USDXFIXGAP_GPU_PACK_DIR=E:\GPUPacks\torch-2.4.1-cu121
usdxfixgap.exe
```

#### Force CPU Mode
```bash
# Disable GPU Pack entirely
set USDXFIXGAP_FORCE_CPU=1
usdxfixgap.exe
```

---

## Migration Notes

### Existing Users (v1.1.x → v1.2.0)

**No action required** - existing GPU Packs in user profile continue to work:
- User profile GPU Packs: Still auto-discovered
- Config files: Still read from user profile
- Behavior: Unchanged for regular deployments

**New users** can now choose:
- **Portable:** Extract onedir build, GPU Pack stays with app
- **Regular:** Run onefile EXE, GPU Pack goes to user profile

---

## Diagnostics

### Hook Diagnostics Log

**Location:**
- Portable: `<app_dir>/hook_diagnostics.log`
- Regular: `<user_profile>/USDXFixGap/hook_diagnostics.log`

**New fields:**
```
Portable mode: True
Config directory: C:\USDXFixGap\
```

### Troubleshooting

**GPU Pack not activating in portable mode:**
1. Check `hook_diagnostics.log` → verify `Portable mode: True`
2. Verify GPU Pack location: `<app_dir>/gpu_runtime/torch-2.4.1-cu121/`
3. Check structure: `torch/`, `torchaudio/`, and `torch/lib/` must exist
4. Verify ABI match: `torch/_C.cpXXX-win_amd64.pyd` must match Python version

**Force specific location:**
```bash
# Override auto-discovery
set USDXFIXGAP_GPU_PACK_DIR=C:\USDXFixGap\gpu_runtime\torch-2.4.1-cu121
```

---

## Architecture Benefits

### Portable Mode Advantages
- ✅ **No registry writes** - No system changes
- ✅ **No user profile pollution** - Clean multi-user systems
- ✅ **Version isolation** - Multiple versions coexist
- ✅ **Clean uninstall** - Delete folder = complete removal
- ✅ **USB deployable** - Run from any drive

### Regular Mode Advantages
- ✅ **Single executable** - One file to distribute
- ✅ **Start menu integration** - System-wide install
- ✅ **Shared GPU Pack** - Multiple versions can share
- ✅ **User preferences** - Per-user configuration

---

## Implementation Notes

### Why Hook-Only Implementation?

The portable mode logic is **only in the runtime hook** (`hook-rthook-gpu-pack.py`), NOT in the app runtime (`src/utils/files.py`), because:

1. **Hook runs first** - Executes before app code, must be self-contained
2. **No project imports** - Can't import `src.utils.files` at hook stage
3. **Independent detection** - Simple `_internal/` check, no dependencies
4. **App already portable-aware** - `src/utils/files.py` already has `is_portable_mode()` and `get_localappdata_dir()` for app runtime

### Consistency Strategy

- **Hook**: Detects portable mode, routes config_dir to app_dir
- **App**: Uses `src/utils/files.get_localappdata_dir()` (already portable-aware)
- **Result**: Both hook and app use app directory in portable mode

No changes needed to `src/utils/files.py` - it already implements portable detection correctly.

---

## Related Documentation

- **Architecture:** `docs/architecture.md` - Overall app structure and DI
- **Configuration:** `docs/configuration.md` - Config file reference
- **Development:** `docs/DEVELOPMENT.md` - Build and test workflows

---

**Last Updated:** 2025-01-XX (v1.2.0)
