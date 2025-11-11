#!/usr/bin/env python3
"""Code quality analysis orchestrator.

Coordinates multiple analysis tools and provides unified reporting.

Modes:
- all: Analyze entire project
- changed: Analyze only git-modified files
- files: Analyze specific files

Usage:
    python scripts/analyze_code.py all
    python scripts/analyze_code.py changed
    python scripts/analyze_code.py files path/to/file.py

Or via module:
    python -m analyze.core all
"""
import sys
import subprocess
import argparse
from pathlib import Path
from typing import List

# Import from analyze module  # noqa: E402
from analyze import (
    analyze_complexity,
    analyze_style,
    analyze_formatting,
    analyze_types,
    analyze_file_length,
)  # noqa: E402
from analyze.utils import (  # noqa: E402
    parse_style_output,
    parse_complexity_output,
    parse_file_length_output,
    _calculate_file_priority_scores,
    print_top_priority_files,
    print_complexity_hotspots,
    print_file_level_summary,
)

# Project root - always go up from analyze/ module location
# scripts/analyze/core.py -> scripts/ -> project_root/
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Directories to exclude
EXCLUDE_PATTERNS = ["__pycache__", ".pytest_cache", ".venv", "venv", "build", "dist"]

# Platform-specific symbols
if sys.platform == "win32":
    SYMBOL_SUCCESS = "[OK]"
    SYMBOL_WARNING = "[!]"
    SYMBOL_INFO = "[i]"
    SYMBOL_REPORT = "[#]"
    SYMBOL_SEARCH = "[~]"
else:
    SYMBOL_SUCCESS = "✅"
    SYMBOL_WARNING = "⚠️ "
    SYMBOL_INFO = "💡"
    SYMBOL_REPORT = "📊"
    SYMBOL_SEARCH = "🔍"


def get_changed_files() -> List[str]:
    """Get list of changed Python files from git.

    Returns:
        List of changed Python file paths
    """
    try:
        # Get staged and unstaged changes
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"], cwd=PROJECT_ROOT, capture_output=True, text=True, check=True
        )

        # Get untracked files
        result_untracked = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )

        all_files = result.stdout.strip().split("\n") + result_untracked.stdout.strip().split("\n")

        # Filter for Python files only
        python_files = [
            f for f in all_files if f.endswith(".py") and f.strip() and not any(excl in f for excl in EXCLUDE_PATTERNS)
        ]

        return python_files
    except subprocess.CalledProcessError:
        print(f"{SYMBOL_WARNING} Warning: Not a git repository or git not available")
        return []


def analyze_links() -> int:
    """Run markdown link validation.

    Returns:
        Exit code (0 = success, 1 = failure)
    """
    print(f"\n{'=' * 80}")
    print(f"{SYMBOL_SEARCH} Markdown Link Validation")
    print(f"{'=' * 80}")

    # Import and run link checker
    check_links_script = PROJECT_ROOT / "scripts" / "check_links.py"
    if not check_links_script.exists():
        print(f"{SYMBOL_WARNING} Warning: scripts/check_links.py not found, skipping link check")
        return 0

    result = subprocess.run([sys.executable, str(check_links_script)], cwd=PROJECT_ROOT, capture_output=False)

    return result.returncode


def print_file_summary(complexity_output: str = "", style_output: str = "", length_output: str = ""):
    """Print summary of issues grouped by file with complexity details.

    Args:
        complexity_output: Lizard output
        style_output: flake8 output
        length_output: File length analysis output
    """
    # Parse outputs
    if complexity_output:
        complexity_issues, complexity_metrics = parse_complexity_output(complexity_output)
    else:
        complexity_issues, complexity_metrics = {}, []

    style_issues = parse_style_output(style_output) if style_output else {}
    length_issues = parse_file_length_output(length_output) if length_output else {}

    # Calculate combined priority scores for each file
    file_priority_scores = _calculate_file_priority_scores(
        complexity_metrics, complexity_issues, style_issues, length_issues
    )

    # Print TOP PRIORITY section first (combined view)
    if file_priority_scores:
        print_top_priority_files(file_priority_scores, complexity_metrics)

    # Print complexity hotspots (most important)
    if complexity_metrics:
        print_complexity_hotspots(complexity_metrics)

    # Print file-level summary (sorted by priority)
    print_file_level_summary(file_priority_scores)


def print_summary(results: dict, complexity_output: str = "", style_output: str = "", length_output: str = ""):
    """Print analysis summary.

    Args:
        results: Dict mapping check name to exit code
        complexity_output: Lizard output for file summary
        style_output: flake8 output for file summary
        length_output: File length output for file summary
    """
    # Print file summary first if we have output
    if complexity_output or style_output or length_output:
        print_file_summary(complexity_output, style_output, length_output)

    print(f"\n{'=' * 80}")
    print(f"{SYMBOL_REPORT} ANALYSIS SUMMARY")
    print(f"{'=' * 80}")

    check_names = {
        "Complexity": "complexity",
        "Style": "style",
        "Formatting": "formatting",
        "File Length": "length",
        "Types": "types",
        "Link Check": "links",
    }

    for name, key in check_names.items():
        if key in results:
            status = f"{SYMBOL_SUCCESS} PASS" if results[key] == 0 else f"{SYMBOL_WARNING} ISSUES"
            print(f"{name:<20}: {status}")

    print(f"{'=' * 80}")

    # Count failures
    failures = sum(1 for code in results.values() if code != 0)
    if failures > 0:
        print(f"{SYMBOL_WARNING} {failures} check(s) found issues")
    else:
        print(f"{SYMBOL_SUCCESS} All checks passed!")

    return failures


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Analyze code quality")
    parser.add_argument(
        "mode",
        choices=["all", "changed", "files"],
        nargs="?",
        default="changed",
        help="Analysis mode: all (entire project), changed (git diff), files (specific files)",
    )
    parser.add_argument("paths", nargs="*", help="File paths (only with 'files' mode)")

    args = parser.parse_args()

    # Determine files to analyze
    files_to_analyze = None
    if args.mode == "changed":
        files_to_analyze = get_changed_files()
        if not files_to_analyze:
            print("No changed files to analyze")
            sys.exit(0)
        print(f"{SYMBOL_SEARCH} Analyzing {len(files_to_analyze)} changed file(s):")
        for f in files_to_analyze:
            print(f"  - {f}")
    elif args.mode == "files":
        if not args.paths:
            print("Error: 'files' mode requires file paths")
            sys.exit(1)
        files_to_analyze = args.paths
        print(f"{SYMBOL_SEARCH} Analyzing {len(files_to_analyze)} specified file(s)")
    else:  # all
        print(f"{SYMBOL_SEARCH} Analyzing entire project")

    # Run analyses
    results = {}

    complexity_code, complexity_output = analyze_complexity(files_to_analyze)
    results["complexity"] = complexity_code

    style_code, style_output = analyze_style(files_to_analyze)
    results["style"] = style_code

    formatting_code, formatting_output = analyze_formatting(files_to_analyze)
    results["formatting"] = formatting_code

    length_code, length_output = analyze_file_length(files_to_analyze)
    results["length"] = length_code

    types_code, types_output = analyze_types(files_to_analyze)
    results["types"] = types_code

    # Link check (always runs on all files)
    links_code = analyze_links()
    results["links"] = links_code

    # Print summary
    failures = print_summary(results, complexity_output, style_output, length_output)

    sys.exit(1 if failures > 0 else 0)


if __name__ == "__main__":
    main()
