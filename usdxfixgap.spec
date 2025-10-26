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
    'resampy',
    
    # PyTorch & Demucs
    'torch',
    'torchaudio',
    'demucs',
    'julius',
    'einops',
    
    # Other dependencies
    'numpy',
    'scipy',
    'mutagen',
    'pytz',
    'chardet',
    
    # Worker threads
    'concurrent.futures',
    'queue',
]

# Data files to include
datas = [
    (str(assets_dir), 'assets'),
]

# Binaries to exclude (reduce size)
exclude_binaries = []

# Modules to exclude (dev/test dependencies)
exclude_modules = [
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
