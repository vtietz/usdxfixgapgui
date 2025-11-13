# -*- mode: python ; coding: utf-8 -*-

# PyInstaller spec that builds a single console=True executable.
#
# The executable works as both GUI and CLI:
#  - When run with CLI flags (--version, --health-check, etc): console stays visible, output captured
#  - When run without flags (GUI mode): console hides immediately via hide_console_window_on_gui_mode()
#
# Build format: ONEFILE (single executable in dist/)
#
# Usage:
#   pyinstaller usdxfixgap.spec
#
# Output:
#   dist/usdxfixgap.exe (single file, ~200-300 MB)
#
# Running:
#   GUI:  dist/usdxfixgap.exe
#   CLI:  dist/usdxfixgap.exe --health-check
#         dist/usdxfixgap.exe --version

block_cipher = None

import os
from pathlib import Path

# Project paths
scripts_dir = Path('.').absolute() / 'scripts'

# Path to main entry script
MAIN_SCRIPT = 'src/usdxfixgap.py'

# Optional icon path
ICON_PATH = 'src/assets/icon.ico'
if not os.path.exists(ICON_PATH):
    ICON_PATH = None

# Analysis
a = Analysis(
    [MAIN_SCRIPT],
    pathex=['.'],
    binaries=[],
    datas=[
        # Include VERSION file for --version command
        ('VERSION', '.'),
        # Include assets directory for GUI icons
        ('src/assets', 'assets'),
        # Include VLC runtime for audio backend (if present)
        ('vlc_runtime', 'vlc_runtime'),
    ],
    hiddenimports=[
        # PySide6 modules
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'PySide6.QtMultimedia',
        'PySide6.QtMultimediaWidgets',

        # VLC backend (optional but recommended)
        'vlc',

        # Audio processing
        'soundfile',
        'sounddevice',
        'librosa',
        'audioread',

        # PyTorch & Demucs
        'torch',
        'torchaudio',
        'demucs',
        'demucs.pretrained',
        'demucs.remote',
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
    ],
    hookspath=['hooks'],
    hooksconfig={},
    runtime_hooks=[str(scripts_dir / 'hook-rthook-gpu-pack.py')],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Single-file executable in dist/
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
    console=True,  # Console subsystem - enables CLI output capture, hidden in GUI mode
    icon=ICON_PATH,
)
