"""
VLC Runtime Setup Helper for Developers

Downloads and extracts VLC portable runtime for Windows development.
Bundled builds include VLC automatically via PyInstaller.

Usage:
    python scripts/setup_vlc_runtime.py
"""

import sys
import urllib.request
import os
import platform
from pathlib import Path

VLC_VERSION = "3.0.21"
VLC_DOWNLOAD_URL = f"https://download.videolan.org/pub/videolan/vlc/{VLC_VERSION}/win64/vlc-{VLC_VERSION}-win64.7z"
VLC_RUNTIME_DIR = Path(__file__).parent.parent / "vlc_runtime"


def download_file(url: str, dest: Path, show_progress: bool = True):
    """Download file with progress bar."""
    def progress_hook(block_num, block_size, total_size):
        if not show_progress or total_size <= 0:
            return
        downloaded = block_num * block_size
        percent = min(100, (downloaded / total_size) * 100)
        bar_length = 40
        filled = int(bar_length * downloaded / total_size)
        bar = '█' * filled + '░' * (bar_length - filled)
        mb_downloaded = downloaded / (1024 * 1024)
        mb_total = total_size / (1024 * 1024)
        print(f'\r[{bar}] {percent:.1f}% ({mb_downloaded:.1f}/{mb_total:.1f} MB)', end='', flush=True)

    print(f"Downloading: {url}")
    urllib.request.urlretrieve(url, dest, reporthook=progress_hook)
    print()  # New line after progress


def extract_7z(archive_path: Path, dest_dir: Path):
    """Extract 7z archive using Python's shutil or 7z command."""
    try:
        import py7zr
        print(f"Extracting with py7zr...")
        with py7zr.SevenZipFile(archive_path, mode='r') as archive:
            archive.extractall(path=dest_dir)
        print(f"Extracted to: {dest_dir}")
        return True
    except ImportError:
        pass

    # Try system 7z command
    import subprocess
    seven_z_cmd = None

    # Check common 7z locations
    possible_paths = [
        r"C:\Program Files\7-Zip\7z.exe",
        r"C:\Program Files (x86)\7-Zip\7z.exe",
        "7z",  # In PATH
    ]

    for path in possible_paths:
        try:
            result = subprocess.run([path, "--help"], capture_output=True, timeout=5)
            if result.returncode == 0:
                seven_z_cmd = path
                break
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue

    if seven_z_cmd:
        print(f"Extracting with 7-Zip...")
        subprocess.run([seven_z_cmd, "x", str(archive_path), f"-o{dest_dir}", "-y"], check=True)
        print(f"Extracted to: {dest_dir}")
        return True

    print("ERROR: No extraction tool found!")
    print("Please install one of:")
    print("  1. pip install py7zr")
    print("  2. Install 7-Zip from https://www.7-zip.org/")
    return False


def setup_vlc():
    """Download and extract VLC runtime."""
    if platform.system() != "Windows":
        print(f"VLC auto-download only needed on Windows for development.")
        print(f"On {platform.system()}, VLC will use system installation or Qt backend.")
        return True

    # Check if already exists
    vlc_dir = VLC_RUNTIME_DIR / f"vlc-{VLC_VERSION}"
    if vlc_dir.exists():
        print(f"✅ VLC runtime already exists: {vlc_dir}")
        print(f"   Delete this directory to re-download.")
        return True

    # Create runtime directory
    VLC_RUNTIME_DIR.mkdir(exist_ok=True)

    # Download
    archive_path = VLC_RUNTIME_DIR / f"vlc-{VLC_VERSION}-win64.7z"
    if not archive_path.exists():
        try:
            download_file(VLC_DOWNLOAD_URL, archive_path)
        except Exception as e:
            print(f"ERROR downloading VLC: {e}")
            return False
    else:
        print(f"Using cached archive: {archive_path}")

    # Extract
    try:
        if not extract_7z(archive_path, VLC_RUNTIME_DIR):
            return False
    except Exception as e:
        print(f"ERROR extracting VLC: {e}")
        return False

    # Cleanup archive
    try:
        archive_path.unlink()
        print(f"Cleaned up archive: {archive_path.name}")
    except Exception as e:
        print(f"Warning: Could not delete archive: {e}")

    print(f"\n✅ VLC runtime setup complete!")
    print(f"   Location: {vlc_dir}")
    print(f"   The app will auto-detect this on startup.")
    return True


if __name__ == "__main__":
    print("="*60)
    print("VLC Runtime Setup for Development")
    print("="*60)
    print()

    success = setup_vlc()

    print()
    print("="*60)
    if success:
        print("✅ Setup complete! Run 'run.bat start' to use the app.")
    else:
        print("❌ Setup failed. See errors above.")
        sys.exit(1)
    print("="*60)
