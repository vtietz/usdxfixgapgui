#!/usr/bin/env python3
"""Formatting check using Black.

Can be run standalone or imported by analyze_code.py orchestrator.

Usage:
    python scripts/analyze_formatting.py [files...]
    python scripts/analyze_formatting.py  # analyze all
"""
import sys
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple

# Project root - go up from scripts/analyze/ to project root
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Directories to analyze
PYTHON_DIRS = ["src", "tests", "scripts"]

# Directories to exclude
EXCLUDE_PATTERNS = ["__pycache__", ".pytest_cache", ".venv", "venv", "build", "dist"]

# Platform-specific symbols
if sys.platform == "win32":
    SYMBOL_SUCCESS = "[OK]"
    SYMBOL_WARNING = "[!]"
    SYMBOL_SEARCH = "[~]"
    SYMBOL_INFO = "[i]"
else:
    SYMBOL_SUCCESS = "✅"
    SYMBOL_WARNING = "⚠️ "
    SYMBOL_SEARCH = "🔍"
    SYMBOL_INFO = "💡"


def analyze_formatting(files: Optional[List[str]] = None) -> Tuple[int, str]:
    """Run Black formatting check.

    Args:
        files: Specific files to analyze, or None for all

    Returns:
        Tuple of (exit_code, output_text)
    """
    print(f"\n{'=' * 80}")
    print(f"{SYMBOL_SEARCH} Code Formatting (black)")
    print(f"{'=' * 80}")

    # Check if black is available
    try:
        subprocess.run([sys.executable, "-m", "black", "--version"], capture_output=True, check=True)
    except subprocess.CalledProcessError:
        print(f"{SYMBOL_WARNING} black not installed, skipping formatting analysis")
        print("   Install with: pip install black")
        return 0, ""

    cmd = [
        sys.executable,
        "-m",
        "black",
        "--check",
        "--diff",
        "--exclude",
        f"({'|'.join(EXCLUDE_PATTERNS)})",
    ]

    if files:
        cmd.extend(files)
    else:
        cmd.extend(PYTHON_DIRS)

    try:
        result = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=300)
        output = result.stdout + result.stderr

        if result.returncode == 0:
            print(f"{SYMBOL_SUCCESS} All files properly formatted!")
            return 0, output
        else:
            print(f"{SYMBOL_WARNING} Found formatting issues")
            print(f"{SYMBOL_INFO} Run 'python -m black src/ tests/ scripts/' to auto-fix")
            return 1, output

    except subprocess.TimeoutExpired:
        print(f"{SYMBOL_WARNING} Black formatting check timed out after 300 seconds")
        return 1, ""


def main():
    """Entry point for standalone execution."""
    files = sys.argv[1:] if len(sys.argv) > 1 else None
    exit_code, _ = analyze_formatting(files)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
