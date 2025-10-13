#!/usr/bin/env python3
"""Safe code cleanup script.

Automatically fixes low-hanging fruit style issues:
- Removes trailing whitespace from lines
- Removes whitespace-only blank lines
- Removes unused imports (using autoflake)
- Adds missing newline at end of file

SAFE operations only - does NOT:
- Reformat code structure
- Change line length
- Modify indentation
- Touch complex formatting

Usage:
    python scripts/cleanup_code.py all              # Clean entire project
    python scripts/cleanup_code.py changed          # Clean only git-modified files
    python scripts/cleanup_code.py files <path>...  # Clean specific files
    python scripts/cleanup_code.py --dry-run all    # Preview changes without modifying
"""
import sys
import argparse
import subprocess
from pathlib import Path
from typing import List


# Project root
PROJECT_ROOT = Path(__file__).parent.parent

# Directories to clean
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


def get_changed_files() -> List[Path]:
    """Get list of modified Python files from git.

    Returns:
        List of Path objects for modified Python files
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
            PROJECT_ROOT / f for f in all_files
            if f.endswith('.py') and f.strip() and not any(excl in f for excl in EXCLUDE_PATTERNS)
        ]

        return [f for f in python_files if f.exists()]
    except subprocess.CalledProcessError:
        print("⚠️  Warning: Not a git repository or git not available")
        return []


def get_all_python_files() -> List[Path]:
    """Get all Python files in the project.

    Returns:
        List of Path objects for all Python files
    """
    python_files = []
    for dir_name in PYTHON_DIRS:
        dir_path = PROJECT_ROOT / dir_name
        if dir_path.exists():
            python_files.extend(dir_path.rglob("*.py"))

    # Filter out excluded directories
    return [
        f for f in python_files
        if not any(excl in str(f) for excl in EXCLUDE_PATTERNS)
    ]


def clean_whitespace(file_path: Path, dry_run: bool = False) -> dict:
    """Clean whitespace issues in a file.

    Fixes:
    - Trailing whitespace on lines
    - Whitespace-only blank lines
    - Missing newline at end of file

    Args:
        file_path: Path to file to clean
        dry_run: If True, don't modify file, just report changes

    Returns:
        Dict with counts of fixes made
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            original_lines = f.readlines()
    except Exception as e:
        print(f"⚠️  Error reading {file_path}: {e}")
        return {'trailing': 0, 'blank': 0, 'eof': 0}

    if not original_lines:
        return {'trailing': 0, 'blank': 0, 'eof': 0}

    trailing_count = 0
    blank_whitespace_count = 0
    cleaned_lines = []

    for line in original_lines:
        original_line = line

        # Remove trailing whitespace
        line = line.rstrip() + '\n' if line.endswith('\n') else line.rstrip()

        if original_line != line:
            if original_line.strip() == '':
                # This was a whitespace-only blank line
                blank_whitespace_count += 1
            else:
                # This was a line with trailing whitespace
                trailing_count += 1

        cleaned_lines.append(line)

    # Ensure file ends with newline
    eof_fix = 0
    if cleaned_lines and not cleaned_lines[-1].endswith('\n'):
        cleaned_lines[-1] += '\n'
        eof_fix = 1

    # Write back if changes were made and not dry run
    if (trailing_count > 0 or blank_whitespace_count > 0 or eof_fix > 0) and not dry_run:
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(cleaned_lines)
        except Exception as e:
            print(f"⚠️  Error writing {file_path}: {e}")
            return {'trailing': 0, 'blank': 0, 'eof': 0}

    return {
        'trailing': trailing_count,
        'blank': blank_whitespace_count,
        'eof': eof_fix
    }


