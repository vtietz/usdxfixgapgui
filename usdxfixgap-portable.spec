# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for USDXFixGap - PORTABLE DIRECTORY BUILD
Creates a directory with exe + dependencies (no extraction needed = instant startup)
"""
import sys
from pathlib import Path

# Import configuration from main spec
spec_path = Path(__file__).parent / 'usdxfixgap.spec'
spec_globals = {}
with open(spec_path) as f:
    exec(f.read(), spec_globals)

# Reuse configuration from main spec
project_root = spec_globals['project_root']
src_dir = spec_globals['src_dir']
assets_dir = spec_globals['assets_dir']
hidden_imports = spec_globals['hidden_imports']
datas = spec_globals['datas']
exclude_binaries = spec_globals['exclude_binaries']
exclude_modules = spec_globals['exclude_modules']
block_cipher = spec_globals['block_cipher']

# Create Analysis
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

# Filter out excluded binaries
a.binaries = TOC([
    x for x in a.binaries
    if not any(pattern in x[0].lower() for pattern in exclude_binaries)
])

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
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(assets_dir / 'usdxfixgap-icon.ico') if (assets_dir / 'usdxfixgap-icon.ico').exists() else None,
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
