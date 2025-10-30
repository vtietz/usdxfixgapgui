# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for USDXFixGap
Builds a single-file executable with all dependencies bundled.
"""
import sys
from pathlib import Path

# Project paths
project_root = Path('.').absolute()
src_dir = project_root / 'src'
assets_dir = src_dir / 'assets'

# Hidden imports (modules that PyInstaller can't auto-detect)
hidden_imports = [
    # PySide6 modules
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    'PySide6.QtMultimedia',
    'PySide6.QtMultimediaWidgets',

    # Audio processing
    'soundfile',
    'sounddevice',
    'librosa',
    'audioread',

    # PyTorch & Demucs
    'torch',
    'torchaudio',
    'demucs',
    'julius',
    'einops',

    # Other dependencies
    'numpy',
    'scipy',
    'chardet',

    # Image processing (for waveforms)
    'PIL',
    'PIL.Image',
    'PIL.ImageDraw',
    'PIL.ImageFont',

    # Worker threads
    'concurrent.futures',
    'queue',
]

# Data files to include
datas = [
    (str(assets_dir), 'assets'),
    (str(project_root / 'VERSION'), '.'),  # Include VERSION file at root
]

# Binaries to exclude (reduce size)
# Exclude CUDA libraries (users can download GPU Pack separately)
# Must cover all platforms: .dll (Windows), .so* (Linux), .dylib (macOS)
exclude_binaries = [
    # CUDA Core Libraries - c10, c10_cuda, etc.
    'c10_cuda', 'libc10_cuda',
    '_C_cuda', 'lib_C_cuda',
    # CUDA Deep Neural Network library
    'cudnn', 'libcudnn',
    # CUDA Basic Linear Algebra Subprograms
    'cublas', 'libcublas', 'cublasLt', 'libcublasLt',
    # CUDA Fast Fourier Transform
    'cufft', 'libcufft', 'cufftw', 'libcufftw',
    # CUDA Random Number Generation
    'curand', 'libcurand',
    # CUDA Solver library
    'cusolver', 'libcusolver', 'cusolverMg', 'libcusolverMg',
    # CUDA Sparse Matrix library
    'cusparse', 'libcusparse',
    # CUDA Runtime Compilation
    'nvrtc', 'libnvrtc', 'nvrtc-builtins',
    # CUDA Runtime
    'cudart', 'libcudart',
    # NVIDIA Tools Extension
    'nvToolsExt', 'libnvToolsExt',
    # Additional CUDA components
    'nvidia-', 'libnvidia-',
    # Triton (CUDA JIT compiler)
    'triton',
    # MKL (Intel Math Kernel Library) - can be large
    'mkl_', 'libmkl_',
]

# Modules to exclude (dev/test dependencies only)
# NOTE: Do NOT exclude torch submodules (torch.cuda, etc.) here!
# PyInstaller will skip torch entirely if it sees dependencies are excluded.
# Instead, exclude CUDA binaries via exclude_binaries below.
exclude_modules = [
    # Development tools
    'pytest',
    'pytest_qt',
    'pytest_mock',
    'lizard',
    'flake8',
    'mypy',
    'autoflake',
    'IPython',
    'jupyter',
    'notebook',
    'black',
    '_pytest',
    'py',
    'pluggy',

    # Unnecessary for our app
    'matplotlib',
    'tkinter',
]

block_cipher = None

a = Analysis(
    [str(src_dir / 'usdxfixgap.py')],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=exclude_modules,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Filter out excluded binaries to reduce size
# Use substring matching to catch all variants (.dll, .so, .so.*, .dylib)
a.binaries = TOC([
    x for x in a.binaries
    if not any(pattern in x[0].lower() for pattern in exclude_binaries)
])

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='usdxfixgap',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Windowed application (no console)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(assets_dir / 'usdxfixgap-icon.ico') if (assets_dir / 'usdxfixgap-icon.ico').exists() else None,
)
