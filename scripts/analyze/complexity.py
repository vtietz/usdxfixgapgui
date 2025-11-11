#!/usr/bin/env python3
"""Complexity analysis using Lizard.

Can be run standalone or imported by analyze_code.py orchestrator.

Usage:
    python scripts/analyze_complexity.py [files...]
    python scripts/analyze_complexity.py  # analyze all
"""
import sys
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple

# Project root - go up from scripts/analyze/ to project root
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Configuration
MAX_COMPLEXITY = 15  # CCN (Cyclomatic Complexity Number) threshold
MAX_NLOC = 100  # Max lines of code per function

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


def analyze_complexity(files: Optional[List[str]] = None) -> Tuple[int, str]:
    """Run Lizard complexity analysis.

    Args:
        files: Specific files to analyze, or None for all

    Returns:
        Tuple of (exit_code, output_text)
    """
    print(f"\n{'=' * 80}")
    print(f"{SYMBOL_SEARCH} Complexity Analysis (Lizard)")
    print(f"{'=' * 80}")

    cmd = [
        sys.executable,
        "-m",
        "lizard",
        "--CCN",
        str(MAX_COMPLEXITY),
        "--length",
        str(MAX_NLOC),
        "--warnings_only",
        "--exclude",
        "*/__pycache__/*",
        "--exclude",
        "*/.pytest_cache/*",
        "--exclude",
        "*/build/*",
        "--exclude",
        "*/dist/*",
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

        # Lizard returns 0 if no issues
        if "No thresholds exceeded" in output or result.returncode == 0:
            print(f"{SYMBOL_SUCCESS} No complexity issues found!")
            return 0, output
        else:
            print(f"{SYMBOL_WARNING} Found complexity issues (CCN > {MAX_COMPLEXITY} or NLOC > {MAX_NLOC})")
            return 1, output

    except subprocess.TimeoutExpired:
        print(f"{SYMBOL_WARNING} Lizard analysis timed out after 300 seconds")
        return 1, ""
    except FileNotFoundError:
        print(f"{SYMBOL_WARNING} Lizard not installed. Install with: pip install lizard")
        return 1, ""


def main():
    """Entry point for standalone execution."""
    files = sys.argv[1:] if len(sys.argv) > 1 else None
    exit_code, _ = analyze_complexity(files)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
