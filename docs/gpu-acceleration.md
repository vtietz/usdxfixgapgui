# GPU Acceleration Guide

This document explains how to set up and use GPU acceleration in USDXFixGap for significantly faster vocal separation processing.

## Overview

USDXFixGap supports optional CUDA GPU acceleration for AI vocal separation, providing **5-10x faster processing** on compatible NVIDIA GPUs. The GPU Pack system keeps the base application small (~300MB) while allowing users with NVIDIA GPUs to optionally download CUDA-enabled PyTorch (~1GB) for accelerated processing.

## System Requirements

### **Automatic GPU Detection** (Recommended)

The application automatically detects your GPU and driver version:
- **NVIDIA GPU** with compatible driver installed
- **Driver ≥531.xx** for CUDA 12.1 support
- **Driver ≥550.xx** for CUDA 12.4 support (recommended)

> **No manual CUDA installation needed!** The GPU Pack includes everything required.

### **Performance Comparison**

| Processing Method | Hardware | Typical Time per Song |
|-------------------|----------|----------------------|
| MDX (CPU-only) | Intel i7/Ryzen 7 | 2-3 minutes |
| MDX (GPU) | RTX 3060/4060 | 10-30 seconds |
| MDX (GPU) | RTX 3080/4080 | 5-15 seconds |

---

## Quick Start

### **Option 1: Automatic Setup (Recommended)**

The easiest way to enable GPU acceleration:

1. **Launch the application** - it will detect your GPU automatically
2. **First detection** - if you have a compatible GPU, the app will:
   - Show a prompt offering to download the GPU Pack
   - Automatically select the correct CUDA version for your driver
   - Download and install the GPU Pack (~1GB)
3. **Enable acceleration** - check "Use GPU" in settings or use CLI flag
4. **Start processing** - gap detection will now use GPU acceleration

### **Option 2: Command-Line Setup**

For advanced users or automated deployment:

```bash
# Download and install GPU Pack automatically
usdxfixgap.exe --setup-gpu

# Install from offline ZIP file
usdxfixgap.exe --setup-gpu-zip "path\to\gpu-pack.zip"

# Enable GPU acceleration
usdxfixgap.exe --gpu-enable

# Check GPU status
usdxfixgap.exe --gpu-diagnostics
```

---

## GPU Pack Details

### **What is the GPU Pack?**

The GPU Pack is a separate download containing:
- **PyTorch with CUDA** (~800MB) - Deep learning framework with GPU support
- **CUDA Runtime Libraries** (~200MB) - NVIDIA CUDA toolkit components
- **Optimized Dependencies** - GPU-accelerated versions of audio processing libraries

### **Storage Location**

GPU Packs are installed to:
```
%LOCALAPPDATA%\USDXFixGap\gpu_runtime\v{version}-{flavor}\
```

Example:
```
C:\Users\YourName\AppData\Local\USDXFixGap\gpu_runtime\v1.0.0-cu124\
```

### **CUDA Flavors**

Two GPU Pack flavors are available, automatically selected based on your driver:

| Flavor | CUDA Version | Min Driver | Recommended For |
|--------|--------------|------------|-----------------|
| cu121 | 12.1 | ≥531.xx | Older drivers, RTX 20/30 series |
| cu124 | 12.4 | ≥550.xx | Latest drivers, RTX 40 series |

> **Automatic Selection**: The application chooses the best flavor for your driver. You can override this in `config.ini` if needed.

---

## Configuration

### **GUI Settings**

1. **Open Settings/Preferences**
2. **GPU Acceleration Section**:
   - ☑ **Enable GPU Acceleration** - Toggle GPU on/off
   - 📊 **GPU Status** - Shows current GPU and driver info
   - 📥 **Download GPU Pack** - Install CUDA support
   - 🔧 **CUDA Flavor** - Override automatic flavor selection (advanced)

### **config.ini Settings**

The GPU Pack adds these settings to `config.ini` under `[General]`:

```ini
[General]
# GPU acceleration (true/false)
GpuOptIn = false

# CUDA flavor (cu121 or cu124, or leave blank for auto-select)
GpuFlavor = cu121

# Installation details (managed by application)
GpuPackInstalledVersion = v1.0.0
GpuPackPath = C:\Users\...\AppData\Local\USDXFixGap\gpu_runtime\v1.0.0-cu121
GpuLastHealth = 2025-10-12T14:30:00Z
GpuLastError = 
```

### **Command-Line Flags**

```bash
# Download and install GPU Pack
--setup-gpu              

# Install from offline ZIP
--setup-gpu-zip "path\to\pack.zip"

# Enable GPU acceleration
--gpu-enable             

# Disable GPU acceleration
--gpu-disable            

# Show GPU diagnostics
--gpu-diagnostics        
```

---

## Troubleshooting

### **GPU Not Detected**

**Symptoms**: Application shows "No GPU detected" or falls back to CPU

**Solutions**:
1. **Update NVIDIA Drivers**:
   - Download latest drivers from [NVIDIA.com](https://www.nvidia.com/Download/index.aspx)
   - Requires driver ≥531.xx (cu121) or ≥550.xx (cu124)

2. **Check GPU Recognition**:
   ```bash
   # Run diagnostics
   usdxfixgap.exe --gpu-diagnostics
   
   # Check nvidia-smi
   nvidia-smi
   ```

3. **Verify GPU Pack Installation**:
   - Check `%LOCALAPPDATA%\USDXFixGap\gpu_runtime\` directory
   - Ensure `install.json` exists in the GPU Pack folder

### **CUDA Errors During Processing**

**Symptoms**: "CUDA out of memory" or "CUDA initialization failed"

**Solutions**:
1. **Reduce Batch Size** (in advanced settings):
   ```ini
   [mdx]
   chunk_duration_ms = 8000  # Reduce from 12000
   ```

2. **Close Other GPU Applications**:
   - Games, video editing software, or other AI tools
   - Check GPU usage: `nvidia-smi`

3. **Switch to CPU Mode Temporarily**:
   ```bash
   usdxfixgap.exe --gpu-disable
   ```

### **Slow Download or Installation**

**Solutions**:
1. **Use Resume Support**:
   - Download will resume automatically if interrupted
   - Look for `.part` files in the GPU Pack directory

2. **Offline Installation**:
   - Download GPU Pack ZIP from project releases
   - Install with: `usdxfixgap.exe --setup-gpu-zip "path\to\pack.zip"`

3. **Check Network Connection**:
   - GPU Pack is ~1GB download
   - Requires stable internet connection

### **GPU Pack Won't Install**

**Solutions**:
1. **Check Disk Space**:
   - GPU Pack requires ~2GB free space
   - Check `%LOCALAPPDATA%` drive

2. **Verify Permissions**:
   - Run as administrator if needed
   - Check write access to `%LOCALAPPDATA%\USDXFixGap\`

3. **Manual Cleanup**:
   ```bash
   # Remove partial installations
   rmdir /s "%LOCALAPPDATA%\USDXFixGap\gpu_runtime"
   
   # Retry installation
   usdxfixgap.exe --setup-gpu
   ```

---

## Advanced Topics

### **Custom GPU Pack Location**

You can override the default installation path in `config.ini`:

```ini
[General]
GpuPackPath = D:\CustomPath\gpu_runtime\v1.0.0-cu124
```

> **Warning**: Manual path changes may break automatic updates. Only recommended for advanced users.

### **Child Process GPU Support**

Background workers automatically inherit GPU Pack configuration via environment variable:

```bash
# Set by main process
USDXFIXGAP_GPU_PACK_DIR=C:\Users\...\gpu_runtime\v1.0.0-cu124

# Child processes check this and enable GPU automatically
```

### **Validation and Health Checks**

The application validates GPU Pack installations:

1. **On Startup**: Checks if GPU Pack path exists and is valid
2. **Before Processing**: Runs `torch.cuda.is_available()` check
3. **Smoke Test**: Performs GPU tensor multiplication to verify functionality

Failed health checks set `GpuLastError` in config and disable GPU temporarily.

### **Version Management**

GPU Packs are versioned to match application releases:
- **v1.0.0-cu121** - CUDA 12.1 for app version 1.0.0
- **v1.0.0-cu124** - CUDA 12.4 for app version 1.0.0

When upgrading the application:
- Old GPU Packs remain installed
- New versions are downloaded separately
- You can manually remove old versions to save disk space

---

## Technical Architecture

For developers and contributors, see implementation details:

### **Bootstrap Sequence**

```python
# 1. Application startup
config = Config()  # Load config.ini

# 2. GPU Pack bootstrap (before any torch import)
from utils import gpu_bootstrap
gpu_bootstrap.bootstrap_and_maybe_enable_gpu(config)
# This modifies sys.path and os.add_dll_directory() if GPU enabled

# 3. Provider imports (now use GPU-enabled torch if available)
from utils.providers import get_detection_provider
provider = get_detection_provider(config)  # Lazy-loaded, uses GPU if enabled
```

### **Key Implementation Files**

- **`src/utils/gpu_bootstrap.py`** - GPU detection, runtime activation, validation
- **`src/utils/gpu_manifest.py`** - Version management, flavor selection
- **`src/utils/gpu_downloader.py`** - Download with resume, SHA-256 verification
- **`src/common/config.py`** - GPU Pack configuration persistence
- **`src/utils/providers/factory.py`** - Lazy provider loading (prevents early torch import)

### **Provider Lazy Loading**

Providers are imported only when needed to prevent early torch import:

```python
# ❌ Old pattern (early import)
from utils.providers.mdx_provider import MdxProvider

# ✅ New pattern (lazy import)
def get_detection_provider(config):
    method = config.method.lower()
    if method == "mdx":
        from utils.providers.mdx_provider import MdxProvider  # Import here
        return MdxProvider(config)
```

This ensures GPU Pack bootstrap completes before torch is imported.

---

## FAQ

### **Do I need to install CUDA manually?**
No! The GPU Pack includes all required CUDA libraries. Just download the GPU Pack and enable GPU acceleration.

### **Will this work with AMD GPUs?**
Not currently. GPU acceleration requires NVIDIA CUDA-compatible GPUs. AMD ROCm support may be added in future releases.

### **Can I use GPU acceleration without downloading the pack?**
No. The base application is CPU-only to keep download size small. GPU support requires the separate GPU Pack download.

### **How much faster is GPU acceleration?**
Typically 5-10x faster than CPU processing. An RTX 3060 can process a song in 10-30 seconds vs. 2-3 minutes on CPU.

### **Does GPU acceleration affect accuracy?**
No. GPU and CPU produce identical results - GPU only affects processing speed, not detection quality.

### **Can I switch between GPU and CPU?**
Yes! Toggle GPU on/off in settings or use `--gpu-enable` / `--gpu-disable` CLI flags.

### **What happens if I upgrade my GPU driver?**
The application will detect the new driver and may recommend upgrading to a newer CUDA flavor (cu121 → cu124) for better performance.

### **How do I uninstall the GPU Pack?**
Simply delete the GPU Pack directory:
```
%LOCALAPPDATA%\USDXFixGap\gpu_runtime\
```
Then disable GPU in settings or use `--gpu-disable`.

---

## Support

For GPU-related issues:

1. **Run diagnostics**: `usdxfixgap.exe --gpu-diagnostics`
2. **Check GPU Pack installation**: `%LOCALAPPDATA%\USDXFixGap\gpu_runtime\`
3. **Review logs**: Look for GPU-related messages in application logs
4. **Report issues**: [GitHub Issues](https://github.com/vtietz/usdxfixgapgui/issues) with diagnostics output

---

**Last Updated**: October 12, 2025  
**GPU Pack Version**: v1.0.0 (cu121, cu124)