def remove_unused_imports(files: List[Path], dry_run: bool = False) -> int:
    """Remove unused imports using autoflake.

    Args:
        files: List of files to process
        dry_run: If True, don't modify files

    Returns:
        Number of files with removed imports
    """
    # Check if autoflake is available
    try:
        subprocess.run(
            [sys.executable, "-m", "autoflake", "--version"],
            capture_output=True,
            check=True
        )
    except subprocess.CalledProcessError:
        print("ℹ️  autoflake not installed, skipping unused import removal")
        print("   Install with: pip install autoflake")
        return 0

    if not files:
        return 0

    # Build autoflake command
    cmd = [
        sys.executable, "-m", "autoflake",
        "--remove-all-unused-imports",
        "--remove-unused-variables",
    ]

    if not dry_run:
        cmd.append("--in-place")

    # Add all files
    cmd.extend([str(f) for f in files])

    try:
        result = subprocess.run(
            cmd,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False
        )

        # Count files that would be/were modified
        output = result.stdout + result.stderr
        if dry_run:
            # In dry-run, autoflake prints diffs
            modified_count = output.count('---')
        else:
            # Count files actually modified by checking if output mentions them
            modified_count = sum(1 for f in files if str(f.name) in output)

        if modified_count > 0 and not dry_run:
            print(f"✅ Removed unused imports from {modified_count} file(s)")
        elif modified_count > 0 and dry_run:
            print(f"ℹ️  Would remove unused imports from {modified_count} file(s)")

        return modified_count
    except Exception as e:
        print(f"⚠️  Error running autoflake: {e}")
        return 0


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Clean Python code (whitespace, unused imports)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s all                     # Clean entire project
  %(prog)s changed                 # Clean only git-modified files
  %(prog)s files src/config.py     # Clean specific files
  %(prog)s --dry-run all           # Preview changes without modifying
  %(prog)s --skip-imports all      # Only clean whitespace, skip imports
        """
    )

    parser.add_argument(
        'mode',
        choices=['all', 'changed', 'files'],
        help='Cleanup mode'
    )
    parser.add_argument(
        'files',
        nargs='*',
        help='Specific files to clean (only for "files" mode)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without modifying files'
    )
    parser.add_argument(
        '--skip-imports',
        action='store_true',
        help='Skip unused import removal'
    )
    parser.add_argument(
        '--skip-whitespace',
        action='store_true',
        help='Skip whitespace cleanup'
    )

    args = parser.parse_args()

    # Determine which files to clean
    files_to_clean = []

    if args.mode == 'changed':
        files_to_clean = get_changed_files()
        if not files_to_clean:
            print("✅ No changed Python files found")
            return 0
        print(f"📝 Cleaning {len(files_to_clean)} changed file(s)")
    elif args.mode == 'files':
        if not args.files:
            print("❌ Error: 'files' mode requires file arguments")
            return 1
        files_to_clean = [Path(f) for f in args.files]
        print(f"📝 Cleaning {len(files_to_clean)} specified file(s)")
    else:  # all
        files_to_clean = get_all_python_files()
        print(f"📝 Cleaning entire project: {len(files_to_clean)} file(s)")

    if args.dry_run:
        print("🔍 DRY RUN MODE - No files will be modified\n")

    # Clean whitespace
    if not args.skip_whitespace:
        print(f"\n{'=' * 80}")
        print("🧹 Cleaning Whitespace")
        print(f"{'=' * 80}")

        total_trailing = 0
        total_blank = 0
        total_eof = 0
        files_modified = 0

        for file_path in files_to_clean:
            stats = clean_whitespace(file_path, dry_run=args.dry_run)
            if stats['trailing'] > 0 or stats['blank'] > 0 or stats['eof'] > 0:
                files_modified += 1
                total_trailing += stats['trailing']
                total_blank += stats['blank']
                total_eof += stats['eof']

                rel_path = file_path.relative_to(PROJECT_ROOT)
                fixes = []
                if stats['trailing'] > 0:
                    fixes.append(f"{stats['trailing']} trailing")
                if stats['blank'] > 0:
                    fixes.append(f"{stats['blank']} blank")
                if stats['eof'] > 0:
                    fixes.append("EOF newline")
                print(f"  {rel_path}: {', '.join(fixes)}")

        if files_modified > 0:
            action = "Would clean" if args.dry_run else "Cleaned"
            print(f"\n{action}:")
            print(f"  - {total_trailing} lines with trailing whitespace")
            print(f"  - {total_blank} blank lines with whitespace")
            print(f"  - {total_eof} files missing EOF newline")
            print(f"  - Total: {files_modified} file(s) modified")
        else:
            print("✅ No whitespace issues found!")

    # Remove unused imports
    if not args.skip_imports:
        print(f"\n{'=' * 80}")
        print("🗑️  Removing Unused Imports")
        print(f"{'=' * 80}")

        removed_count = remove_unused_imports(files_to_clean, dry_run=args.dry_run)

        if removed_count == 0:
            print("✅ No unused imports found!")

    # Summary
    print(f"\n{'=' * 80}")
    print("📊 CLEANUP SUMMARY")
    print(f"{'=' * 80}")

    if args.dry_run:
        print("ℹ️  DRY RUN - No files were modified")
        print("   Run without --dry-run to apply changes")
    else:
        print("✅ Cleanup complete!")
        print("   Run code analysis to verify: run.bat analyze changed")

    return 0


if __name__ == '__main__':
    sys.exit(main())
