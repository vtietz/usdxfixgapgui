#!/usr/bin/env python3
"""Code quality analysis script.

Analyzes Python code for:
- Complexity (using Lizard)
- Style issues (using flake8)
- Type issues (using mypy - optional)

Modes:
- all: Analyze entire project
- changed: Analyze only git-modified files
- files: Analyze specific files

Usage:
    python scripts/analyze_code.py all
    python scripts/analyze_code.py changed
    python scripts/analyze_code.py files psm/gui/main_window.py psm/config.py
"""
import sys
import subprocess
import argparse
from pathlib import Path
from typing import List, Optional, Tuple
from collections import defaultdict

# Platform-specific symbols (Windows-safe ASCII)
if sys.platform == "win32":
    # Use ASCII-safe symbols for Windows console compatibility
    SYMBOL_SEARCH = "[~]"
    SYMBOL_SUCCESS = "[OK]"
    SYMBOL_WARNING = "[!]"
    SYMBOL_ERROR = "[X]"
    SYMBOL_INFO = "[i]"
    SYMBOL_REPORT = "[#]"
else:
    # Use emojis on Unix-like systems
    SYMBOL_SEARCH = "🔍"
    SYMBOL_SUCCESS = "✅"
    SYMBOL_WARNING = "⚠️ "
    SYMBOL_ERROR = "❌"
    SYMBOL_INFO = "💡"
    SYMBOL_REPORT = "📊"


# Configuration
MAX_COMPLEXITY = 15  # CCN (Cyclomatic Complexity Number) threshold
MAX_NLOC = 100  # Max lines of code per function
MAX_LINE_LENGTH = 120  # Max line length (matches project style)

# File length thresholds (for AI-friendly architecture)
FILE_LENGTH_WARN = 500  # Warning threshold
FILE_LENGTH_ERROR = 800  # Error threshold
FILE_LENGTH_FAIL = 1000  # Fail threshold

# Project root
PROJECT_ROOT = Path(__file__).parent.parent

# Directories to analyze
PYTHON_DIRS = [
    "src",
    "tests",
    "scripts",
]

# Directories to exclude
EXCLUDE_PATTERNS = [
    "__pycache__",
    ".pytest_cache",
    ".venv",
    "venv",
    "build",
    "dist",
]


def run_command(cmd: List[str], description: str) -> Tuple[int, str]:
    """Run a command and return exit code and output.

    Args:
        cmd: Command to run as list of strings
        description: Human-readable description

    Returns:
        Tuple of (exit_code, output)
    """
    print(f"\n{' = '*80}")
    print(f"{SYMBOL_SEARCH} {description}")
    print(f"{' = '*80}")

    try:
        result = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True, check=False)

        output = result.stdout + result.stderr
        print(output)

        return result.returncode, output
    except Exception as e:
        error_msg = f"{SYMBOL_ERROR} Error running {description}: {e}"
        print(error_msg)
        return 1, error_msg


def get_changed_files() -> List[str]:
    """Get list of modified Python files from git.

    Returns:
        List of file paths
    """
    try:
        # Get modified files (staged + unstaged)
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"], cwd=PROJECT_ROOT, capture_output=True, text=True, check=True
        )

        # Also get untracked files
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


def analyze_complexity(files: Optional[List[str]] = None) -> tuple:
    """Run Lizard complexity analysis.

    Args:
        files: Specific files to analyze, or None for all

    Returns:
        Tuple of (exit_code, output_text)
    """
    cmd = [
        sys.executable,
        "-m",
        "lizard",
        "--CCN",
        str(MAX_COMPLEXITY),  # Complexity threshold
        "--length",
        str(MAX_NLOC),  # Function length threshold
        "--warnings_only",  # Only show issues
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

    exit_code, output = run_command(cmd, "Complexity Analysis (Lizard)")

    # Lizard returns 0 if no issues, parse output for summary
    if "No thresholds exceeded" in output or exit_code == 0:
        print(f"{SYMBOL_SUCCESS} No complexity issues found!")
        return 0, output
    else:
        print(f"{SYMBOL_WARNING} Found complexity issues (CCN > {MAX_COMPLEXITY} or NLOC > {MAX_NLOC})")
        return 1, output


def analyze_style(files: Optional[List[str]] = None) -> tuple:
    """Run flake8 style analysis.

    Args:
        files: Specific files to analyze, or None for all

    Returns:
        Tuple of (exit_code, output_text)
    """
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
        "--exclude",
        "__pycache__,.pytest_cache,build,dist,.venv,venv",
        "--ignore",
        "E203,W503",  # Black-compatible ignores
        "--count",
        "--statistics",
    ]

    if files:
        cmd.extend(files)
    else:
        cmd.extend(PYTHON_DIRS)

    exit_code, output = run_command(cmd, "Style Analysis (flake8)")

    if exit_code == 0:
        print(f"{SYMBOL_SUCCESS} No style issues found!")
        return 0, output
    else:
        print(f"{SYMBOL_WARNING} Found style issues")
        return 1, output


