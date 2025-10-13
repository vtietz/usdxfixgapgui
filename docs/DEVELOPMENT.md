# Development Guide

## Quick Start

### Initial Setup

```bash
# Windows
run.bat install-dev

# Linux/macOS
./run.sh install-dev
```

This installs:
- Runtime dependencies (from `requirements.txt`)
- Development dependencies (from `requirements-dev.txt`)
  - pytest, pytest-qt, pytest-mock (testing)
  - lizard (complexity analysis)
  - flake8 (style checking)
  - mypy (type checking - optional)
  - autoflake (unused import removal)

## Development Workflow

### Running the Application

```bash
# Windows
run.bat start

# Linux/macOS
./run.sh start
```

### Running Tests

```bash
# Windows
run.bat test

# Linux/macOS
./run.sh test
```

### Code Quality Analysis

Analyze code for complexity issues, style violations, and type problems:

```bash
# Analyze only changed files (default, recommended)
run.bat analyze
./run.sh analyze

# Analyze entire project
run.bat analyze all
./run.sh analyze all

# Analyze specific files
run.bat analyze files src/ui/main_window.py src/services/gap_service.py
./run.sh analyze files src/ui/main_window.py src/services/gap_service.py

# Skip certain checks
run.bat analyze all --skip-style
run.bat analyze all --skip-complexity
```

**Quality Thresholds:**
- **Cyclomatic Complexity (CCN)**: ≤ 15 per function
- **Function Length (NLOC)**: ≤ 100 lines per function
- **Line Length**: ≤ 120 characters
- **Style**: PEP 8 compliant (with Black-compatible ignores)

### Code Cleanup

Automatically fix common style issues:

```bash
# Preview changes without modifying files (dry run)
run.bat cleanup --dry-run
./run.sh cleanup --dry-run

# Clean only changed files (default)
run.bat cleanup
./run.sh cleanup

# Clean entire project
run.bat cleanup all
./run.sh cleanup all

# Clean specific files
run.bat cleanup files src/services/gap_service.py
./run.sh cleanup files src/services/gap_service.py

# Skip certain cleanup operations
run.bat cleanup all --skip-imports
run.bat cleanup all --skip-whitespace
```

**Cleanup Operations:**
- Remove trailing whitespace
- Fix whitespace-only blank lines
- Add missing newline at end of file
- Remove unused imports (via autoflake)

## Development Dependencies

### Runtime vs Development

**Runtime dependencies** (`requirements.txt`):
- Included in built executables
- Required for end users
- Examples: PySide6, spleeter, torch, librosa

**Development dependencies** (`requirements-dev.txt`):
- **NOT** included in built executables
- Only for developers
- Examples: pytest, lizard, flake8, mypy, autoflake

### Installing Development Dependencies

Development dependencies are automatically installed with:

```bash
run.bat install-dev
./run.sh install-dev
```

Or manually:

```bash
pip install -r requirements-dev.txt
```

## Building Executables

### Build Process

All build scripts automatically **exclude development dependencies** to minimize executable size:

```bash
# Windows
build.bat

# Linux
./build_linux.sh

# macOS
./build_macos.sh
```

**Excluded from builds:**
- pytest, pytest-qt, pytest-mock
- lizard, flake8, mypy, autoflake
- IPython, jupyter, notebook

This significantly reduces the executable size while keeping all runtime functionality.

### Build Output

- Windows: `dist/usdxfixgap.exe`
- Linux: `dist/usdxfixgap`
- macOS: `dist/usdxfixgap`

## Best Practices

### Before Committing

1. **Run tests**:
   ```bash
   run.bat test
   ```

2. **Analyze code quality**:
   ```bash
   run.bat analyze
   ```

3. **Clean up code**:
   ```bash
   run.bat cleanup
   ```

4. **Address any issues** found by the analysis tools

### During Development

- Use `run.bat analyze` after making significant changes
- Run tests frequently to catch regressions early
- Use `run.bat cleanup --dry-run` to preview automatic fixes before applying

### Code Quality Gates

Before committing, ensure:
- ✅ All tests pass
- ✅ No functions with CCN > 15
- ✅ No functions with NLOC > 100
- ✅ No flake8 style violations
- ✅ No trailing whitespace or missing EOF newlines

## Additional Commands

### Clean Build Artifacts

```bash
run.bat clean
./run.sh clean
```

Removes:
- `__pycache__` directories
- Cache database (`src/cache.db`)
- Test output files
- Temporary files

### Python Shell

```bash
run.bat shell
./run.sh shell
```

Opens interactive Python shell with project environment activated.

### Environment Info

```bash
run.bat info
./run.sh info
```

Shows:
- Conda environment info
- Python version
- Installed packages

## Troubleshooting

### "analyze" command not working

Make sure development dependencies are installed:

```bash
run.bat install-dev
```

### "cleanup" command not working

Install development dependencies (includes autoflake):

```bash
run.bat install-dev
```

### Build includes test libraries

This shouldn't happen with the updated build scripts. If it does:

1. Check that `build.bat` (or `build_linux.sh`/`build_macos.sh`) has the `--exclude-module` flags
2. Clean old build artifacts: `rmdir /s /q build dist` (Windows) or `rm -rf build dist` (Linux/macOS)
3. Rebuild

## See Also

- [Architecture](architecture.md) - System design and patterns
- [Coding Standards](coding-standards.md) - Code style guidelines
- [Signals](signals.md) - Signal/slot patterns
- [Release Process](RELEASE_PROCESS.md) - How to create releases
