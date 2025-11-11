#!/usr/bin/env python3
"""Type checking using mypy.

Can be run standalone or imported by analyze_code.py orchestrator.

Usage:
    python scripts/analyze_types.py [files...]
    python scripts/analyze_types.py  # analyze all
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


def analyze_types(files: Optional[List[str]] = None) -> Tuple[int, str]:
    """Run mypy type checking.

    Args:
        files: Specific files to analyze, or None for all

    Returns:
        Tuple of (exit_code, output_text)
    """
    print(f"\n{'=' * 80}")
    print(f"{SYMBOL_SEARCH} Type Analysis (mypy - optional)")
    print(f"{'=' * 80}")

    # Check if mypy is available
    try:
        subprocess.run([sys.executable, "-m", "mypy", "--version"], capture_output=True, check=True)
    except subprocess.CalledProcessError:
        print(f"{SYMBOL_INFO} mypy not installed, skipping type analysis (optional)")
        print("   Install with: pip install mypy")
        return 0, ""

    cmd = [sys.executable, "-m", "mypy", "--ignore-missing-imports", "--no-error-summary"]

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
            print(f"{SYMBOL_SUCCESS} No type issues found!")
            return 0, output
        else:
            print(f"{SYMBOL_INFO} Found type issues (informational only)")
            return 0, output  # Don't fail on type issues (informational)

    except subprocess.TimeoutExpired:
        print(f"{SYMBOL_WARNING} mypy analysis timed out after 300 seconds")
        return 0, ""  # Don't fail on timeout


def main():
    """Entry point for standalone execution."""
    files = sys.argv[1:] if len(sys.argv) > 1 else None
    exit_code, _ = analyze_types(files)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
