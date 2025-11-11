#!/usr/bin/env python3
"""Style analysis using flake8.

Can be run standalone or imported by analyze_code.py orchestrator.

Usage:
    python scripts/analyze_style.py [files...]
    python scripts/analyze_style.py  # analyze all
"""
import sys
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple

# Project root - go up from scripts/analyze/ to project root
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Configuration
MAX_LINE_LENGTH = 120  # Max line length (matches project style)

# Directories to analyze
PYTHON_DIRS = ["src", "tests", "scripts"]

# Directories to exclude
EXCLUDE_PATTERNS = ["__pycache__", ".pytest_cache", ".venv", "venv", "build", "dist"]

# Platform-specific symbols
if sys.platform == "win32":
    SYMBOL_SUCCESS = "[OK]"
    SYMBOL_WARNING = "[!]"
    SYMBOL_SEARCH = "[~]"
else:
    SYMBOL_SUCCESS = "✅"
    SYMBOL_WARNING = "⚠️ "
    SYMBOL_SEARCH = "🔍"


def analyze_style(files: Optional[List[str]] = None) -> Tuple[int, str]:
    """Run flake8 style analysis.

    Args:
        files: Specific files to analyze, or None for all

    Returns:
        Tuple of (exit_code, output_text)
    """
    print(f"\n{'=' * 80}")
    print(f"{SYMBOL_SEARCH} Style Analysis (flake8)")
    print(f"{'=' * 80}")

    # Check if flake8 is available
    try:
        subprocess.run([sys.executable, "-m", "flake8", "--version"], capture_output=True, check=True)
    except subprocess.CalledProcessError:
        print(f"{SYMBOL_WARNING} flake8 not installed, skipping style analysis")
        print("   Install with: pip install flake8")
        return 0, ""

    cmd = [
        sys.executable,
        "-m",
        "flake8",
        "--max-line-length",
        str(MAX_LINE_LENGTH),
        "--extend-ignore=E203,W503",
        "--exclude",
        ",".join(EXCLUDE_PATTERNS),
        "--statistics",
    ]

    if files:
        cmd.extend(files)
    else:
        cmd.extend(PYTHON_DIRS)

    try:
        result = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=300)
        output = result.stdout + result.stderr

        # Print output
        if output.strip():
            print(output)

        if result.returncode == 0:
            print(f"{SYMBOL_SUCCESS} No style issues found!")
            return 0, output
        else:
            print(f"{SYMBOL_WARNING} Found style issues")
            return 1, output

    except subprocess.TimeoutExpired:
        print(f"{SYMBOL_WARNING} flake8 analysis timed out after 300 seconds")
        return 1, ""


def main():
    """Entry point for standalone execution."""
    files = sys.argv[1:] if len(sys.argv) > 1 else None
    exit_code, _ = analyze_style(files)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
