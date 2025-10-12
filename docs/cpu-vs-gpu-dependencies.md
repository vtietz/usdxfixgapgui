# CPU vs GPU Dependencies Analysis

## Current Situation

Your conda environment currently has **CUDA-enabled PyTorch** installed:
- `torch 2.4.1+cu121` (CUDA 12.1)
- `torchaudio 2.4.1+cu121`
- `torchvision 0.19.1+cu121`

This happened because `pip install torch` defaults to CUDA version on Windows with NVIDIA GPU.

---

## Dependency Breakdown

### Spleeter (TensorFlow-based)
```
spleeter==2.4.0
├── tensorflow 2.9.3 (CPU version ✅)
├── ffmpeg-python
├── httpx
├── norbert
├── pandas
└── typer

Size: ~150 MB (TensorFlow)
GPU Support: Optional (TensorFlow-GPU not installed)
```

**Spleeter does NOT use PyTorch!** It's TensorFlow-based.

### Demucs (PyTorch-based)
```
demucs==4.0.1
├── torch (currently CUDA version ⚠️)
├── torchaudio (currently CUDA version ⚠️)
├── julius
└── openunmix

Size: ~2.3 GB (PyTorch CUDA) or ~150 MB (PyTorch CPU)
GPU Support: Requires PyTorch (CUDA or CPU)
```

**Demucs requires PyTorch!** It won't work without it.

---

## Bundle Size Impact

### Current Build (77 MB)
```
build/usdxfixgap/
├── usdxfixgap.exe         4.5 MB
├── base_library.zip      72 MB
└── (other files)          0.6 MB

Total: ~77 MB
```

**Why so small?**
- PyInstaller excludes heavy dependencies (torch/tensorflow) by default
- Models loaded dynamically at runtime from `pretrained_models/`
- No CUDA libraries bundled (users need local installation)

### If You Bundle PyTorch CUDA (~2.5+ GB)
```
build/usdxfixgap/
├── usdxfixgap.exe         4.5 MB
├── base_library.zip      72 MB
├── torch/cuda libs     ~2.3 GB (!!!!)
└── (other files)          0.6 MB

Total: ~2.4+ GB
```

**Not recommended** - executables become huge.

---

## Executable Behavior

### Without PyTorch/TensorFlow Bundled (Current)
✅ Small executable (~77 MB)
❌ Requires users to install Python + dependencies separately
❌ Won't work standalone

### With PyTorch/TensorFlow Bundled
✅ Works standalone (no Python installation needed)
❌ Huge executable size (2+ GB)
❌ Still needs pretrained models (~500 MB separate)

---

## Recommendations

### For Development: Clean CPU Environment

1. **Uninstall CUDA PyTorch:**
   ```bash
   .\uninstall_cuda.bat
   ```

2. **Install CPU-only PyTorch:**
   ```bash
   pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
   ```

3. **Update requirements.txt:**
   ```python
   # Add this line BEFORE torch/torchaudio:
   --extra-index-url https://download.pytorch.org/whl/cpu
   torch>=2.0.0
   torchaudio>=2.0.0
   ```

### For Distribution: Minimal Build

**Option A: Bundle Nothing (Current)**
- Users run via `run.bat` (conda environment)
- Small download size
- Requires Python/conda setup

**Option B: Bundle PySide6 Only**
- Bundle UI framework only
- Users install audio deps separately
- Medium download size (~300 MB)

**Option C: Bundle Everything**
- Standalone executable
- Huge download size (~2.5+ GB)
- Not recommended

---

## Size Comparison

| Package          | CPU Version | CUDA Version | Notes                    |
|------------------|-------------|--------------|--------------------------|
| PyTorch          | ~150 MB     | ~2.3 GB      | +2.15 GB for CUDA        |
| TensorFlow       | ~150 MB     | ~500 MB      | +350 MB for CUDA         |
| Spleeter models  | ~40 MB      | ~40 MB       | Same for both            |
| Demucs models    | ~350 MB     | ~350 MB      | Same for both            |
| PySide6          | ~80 MB      | ~80 MB       | Same for both            |

**Total Development Environment:**
- CPU-only: ~770 MB
- With CUDA: ~3.3 GB (+2.5 GB for CUDA)

---

## Your Questions Answered

### 1. Is requirements.txt clean for CPU support?
**No** - it installs CUDA PyTorch by default. Use `requirements-cpu.txt` instead.

### 2. What does Spleeter rely on?
**TensorFlow** (not PyTorch!). Already CPU-only in your environment. ✅

### 3. How does it work with the bundled executable?
**Not bundled** - PyInstaller excludes it. Users need local installation.

### 4. How big is the executable?
**77 MB** - because PyTorch/TensorFlow aren't bundled.

### 5. Would it work without torch/torchaudio?
- **Spleeter**: YES ✅ (uses TensorFlow)
- **Demucs**: NO ❌ (requires PyTorch)
- **MDX (current default)**: Depends on implementation

---

## Action Items

To clean your dev environment and ensure CPU-only:

1. **Run the cleanup script:**
   ```bash
   .\uninstall_cuda.bat
   ```

2. **Choose your installation:**
   ```bash
   # Option A: CPU-only PyTorch (keeps Demucs)
   pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
   
   # Option B: Remove PyTorch entirely (Spleeter only)
   pip uninstall -y demucs
   ```

3. **Update requirements.txt** to prevent future CUDA installs:
   - Use `requirements-cpu.txt` as template
   - Add `--extra-index-url https://download.pytorch.org/whl/cpu`

4. **Verify installation:**
   ```bash
   python -c "import torch; print('CUDA:', torch.cuda.is_available())"
   # Should print: CUDA: False
   ```
