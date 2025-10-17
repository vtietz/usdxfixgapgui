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
from typing import List, Tuple
from collections import defaultdict

# Fix Windows cmd encoding for emojis
if sys.platform == 'win32':
    import io
    if isinstance(sys.stdout, io.TextIOWrapper):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except AttributeError:
            pass


def safe_print(text: str):
    """Print text with fallback for Windows cmd encoding issues."""
    try:
        print(text)
    except UnicodeEncodeError:
        # Fallback: remove emojis and special chars
        ascii_text = text.encode('ascii', errors='replace').decode('ascii')
        print(ascii_text)


# Configuration
MAX_COMPLEXITY = 15  # CCN (Cyclomatic Complexity Number) threshold
MAX_NLOC = 100       # Max lines of code per function
MAX_LINE_LENGTH = 120  # Max line length (matches project style)

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
    print(f"\n{'='*80}")
    print(f"🔍 {description}")
    print(f"{'='*80}")

    try:
        result = subprocess.run(
            cmd,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False
        )

        output = result.stdout + result.stderr
        print(output)

        return result.returncode, output
    except Exception as e:
        error_msg = f"❌ Error running {description}: {e}"
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
            ["git", "diff", "--name-only", "HEAD"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True
        )

        # Also get untracked files
        result_untracked = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True
        )

        all_files = result.stdout.strip().split("\n") + result_untracked.stdout.strip().split("\n")

        # Filter for Python files only
        python_files = [
            f for f in all_files
            if f.endswith('.py') and f.strip() and not any(excl in f for excl in EXCLUDE_PATTERNS)
        ]

        return python_files
    except subprocess.CalledProcessError:
        print("⚠️  Warning: Not a git repository or git not available")
        return []


def analyze_complexity(files: List[str] = None) -> tuple:
    """Run Lizard complexity analysis.

    Args:
        files: Specific files to analyze, or None for all

    Returns:
        Tuple of (exit_code, output_text)
    """
    cmd = [
        sys.executable, "-m", "lizard",
        "--CCN", str(MAX_COMPLEXITY),  # Complexity threshold
        "--length", str(MAX_NLOC),     # Function length threshold
        "--warnings_only",             # Only show issues
        "--exclude", "*/__pycache__/*",
        "--exclude", "*/.pytest_cache/*",
        "--exclude", "*/build/*",
        "--exclude", "*/dist/*",
    ]

    if files:
        cmd.extend(files)
    else:
        cmd.extend(PYTHON_DIRS)

    exit_code, output = run_command(cmd, "Complexity Analysis (Lizard)")

    # Lizard returns 0 if no issues, parse output for summary
    if "No thresholds exceeded" in output or exit_code == 0:
        print("✅ No complexity issues found!")
        return 0, output
    else:
        print(f"⚠️  Found complexity issues (CCN > {MAX_COMPLEXITY} or NLOC > {MAX_NLOC})")
        return 1, output


def analyze_style(files: List[str] = None) -> tuple:
    """Run flake8 style analysis.

    Args:
        files: Specific files to analyze, or None for all

    Returns:
        Tuple of (exit_code, output_text)
    """
    # Check if flake8 is available
    try:
        subprocess.run([sys.executable, "-m", "flake8", "--version"],
                       capture_output=True, check=True)
    except subprocess.CalledProcessError:
        print("⚠️  flake8 not installed, skipping style analysis")
        print("   Install with: pip install flake8")
        return 0, ""

    cmd = [
        sys.executable, "-m", "flake8",
        "--max-line-length", str(MAX_LINE_LENGTH),
        "--exclude", "__pycache__,.pytest_cache,build,dist,.venv,venv",
        "--ignore", "E203,W503",  # Black-compatible ignores
        "--count",
        "--statistics",
    ]

    if files:
        cmd.extend(files)
    else:
        cmd.extend(PYTHON_DIRS)

    exit_code, output = run_command(cmd, "Style Analysis (flake8)")

    if exit_code == 0:
        print("✅ No style issues found!")
        return 0, output
    else:
        print("⚠️  Found style issues")
        return 1, output


