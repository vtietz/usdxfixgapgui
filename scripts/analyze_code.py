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
import json


# Configuration
MAX_COMPLEXITY = 15  # CCN (Cyclomatic Complexity Number) threshold
MAX_NLOC = 100       # Max lines of code per function
MAX_LINE_LENGTH = 120  # Max line length (matches project style)

# Project root
PROJECT_ROOT = Path(__file__).parent.parent

# Directories to analyze
PYTHON_DIRS = [
    "psm",
    "tests",
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


def analyze_complexity(files: List[str] = None) -> int:
    """Run Lizard complexity analysis.
    
    Args:
        files: Specific files to analyze, or None for all
        
    Returns:
        Exit code (0 = success)
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
        return 0
    else:
        print(f"⚠️  Found complexity issues (CCN > {MAX_COMPLEXITY} or NLOC > {MAX_NLOC})")
        return 1


def analyze_style(files: List[str] = None) -> int:
    """Run flake8 style analysis.
    
    Args:
        files: Specific files to analyze, or None for all
        
    Returns:
        Exit code (0 = success)
    """
    # Check if flake8 is available
    try:
        subprocess.run([sys.executable, "-m", "flake8", "--version"], 
                      capture_output=True, check=True)
    except subprocess.CalledProcessError:
        print("⚠️  flake8 not installed, skipping style analysis")
        print("   Install with: pip install flake8")
        return 0
    
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
        return 0
    else:
        print(f"⚠️  Found style issues")
        return 1


def analyze_types(files: List[str] = None) -> int:
    """Run mypy type checking (optional).
    
    Args:
        files: Specific files to analyze, or None for all
        
    Returns:
        Exit code (0 = success)
    """
    # Check if mypy is available
    try:
        subprocess.run([sys.executable, "-m", "mypy", "--version"], 
                      capture_output=True, check=True)
    except subprocess.CalledProcessError:
        print("ℹ️  mypy not installed, skipping type analysis (optional)")
        return 0
    
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
        return 0
    else:
        print("ℹ️  Found type issues (informational only)")
        return 0  # Don't fail on type issues


def print_summary(results: dict):
    """Print analysis summary.
    
    Args:
        results: Dict mapping check name to exit code
    """
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
  %(prog)s files psm/gui/main_window.py  # Analyze specific files
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
    
    if not args.skip_complexity:
        results['Complexity'] = analyze_complexity(files_to_analyze)
    
    if not args.skip_style:
        results['Style'] = analyze_style(files_to_analyze)
    
    if not args.skip_types:
        results['Types'] = analyze_types(files_to_analyze)
    
    # Print summary
    return print_summary(results)


if __name__ == '__main__':
    sys.exit(main())