def analyze_formatting(files: Optional[List[str]] = None) -> tuple:
    """Run Black code formatting check.

    Args:
        files: Specific files to analyze, or None for all

    Returns:
        Tuple of (exit_code, output_text)
    """
    # Check if Black is available
    try:
        subprocess.run([sys.executable, "-m", "black", "--version"], capture_output=True, check=True)
    except subprocess.CalledProcessError:
        print(f"{SYMBOL_WARNING} black not installed, skipping formatting check")
        print("   Install with: pip install black")
        return 0, ""

    cmd = [
        sys.executable,
        "-m",
        "black",
        "--check",
        "--diff",
    ]

    if files:
        cmd.extend(files)
    else:
        cmd.extend(PYTHON_DIRS)

    exit_code, output = run_command(cmd, "Code Formatting (black)")

    if exit_code == 0:
        print(f"{SYMBOL_SUCCESS} All files are properly formatted!")
        return 0, output
    else:
        print(f"{SYMBOL_WARNING} Found formatting issues")
        print(f"{SYMBOL_INFO} Run 'python -m black src/ tests/ scripts/' to auto-fix")
        return 1, output


def analyze_types(files: Optional[List[str]] = None) -> tuple:
    """Run mypy type checking (optional).

    Args:
        files: Specific files to analyze, or None for all

    Returns:
        Tuple of (exit_code, output_text)
    """
    # Check if mypy is available
    try:
        subprocess.run([sys.executable, "-m", "mypy", "--version"], capture_output=True, check=True)
    except subprocess.CalledProcessError:
        print(f"{SYMBOL_INFO} mypy not installed, skipping type analysis (optional)")
        return 0, ""

    cmd = [
        sys.executable,
        "-m",
        "mypy",
        "--ignore-missing-imports",
        "--no-strict-optional",
        "--check-untyped-defs",
    ]

    if files:
        cmd.extend(files)
    else:
        cmd.extend(PYTHON_DIRS)

    exit_code, output = run_command(cmd, "Type Analysis (mypy - optional)")

    if exit_code == 0:
        print(f"{SYMBOL_SUCCESS} No type issues found!")
        return 0, output
    else:
        print(f"{SYMBOL_INFO} Found type issues (informational only)")
        return 0, output  # Don't fail on type issues


def analyze_file_length(files: Optional[List[str]] = None) -> tuple:
    """Check file length to ensure AI-friendly file sizes.

    Args:
        files: Specific files to analyze, or None for all

    Returns:
        Tuple of (exit_code, output_text)
    """
    print(f"\n{'='*80}")
    print(f"{SYMBOL_SEARCH} File Length Analysis")
    print(f"{'='*80}")

    # Collect all Python files to analyze
    files_to_check = []
    if files:
        # Convert to absolute paths if relative
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

    # Filter out excluded patterns
    files_to_check = [f for f in files_to_check if not any(excl in str(f) for excl in EXCLUDE_PATTERNS)]

    if not files_to_check:
        print("No files to analyze")
        return 0, ""

    # Count lines in each file
    file_lengths = []
    for file_path in files_to_check:
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                line_count = len(f.readlines())
            file_lengths.append((file_path, line_count))
        except Exception as e:
            print(f"{SYMBOL_WARNING} Warning: Could not read {file_path}: {e}")

    # Sort by line count (descending)
    file_lengths.sort(key=lambda x: x[1], reverse=True)

    # Categorize files
    fail_files = [(f, l) for f, l in file_lengths if l > FILE_LENGTH_FAIL]
    error_files = [(f, l) for f, l in file_lengths if FILE_LENGTH_ERROR < l <= FILE_LENGTH_FAIL]
    warn_files = [(f, l) for f, l in file_lengths if FILE_LENGTH_WARN < l <= FILE_LENGTH_ERROR]

    # Build output
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

    # Print summary
    total_issues = len(fail_files) + len(error_files) + len(warn_files)
    if total_issues == 0:
        print(f"{SYMBOL_SUCCESS} All files under {FILE_LENGTH_WARN} lines (AI-friendly)")
        return 0, ""
    else:
        print("\nSummary:")
        print(f"  Critical (>{FILE_LENGTH_FAIL}): {len(fail_files)}")
        print(f"  Error (>{FILE_LENGTH_ERROR}): {len(error_files)}")
        print(f"  Warning (>{FILE_LENGTH_WARN}): {len(warn_files)}")
        print(f"\n{SYMBOL_INFO} Tip: Split large files into smaller modules for better AI assistance")

        output = "\n".join(output_lines)

        # Fail only if we have critical files (>1000 lines)
        if fail_files:
            print(f"{SYMBOL_WARNING} Found {len(fail_files)} file(s) requiring immediate refactoring")
            return 1, output
        else:
            return 0, output


