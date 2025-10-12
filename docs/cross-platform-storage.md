# Cross-Platform Storage Strategy

## Current State

### Windows (✅ Implemented)
```
%LOCALAPPDATA%\USDXFixGap\
├── config.ini
├── cache.db
├── usdxfixgap.log
├── .tmp\
├── output\
├── samples\
├── models\
│   ├── demucs\
│   └── spleeter\
└── gpu_runtime\
```
**Path:** `C:\Users\<username>\AppData\Local\USDXFixGap\`

### Linux (⚠️ Partial)
**Current Implementation:**
- GPU Bootstrap: Uses `~/.local/share/USDXFixGap/`
- App Data: Falls back to app directory (not ideal)

**Should Be:**
```
~/.local/share/USDXFixGap/          # User data
├── config.ini
├── cache.db
├── usdxfixgap.log
├── .tmp/
├── output/
├── samples/
└── gpu_runtime/

~/.cache/USDXFixGap/                # Cache/models
└── models/
    ├── demucs/
    └── spleeter/
```
**Standards:**
- XDG Base Directory Specification
- `$XDG_DATA_HOME` (default: `~/.local/share/`)
- `$XDG_CACHE_HOME` (default: `~/.cache/`)
- `$XDG_CONFIG_HOME` (default: `~/.config/`)

### macOS (⚠️ Not Implemented)
**Should Be:**
```
~/Library/Application Support/USDXFixGap/    # User data
├── config.ini
├── usdxfixgap.log
├── .tmp/
├── output/
├── samples/
└── gpu_runtime/

~/Library/Caches/USDXFixGap/                  # Cache/models
└── models/
    ├── demucs/
    └── spleeter/
```
**Standards:**
- Apple File System Programming Guide
- Application Support for user data
- Caches for temporary/regenerable data

---

## Problem Analysis

### Current `get_localappdata_dir()`:
```python
def get_localappdata_dir():
    # Try standard Windows LOCALAPPDATA first
    local_app_data = os.getenv('LOCALAPPDATA')
    if local_app_data:
        app_data_dir = os.path.join(local_app_data, 'USDXFixGap')
        os.makedirs(app_data_dir, exist_ok=True)
        return app_data_dir
    
    # Fallback to app directory for portable mode
    logger.warning("LOCALAPPDATA not found, using app directory (portable mode)")
    return get_app_dir()
```

**Issues:**
1. ❌ Only checks `LOCALAPPDATA` (Windows-specific)
2. ❌ Falls back to app directory on Linux/macOS
3. ❌ Doesn't respect XDG standards on Linux
4. ❌ Doesn't use proper macOS paths

### Current `gpu_bootstrap.py`:
```python
def resolve_pack_dir(app_version: str, flavor: str = "cu121") -> Path:
    local_app_data = os.getenv('LOCALAPPDATA')
    if not local_app_data:
        # Fallback for non-Windows or missing env var
        local_app_data = os.path.expanduser('~/.local/share')
    
    pack_dir = Path(local_app_data) / 'USDXFixGap' / 'gpu_runtime' / f'v{app_version}-{flavor}'
    return pack_dir
```

**Better:** Already uses `~/.local/share/` on Linux/macOS (XDG compliant!)

---

## Recommended Solution

### Platform Detection Helper
```python
import sys
import os
from pathlib import Path

def get_platform():
    """Detect current platform."""
    if sys.platform == 'win32':
        return 'windows'
    elif sys.platform == 'darwin':
        return 'macos'
    else:
        return 'linux'
```

### Cross-Platform App Data Directory
```python
def get_app_data_dir():
    """
    Get platform-appropriate application data directory.
    
    Returns:
        Windows: %LOCALAPPDATA%/USDXFixGap/
        Linux:   ~/.local/share/USDXFixGap/ (XDG_DATA_HOME)
        macOS:   ~/Library/Application Support/USDXFixGap/
    """
    platform = get_platform()
    
    if platform == 'windows':
        local_app_data = os.getenv('LOCALAPPDATA')
        if local_app_data:
            return os.path.join(local_app_data, 'USDXFixGap')
    
    elif platform == 'macos':
        return os.path.expanduser('~/Library/Application Support/USDXFixGap')
    
    else:  # Linux and other Unix-like
        # Respect XDG_DATA_HOME if set
        xdg_data = os.getenv('XDG_DATA_HOME')
        if xdg_data:
            return os.path.join(xdg_data, 'USDXFixGap')
        return os.path.expanduser('~/.local/share/USDXFixGap')
    
    # Fallback to portable mode (current directory)
    logger.warning("Could not determine platform data directory, using portable mode")
    return get_app_dir()
```

### Cross-Platform Cache Directory
```python
def get_cache_dir():
    """
    Get platform-appropriate cache directory for models and temp data.
    
    Returns:
        Windows: %LOCALAPPDATA%/USDXFixGap/  (same as data)
        Linux:   ~/.cache/USDXFixGap/ (XDG_CACHE_HOME)
        macOS:   ~/Library/Caches/USDXFixGap/
    """
    platform = get_platform()
    
    if platform == 'windows':
        # Windows doesn't separate cache from data
        return get_app_data_dir()
    
    elif platform == 'macos':
        return os.path.expanduser('~/Library/Caches/USDXFixGap')
    
    else:  # Linux
        xdg_cache = os.getenv('XDG_CACHE_HOME')
        if xdg_cache:
            return os.path.join(xdg_cache, 'USDXFixGap')
        return os.path.expanduser('~/.cache/USDXFixGap')
