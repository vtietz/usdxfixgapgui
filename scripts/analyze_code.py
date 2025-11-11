#!/usr/bin/env python3
"""Code quality analysis entry point.

Thin wrapper that delegates to the analyze.core module.

Usage:
    python scripts/analyze_code.py all
    python scripts/analyze_code.py changed
    python scripts/analyze_code.py files path/to/file.py
"""
import sys
from pathlib import Path

# Add scripts directory to path to enable analyze module import
SCRIPTS_DIR = Path(__file__).parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from analyze.core import main as run_analysis  # noqa: E402


if __name__ == "__main__":
    run_analysis()