def analyze_links() -> int:
    """Check all markdown links for validity.

    Returns:
        0 if all links valid, 1 otherwise
    """
    print(f"\n{'='*80}")
    print(f"{SYMBOL_SEARCH} Markdown Link Validation")
    print(f"{'='*80}\n")

    # Import and run link checker
    check_links_script = PROJECT_ROOT / "scripts" / "check_links.py"
    if not check_links_script.exists():
        print(f"{SYMBOL_WARNING} Warning: scripts/check_links.py not found, skipping link check")
        return 0

    result = subprocess.run(
        [sys.executable, str(check_links_script)], cwd=PROJECT_ROOT, capture_output=False  # Let it print directly
    )

    return result.returncode


def parse_style_output(output: str) -> dict:
    """Parse flake8 output to count issues per file.

    Args:
        output: flake8 output string

    Returns:
        Dict mapping file path to issue count
    """
    file_issues = defaultdict(int)

    for line in output.split("\n"):
        if ":" in line and len(line.split(":")) >= 3:
            # Format: path/to/file.py:line:col: CODE message
            filepath = line.split(":")[0]
            if filepath and filepath.endswith(".py"):
                file_issues[filepath] += 1

    return dict(file_issues)


def parse_complexity_output(output: str) -> dict:
    """Parse Lizard output to count issues per file.

    Args:
        output: Lizard output string

    Returns:
        Dict mapping file path to issue count
    """
    file_issues = defaultdict(int)

    for line in output.split("\n"):
        if "warning:" in line and ":" in line:
            # Format: path/to/file.py:line: warning: ...
            filepath = line.split(":")[0]
            if filepath and filepath.endswith(".py"):
                file_issues[filepath] += 1

    return dict(file_issues)


def parse_file_length_output(output: str) -> dict:
    """Parse file length output to count issues per file.

    Args:
        output: File length analysis output

    Returns:
        Dict mapping file path to issue count (1 per file)
    """
    file_issues = {}

    for line in output.split("\n"):
        if ".py:" in line and "lines" in line:
            # Extract file path
            parts = line.strip().split(":")
            if len(parts) >= 2:
                filepath = parts[0].strip()
                if filepath:
                    file_issues[filepath] = 1

    return file_issues


