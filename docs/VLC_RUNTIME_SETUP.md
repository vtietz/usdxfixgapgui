# VLC Runtime Bundling for Development

## Overview

For **development purposes**, you can bundle VLC runtime locally (similar to GPU Pack approach) instead of requiring system-wide VLC installation.

## Quick Setup (Recommended for Dev)

### Windows

1. **Download VLC Portable** (lightweight, no installer):
   ```
   https://get.videolan.org/vlc/3.0.21/win64/vlc-3.0.21-win64.7z
   ```

2. **Extract to project**:
   ```
   vlc_runtime/
     vlc-3.0.21/
       libvlc.dll
       libvlccore.dll
       plugins/
       ...
   ```

3. **Set environment variable** (temporary, for this session):
   ```cmd
   set VLC_PLUGIN_PATH=C:\Users\live\.coding\usdxfixgapgui\vlc_runtime\vlc-3.0.21\plugins
   ```

4. **Add DLL directory** at runtime (in code):
   ```python
   import os
   vlc_dir = Path(__file__).parent.parent.parent / "vlc_runtime" / "vlc-3.0.21"
   if vlc_dir.exists():
       os.add_dll_directory(str(vlc_dir))
   ```

### Alternative: System-Wide Install

Just install VLC normally:
- Download: https://www.videolan.org/vlc/download-windows.html
- python-vlc auto-detects system installation
- Simpler but requires every dev to install VLC

## Production Bundling

For **production builds** (PyInstaller), we'll need to:

1. **Bundle VLC DLLs** in the executable (like we do with Demucs models)
2. **Set VLC_PLUGIN_PATH** in runtime hook
3. **Add to PyInstaller spec**:
   ```python
   datas=[
       ('vlc_runtime/vlc-3.0.21/libvlc.dll', 'vlc'),
       ('vlc_runtime/vlc-3.0.21/libvlccore.dll', 'vlc'),
       ('vlc_runtime/vlc-3.0.21/plugins', 'vlc/plugins'),
   ]
   ```

## File Structure

```
usdxfixgapgui/
  vlc_runtime/           # Local VLC bundles (gitignored)
    vlc-3.0.21/
      libvlc.dll
      libvlccore.dll
      plugins/
  src/
    services/media/
      vlc_backend.py     # Uses local VLC if available
  requirements-build-windows.txt  # python-vlc package
```

## Advantages of Bundled Approach

✅ **Dev Experience**: No system-wide VLC installation required
✅ **Version Control**: Specific VLC version for consistency
✅ **Portable**: Works in CI/CD without system dependencies
✅ **Clean**: Doesn't pollute system PATH or Program Files
✅ **Matches GPU Pack Pattern**: Familiar architecture

## Implementation Plan

1. **Phase 1 (Current)**: Test with system VLC (quick validation)
2. **Phase 2**: Add local VLC runtime detection to `vlc_backend.py`
3. **Phase 3**: Bundle VLC in PyInstaller builds

## Next Steps

For immediate testing:
```cmd
# Option A: Install VLC system-wide (quick)
winget install VideoLAN.VLC

# Option B: Use portable VLC (cleaner, matches production)
# Download from https://get.videolan.org/vlc/3.0.21/win64/vlc-3.0.21-win64.7z
# Extract to vlc_runtime/vlc-3.0.21/
# Set VLC_PLUGIN_PATH environment variable
```

Then test:
```cmd
.\run.bat test-backend
```