def analyze_types(files: List[str] = None) -> tuple:
    """Run mypy type checking (optional).

    Args:
        files: Specific files to analyze, or None for all

    Returns:
        Tuple of (exit_code, output_text)
    """
    # Check if mypy is available
    try:
        subprocess.run([sys.executable, "-m", "mypy", "--version"],
                       capture_output=True, check=True)
    except subprocess.CalledProcessError:
        print("ℹ️  mypy not installed, skipping type analysis (optional)")
        return 0, ""

    cmd = [
        sys.executable, "-m", "mypy",
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
        print("✅ No type issues found!")
        return 0, output
    else:
        print("ℹ️  Found type issues (informational only)")
        return 0, output  # Don't fail on type issues


def parse_style_output(output: str) -> dict:
    """Parse flake8 output to count issues per file.

    Args:
        output: flake8 output string

    Returns:
        Dict mapping file path to issue count
    """
    file_issues = defaultdict(int)

    for line in output.split('\n'):
        if ':' in line and len(line.split(':')) >= 3:
            # Format: path/to/file.py:line:col: CODE message
            filepath = line.split(':')[0]
            if filepath and filepath.endswith('.py'):
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

    for line in output.split('\n'):
        if 'warning:' in line and ':' in line:
            # Format: path/to/file.py:line: warning: ...
            filepath = line.split(':')[0]
            if filepath and filepath.endswith('.py'):
                file_issues[filepath] += 1

    return dict(file_issues)


def print_file_summary(complexity_output: str = "", style_output: str = ""):
    """Print summary of issues grouped by file.

    Args:
        complexity_output: Lizard output
        style_output: flake8 output
    """

    # Parse outputs
    complexity_issues = parse_complexity_output(complexity_output) if complexity_output else {}
    style_issues = parse_style_output(style_output) if style_output else {}

    # Combine all files
    all_files = set(complexity_issues.keys()) | set(style_issues.keys())

    if not all_files:
        return

    # Calculate totals per file
    file_totals = []
    for filepath in all_files:
        total = complexity_issues.get(filepath, 0) + style_issues.get(filepath, 0)
        file_totals.append((filepath, complexity_issues.get(filepath, 0), style_issues.get(filepath, 0), total))

    # Sort by total issues (descending)
    file_totals.sort(key=lambda x: x[3], reverse=True)

    # Print top offenders
    print(f"\n{'='*80}")
    print("📋 TOP FILES BY ISSUE COUNT")
    print(f"{'='*80}")
    print(f"{'File':<60} {'Complex':>8} {'Style':>8} {'Total':>8}")
    print(f"{'-'*60} {'-'*8} {'-'*8} {'-'*8}")

    # Show top 20 files
    for filepath, complexity, style, total in file_totals[:20]:
        # Shorten path for display
        display_path = filepath if len(filepath) <= 60 else '...' + filepath[-57:]
        print(f"{display_path:<60} {complexity:>8} {style:>8} {total:>8}")

    total_files = len(file_totals)
    if total_files > 20:
        print(f"\n... and {total_files - 20} more file(s) with issues")


def print_summary(results: dict, complexity_output: str = "", style_output: str = ""):
    """Print analysis summary.

    Args:
        results: Dict mapping check name to exit code
        complexity_output: Lizard output for file summary
        style_output: flake8 output for file summary
    """
    # Print file summary first if we have output
    if complexity_output or style_output:
        print_file_summary(complexity_output, style_output)

    print(f"\n{'='*80}")
    print("📊 ANALYSIS SUMMARY")
    print(f"{'='*80}")

    total_issues = 0
    for check, exit_code in results.items():
        status = "✅ PASS" if exit_code == 0 else "⚠️  ISSUES"
        print(f"{check:20s}: {status}")
        if exit_code != 0:
            total_issues += 1

    print(f"{'='*80}")

    if total_issues == 0:
        print("✅ All checks passed!")
        return 0
    else:
        print(f"⚠️  {total_issues} check(s) found issues")
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
        """
    )

    parser.add_argument(
        'mode',
        choices=['all', 'changed', 'files'],
        help='Analysis mode'
    )
    parser.add_argument(
        'files',
        nargs='*',
        help='Specific files to analyze (only for "files" mode)'
    )
    parser.add_argument(
        '--skip-style',
        action='store_true',
        help='Skip flake8 style analysis'
    )
    parser.add_argument(
        '--skip-complexity',
        action='store_true',
        help='Skip Lizard complexity analysis'
    )
    parser.add_argument(
        '--skip-types',
        action='store_true',
        help='Skip mypy type analysis'
    )

    args = parser.parse_args()

    # Determine which files to analyze
    files_to_analyze = None

    if args.mode == 'changed':
        files_to_analyze = get_changed_files()
        if not files_to_analyze:
            print("✅ No changed Python files found")
            return 0
        print(f"📝 Analyzing {len(files_to_analyze)} changed file(s):")
        for f in files_to_analyze:
            print(f"  - {f}")
    elif args.mode == 'files':
        if not args.files:
            print("❌ Error: 'files' mode requires file arguments")
            return 1
        files_to_analyze = args.files
        print(f"📝 Analyzing {len(files_to_analyze)} specified file(s)")
    else:  # all
        print(f"📝 Analyzing entire project: {', '.join(PYTHON_DIRS)}")

    # Run analyses
    results = {}
    complexity_output = ""
    style_output = ""

    if not args.skip_complexity:
        exit_code, output = analyze_complexity(files_to_analyze)
        results['Complexity'] = exit_code
        complexity_output = output

    if not args.skip_style:
        exit_code, output = analyze_style(files_to_analyze)
        results['Style'] = exit_code
        style_output = output

    if not args.skip_types:
        exit_code, output = analyze_types(files_to_analyze)
        results['Types'] = exit_code

    # Print summary with file breakdown
    return print_summary(results, complexity_output, style_output)


if __name__ == '__main__':
    sys.exit(main())