def print_file_summary(complexity_output: str = "", style_output: str = "", length_output: str = ""):
    """Print summary of issues grouped by file.

    Args:
        complexity_output: Lizard output
        style_output: flake8 output
        length_output: File length analysis output
    """

    # Parse outputs
    complexity_issues = parse_complexity_output(complexity_output) if complexity_output else {}
    style_issues = parse_style_output(style_output) if style_output else {}
    length_issues = parse_file_length_output(length_output) if length_output else {}

    # Combine all files
    all_files = set(complexity_issues.keys()) | set(style_issues.keys()) | set(length_issues.keys())

    if not all_files:
        return

    # Calculate totals per file
    file_totals = []
    for filepath in all_files:
        complexity = complexity_issues.get(filepath, 0)
        style = style_issues.get(filepath, 0)
        length = length_issues.get(filepath, 0)
        total = complexity + style + length
        file_totals.append((filepath, complexity, style, length, total))

    # Sort by total issues (descending)
    file_totals.sort(key=lambda x: x[4], reverse=True)

    # Print top offenders
    print(f"\n{' = '*80}")
    print("📋 TOP FILES BY ISSUE COUNT")
    print(f"{' = '*80}")
    print(f"{'File':<55} {'Complex':>7} {'Style':>7} {'Length':>7} {'Total':>7}")
    print(f"{'-'*55} {'-'*7} {'-'*7} {'-'*7} {'-'*7}")

    # Show top 20 files
    for filepath, complexity, style, length, total in file_totals[:20]:
        # Shorten path for display
        display_path = filepath if len(filepath) <= 55 else "..." + filepath[-52:]
        print(f"{display_path:<55} {complexity:>7} {style:>7} {length:>7} {total:>7}")

    total_files = len(file_totals)
    if total_files > 20:
        print(f"\n... and {total_files - 20} more file(s) with issues")


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

    print(f"\n{'='*80}")
    print(f"{SYMBOL_REPORT} ANALYSIS SUMMARY")
    print(f"{'='*80}")

    total_issues = 0
    for check, exit_code in results.items():
        status = f"{SYMBOL_SUCCESS} PASS" if exit_code == 0 else f"{SYMBOL_WARNING} ISSUES"
        print(f"{check:20s}: {status}")
        if exit_code != 0:
            total_issues += 1

    print(f"{'='*80}")

    if total_issues == 0:
        print(f"{SYMBOL_SUCCESS} All checks passed!")
        return 0
    else:
        print(f"{SYMBOL_WARNING} {total_issues} check(s) found issues")
        return 1


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Analyze Python code quality",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s all              # Analyze entire project
  %(prog)s changed          # Analyze only git-modified files
  %(prog)s files src/ui/main_window.py  # Analyze specific files
  %(prog)s --skip-style all # Skip style checks, only complexity
        """,
    )

    parser.add_argument("mode", choices=["all", "changed", "files"], help="Analysis mode")
    parser.add_argument("files", nargs="*", help='Specific files to analyze (only for "files" mode)')
    parser.add_argument("--skip-style", action="store_true", help="Skip flake8 style analysis")
    parser.add_argument("--skip-formatting", action="store_true", help="Skip Black code formatting check")
    parser.add_argument("--skip-complexity", action="store_true", help="Skip Lizard complexity analysis")
    parser.add_argument("--skip-types", action="store_true", help="Skip mypy type analysis")
    parser.add_argument("--skip-length", action="store_true", help="Skip file length analysis")
    parser.add_argument("--skip-links", action="store_true", help="Skip markdown link validation")

    args = parser.parse_args()

    # Determine which files to analyze
    files_to_analyze = None

    if args.mode == "changed":
        files_to_analyze = get_changed_files()
        if not files_to_analyze:
            print(f"{SYMBOL_SUCCESS} No changed Python files found")
            return 0
        print(f"{SYMBOL_SEARCH} Analyzing {len(files_to_analyze)} changed file(s):")
        for f in files_to_analyze:
            print(f"  - {f}")
    elif args.mode == "files":
        if not args.files:
            print(f"{SYMBOL_ERROR} Error: 'files' mode requires file arguments")
            return 1
        files_to_analyze = args.files
        print(f"{SYMBOL_SEARCH} Analyzing {len(files_to_analyze)} specified file(s)")
    else:  # all
        print(f"{SYMBOL_SEARCH} Analyzing entire project: {', '.join(PYTHON_DIRS)}")

    # Run analyses
    results = {}
    complexity_output = ""
    style_output = ""
    length_output = ""

    if not args.skip_complexity:
        exit_code, output = analyze_complexity(files_to_analyze)
        results["Complexity"] = exit_code
        complexity_output = output

    if not args.skip_style:
        exit_code, output = analyze_style(files_to_analyze)
        results["Style"] = exit_code
        style_output = output

    if not args.skip_formatting:
        exit_code, _ = analyze_formatting(files_to_analyze)
        results["Formatting"] = exit_code

    if not args.skip_length:
        exit_code, output = analyze_file_length(files_to_analyze)
        results["File Length"] = exit_code
        length_output = output

    if not args.skip_types:
        exit_code, output = analyze_types(files_to_analyze)
        results["Types"] = exit_code

    if not args.skip_links:
        exit_code = analyze_links()
        results["Link Check"] = exit_code

    # Print summary with file breakdown
    return print_summary(results, complexity_output, style_output, length_output)


if __name__ == "__main__":
    sys.exit(main())