```

### Updated File Organization
```python
def get_config_dir():
    """Get directory for config.ini"""
    # On all platforms, config goes in app data directory
    return get_app_data_dir()

def get_cache_db_dir():
    """Get directory for cache.db"""
    # On all platforms, cache database goes in app data directory
    return get_app_data_dir()

def get_log_dir():
    """Get directory for logs"""
    # On all platforms, logs go in app data directory
    return get_app_data_dir()

def get_models_dir(config=None):
    """Get directory for AI models"""
    if config and hasattr(config, 'models_directory') and config.models_directory:
        return os.path.expanduser(config.models_directory)
    
    # Use cache directory for models (regenerable data)
    cache_dir = get_cache_dir()
    return os.path.join(cache_dir, 'models')
```

---

## Migration Strategy

### Option 1: Immediate Full Implementation
**Pros:**
- Proper cross-platform support from the start
- Respects OS conventions
- Better separation of data types (data vs cache)

**Cons:**
- More complex implementation
- Need to test on all platforms
- Migration needed for existing users

### Option 2: Incremental Approach (Recommended)
1. **Phase 1 (Current):** Windows support with LOCALAPPDATA ✅
2. **Phase 2:** Add Linux XDG support (simple)
3. **Phase 3:** Add macOS Library support
4. **Phase 4:** Separate cache directory on Linux/macOS

---

## Proposed Implementation (Phase 2)

### Update `get_localappdata_dir()` → `get_app_data_dir()`:
```python
def get_app_data_dir():
    """
    Get platform-appropriate application data directory.
    
    Returns:
        str: Path to application data directory
        
    Platform paths:
        Windows: %LOCALAPPDATA%/USDXFixGap/
        Linux:   ~/.local/share/USDXFixGap/
        macOS:   ~/Library/Application Support/USDXFixGap/
        Portable: <app_directory>/
    """
    import sys
    
    # Windows
    if sys.platform == 'win32':
        local_app_data = os.getenv('LOCALAPPDATA')
        if local_app_data:
            app_data_dir = os.path.join(local_app_data, 'USDXFixGap')
            os.makedirs(app_data_dir, exist_ok=True)
            return app_data_dir
    
    # macOS
    elif sys.platform == 'darwin':
        app_support = os.path.expanduser('~/Library/Application Support/USDXFixGap')
        os.makedirs(app_support, exist_ok=True)
        return app_support
    
    # Linux and other Unix-like
    else:
        # Respect XDG_DATA_HOME if set, otherwise use default
        xdg_data = os.getenv('XDG_DATA_HOME')
        if xdg_data:
            app_data_dir = os.path.join(xdg_data, 'USDXFixGap')
        else:
            app_data_dir = os.path.expanduser('~/.local/share/USDXFixGap')
        os.makedirs(app_data_dir, exist_ok=True)
        return app_data_dir
    
    # Fallback to portable mode
    logger.warning("Could not determine platform data directory, using app directory (portable mode)")
    return get_app_dir()
```

### Keep Backward Compatibility:
```python
def get_localappdata_dir():
    """
    Deprecated: Use get_app_data_dir() instead.
    Kept for backward compatibility.
    """
    return get_app_data_dir()
```

---

## Testing Plan

### Windows (Already Working)
- [x] Config in %LOCALAPPDATA%\USDXFixGap\
- [x] Models download correctly
- [x] Cache database works
- [x] Tests pass

### Linux (To Test)
- [ ] Config in ~/.local/share/USDXFixGap/
- [ ] Models in ~/.local/share/USDXFixGap/models/ (or ~/.cache/USDXFixGap/models/)
- [ ] Respects XDG_DATA_HOME if set
- [ ] Portable mode fallback works

### macOS (To Test)
- [ ] Config in ~/Library/Application Support/USDXFixGap/
- [ ] Models in appropriate location
- [ ] Follows Apple guidelines
- [ ] App bundle integration

---

## Current Recommendation

**For Now (Your Current Development):**
1. Keep current Windows-focused implementation ✅
2. The fallback to `get_app_dir()` works for development on Linux/macOS
3. Document that full cross-platform support is coming

**For Production:**
1. Implement `get_app_data_dir()` with proper platform detection
2. Test on Linux VM or Docker container
3. Test on macOS if possible
4. Add platform-specific paths to documentation

**Quick Fix (10 minutes):**
Just update `get_localappdata_dir()` to handle Linux properly:
```python
# In get_localappdata_dir()
if not local_app_data:
    # Linux/macOS fallback
    if sys.platform != 'win32':
        return os.path.expanduser('~/.local/share/USDXFixGap')
    # Windows portable mode
    logger.warning("LOCALAPPDATA not found, using app directory (portable mode)")
    return get_app_dir()
```

---

## Summary

**Current Status:**
- ✅ Windows: Fully working with LOCALAPPDATA
- ⚠️ Linux/macOS: Falls back to app directory (not ideal but functional)

**Proper Cross-Platform Solution:**
- Windows: `%LOCALAPPDATA%\USDXFixGap\`
- Linux: `~/.local/share/USDXFixGap/` (XDG standard)
- macOS: `~/Library/Application Support/USDXFixGap/` (Apple standard)
- Portable: Current directory (any platform)

**Next Steps:**
1. Implement platform detection in `get_app_data_dir()`
2. Test on Linux (VM or WSL)
3. Optionally separate cache directory on Linux/macOS
4. Update documentation

Would you like me to implement the quick fix or the full cross-platform solution?
