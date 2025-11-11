#!/usr/bin/env python3
"""File length analysis for AI-friendly architecture.

Can be run standalone or imported by analyze_code.py orchestrator.

Usage:
    python scripts/analyze_file_length.py [files...]
    python scripts/analyze_file_length.py  # analyze all
"""
import sys
from pathlib import Path
from typing import List, Optional, Tuple

# Project root - go up from scripts/analyze/ to project root
PROJECT_ROOT = Path(__file__).parent.parent.parent

# File length thresholds (for AI-friendly architecture)
FILE_LENGTH_WARN = 500  # Warning threshold
FILE_LENGTH_ERROR = 800  # Error threshold
FILE_LENGTH_FAIL = 1000  # Fail threshold

# Directories to analyze
PYTHON_DIRS = ["src", "tests", "scripts"]

# Directories to exclude
EXCLUDE_PATTERNS = ["__pycache__", ".pytest_cache", ".venv", "venv", "build", "dist"]

# Platform-specific symbols
if sys.platform == "win32":
    SYMBOL_SUCCESS = "[OK]"
    SYMBOL_WARNING = "[!]"
    SYMBOL_ERROR = "[X]"
    SYMBOL_INFO = "[i]"
    SYMBOL_SEARCH = "[~]"
else:
    SYMBOL_SUCCESS = "✅"
    SYMBOL_WARNING = "⚠️ "
    SYMBOL_ERROR = "❌"
    SYMBOL_INFO = "💡"
    SYMBOL_SEARCH = "🔍"


def _collect_python_files(files: Optional[List[str]] = None) -> List[Path]:
    """Collect Python files to analyze."""
    files_to_check = []
    if files:
        for f in files:
            if f.endswith(".py"):
                file_path = Path(f)
                if not file_path.is_absolute():
                    file_path = PROJECT_ROOT / file_path
                files_to_check.append(file_path)
    else:
        for dir_name in PYTHON_DIRS:
            dir_path = PROJECT_ROOT / dir_name
            if dir_path.exists():
                files_to_check.extend(dir_path.rglob("*.py"))

    files_to_check = [f for f in files_to_check if not any(excl in str(f) for excl in EXCLUDE_PATTERNS)]
    return files_to_check


def _count_file_lines(files_to_check: List[Path]) -> List[tuple]:
    """Count lines in each file."""
    file_lengths = []
    for file_path in files_to_check:
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                line_count = len(f.readlines())
            file_lengths.append((file_path, line_count))
        except Exception as e:
            print(f"{SYMBOL_WARNING} Warning: Could not read {file_path}: {e}")

    file_lengths.sort(key=lambda x: x[1], reverse=True)
    return file_lengths


def _categorize_file_lengths(file_lengths: List[tuple]) -> tuple:
    """Categorize files by line count thresholds."""
    fail_files = [(f, l) for f, l in file_lengths if l > FILE_LENGTH_FAIL]
    error_files = [(f, l) for f, l in file_lengths if FILE_LENGTH_ERROR < l <= FILE_LENGTH_FAIL]
    warn_files = [(f, l) for f, l in file_lengths if FILE_LENGTH_WARN < l <= FILE_LENGTH_ERROR]
    return fail_files, error_files, warn_files


def _print_file_length_issues(fail_files: List[tuple], error_files: List[tuple], warn_files: List[tuple]) -> List[str]:
    """Print categorized file length issues."""
    output_lines = []

    if fail_files:
        output_lines.append(f"\n{SYMBOL_ERROR} CRITICAL: Files exceeding {FILE_LENGTH_FAIL} lines (must be split):")
        for file_path, line_count in fail_files:
            rel_path = file_path.relative_to(PROJECT_ROOT)
            output_lines.append(f"  {rel_path}: {line_count} lines")
            print(f"  {SYMBOL_ERROR} {rel_path}: {line_count} lines (CRITICAL - split required)")

    if error_files:
        output_lines.append(f"\n{SYMBOL_WARNING} ERROR: Files exceeding {FILE_LENGTH_ERROR} lines (should be split):")
        for file_path, line_count in error_files:
            rel_path = file_path.relative_to(PROJECT_ROOT)
            output_lines.append(f"  {rel_path}: {line_count} lines")
            print(f"  {SYMBOL_WARNING} {rel_path}: {line_count} lines")

    if warn_files:
        output_lines.append(f"\n{SYMBOL_INFO} WARNING: Files exceeding {FILE_LENGTH_WARN} lines (consider splitting):")
        for file_path, line_count in warn_files:
            rel_path = file_path.relative_to(PROJECT_ROOT)
            output_lines.append(f"  {rel_path}: {line_count} lines")
            print(f"  {SYMBOL_INFO} {rel_path}: {line_count} lines")

    return output_lines


def _print_length_summary(fail_files: List[tuple], error_files: List[tuple], warn_files: List[tuple]) -> None:
    """Print summary of file length issues."""
    total_issues = len(fail_files) + len(error_files) + len(warn_files)
    if total_issues == 0:
        print(f"{SYMBOL_SUCCESS} All files under {FILE_LENGTH_WARN} lines (AI-friendly)")
    else:
        print("\nSummary:")
        print(f"  Critical (>{FILE_LENGTH_FAIL}): {len(fail_files)}")
        print(f"  Error (>{FILE_LENGTH_ERROR}): {len(error_files)}")
        print(f"  Warning (>{FILE_LENGTH_WARN}): {len(warn_files)}")
        print(f"\n{SYMBOL_INFO} Tip: Split large files into smaller modules for better AI assistance")


def analyze_file_length(files: Optional[List[str]] = None) -> Tuple[int, str]:
    """Check file length to ensure AI-friendly file sizes.

    Args:
        files: Specific files to analyze, or None for all

    Returns:
        Tuple of (exit_code, output_text)
    """
    print(f"\n{'=' * 80}")
    print(f"{SYMBOL_SEARCH} File Length Analysis")
    print(f"{'=' * 80}")

    files_to_check = _collect_python_files(files)

    if not files_to_check:
        print("No files to analyze")
        return 0, ""

    file_lengths = _count_file_lines(files_to_check)
    fail_files, error_files, warn_files = _categorize_file_lengths(file_lengths)
    output_lines = _print_file_length_issues(fail_files, error_files, warn_files)
    _print_length_summary(fail_files, error_files, warn_files)

    total_issues = len(fail_files) + len(error_files) + len(warn_files)
    if total_issues == 0:
        return 0, ""

    output = "\n".join(output_lines)

    # Fail only if we have critical files (>1000 lines)
    if fail_files:
        print(f"{SYMBOL_WARNING} Found {len(fail_files)} file(s) requiring immediate refactoring")
        return 1, output
    else:
        return 0, output


def main():
    """Entry point for standalone execution."""
    files = sys.argv[1:] if len(sys.argv) > 1 else None
    exit_code, _ = analyze_file_length(files)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
