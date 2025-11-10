"""
PyInstaller hook for Demucs package.

Collects data files needed by Demucs:
- remote/files.txt: List of pretrained models
- remote/*.yaml: Model configurations
"""

from PyInstaller.utils.hooks import collect_data_files

# Collect all data files from demucs package
datas = collect_data_files('demucs', include_py_files=False)
