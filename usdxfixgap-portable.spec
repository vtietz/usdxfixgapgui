# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for USDXFixGap - PORTABLE DIRECTORY BUILD
Creates a directory with exe + dependencies (no extraction needed = instant startup)
"""
import os
from pathlib import Path

block_cipher = None

# Project paths
MAIN_SCRIPT = 'src/usdxfixgap.py'
ICON_PATH = 'src/assets/usdxfixgap-icon.ico'
if not os.path.exists(ICON_PATH):
    ICON_PATH = None

# Create Analysis
a = Analysis(
    [MAIN_SCRIPT],
    pathex=['.'],
    binaries=[],
    datas=[
        ('VERSION', '.'),
        ('src/assets', 'assets'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# PORTABLE BUILD: Separate exe and dependencies
exe = EXE(
    pyz,
    a.scripts,
    [],  # No binaries in exe - they go in COLLECT
    exclude_binaries=True,  # Important: put binaries in folder, not in exe
    name='usdxfixgap',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # No compression needed for directory build
    console=True,  # Console subsystem - enables CLI output capture, hidden in GUI mode
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON_PATH,
)

# COLLECT: Create directory structure
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='usdxfixgap-portable'
)
