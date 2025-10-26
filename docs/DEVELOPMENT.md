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
  - mypy (type checking)
  - autoflake (unused import removal)
  - black (code formatting)

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
- Format code with Black (opinionated formatter, line-length=120)

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
.\run.bat build

# Linux/macOS
./run.sh build
```

**Excluded from builds:**
- pytest, pytest-qt, pytest-mock
- lizard, flake8, mypy, autoflake, black
- IPython, jupyter, notebook

**Included in builds:**
- **CPU-only PyTorch** (~300-500 MB) - Works immediately, no extra downloads required
- All other runtime dependencies (PySide6, librosa, demucs, etc.)

**GPU Pack Architecture:**
The executable bundles **CPU-only PyTorch** for immediate functionality. Users can optionally upgrade:
- **CPU mode** (bundled): ~2-5 minutes per song, works everywhere
- **GPU mode** (optional download): ~10-30 seconds per song with GPU Pack (~2.8 GB)
- Downloads from GitHub releases with automatic hardware detection
- Supports CUDA 12.1 and 12.4 flavors
- GPU Pack overrides bundled CPU-only PyTorch when installed

This approach provides immediate functionality while enabling optional 10x GPU acceleration.

### Build Output

- Windows: `dist/usdxfixgap.exe`
- Linux: `dist/usdxfixgap`
- macOS: `dist/usdxfixgap`

## Code Formatting with Black

The project uses [Black](https://black.readthedocs.io/) for consistent code formatting.

**Configuration** (`pyproject.toml`):
- Line length: 120 characters
- Python version: 3.11
- Excludes: `.venv`, `build`, `dist`, `pretrained_models`

**Format code manually:**
```bash
# Format specific file
black src/ui/main_window.py

# Format entire project
black .
```

**Automatic formatting:**
- VS Code: Save file triggers auto-format (enabled in `.vscode/settings.json`)
- Command line: `run.bat cleanup` applies Black formatting

**Check formatting without changes:**
```bash
black --check .
```

## CI/CD Workflows

The project uses GitHub Actions for continuous integration:

**CI Workflow** (`.github/workflows/ci.yml`):
- Triggers: Push to `main`/`develop`/`mdx_only_detection_method`, pull requests
- Runs: Tests, lizard, flake8, mypy, black check
- Purpose: Ensure code quality before merging
- Dependencies: Uses `requirements.txt` + `requirements-dev.txt`

**Build Workflow** (`.github/workflows/build-exe.yml`):
- Triggers: Manual workflow dispatch
- Builds: Windows (.exe), Linux (.tar.gz), macOS (.tar.gz)
- Dependencies: Uses `requirements-build.txt` (CPU-only PyTorch)
- Purpose: Test builds without creating releases

**Release Workflow** (`.github/workflows/release.yml`):
- Triggers: Git tags (e.g., `v2.0.0`)
- Builds: Windows (.exe), Linux (.tar.gz), macOS (.tar.gz)
- Dependencies: Uses `requirements-build.txt` (CPU-only PyTorch)
- Publishes: GitHub release with artifacts and notes from `docs/releases/{VERSION}.md`
- Executable size: ~350-500 MB (CPU-only PyTorch bundled)

## Best Practices

### Before Committing

1. **Run tests**:
   ```bash
   run.bat test
   ```

2. **Format code**:
   ```bash
   run.bat cleanup
   ```

3. **Analyze code quality**:
   ```bash
   run.bat analyze
   ```

4. **Address any issues** found by the analysis tools

**Quick validation** (same as CI):
```bash
run.bat test && run.bat cleanup && run.bat analyze
```

### During Development

- Use `run.bat analyze` after making significant changes
- Run tests frequently to catch regressions early
- Use `run.bat cleanup --dry-run` to preview automatic fixes before applying

### Code Quality Gates

Before committing, ensure:
- ✅ All tests pass (`run.bat test`)
- ✅ Code is formatted with Black (`run.bat cleanup`)
- ✅ No functions with CCN > 15 (`run.bat analyze`)
- ✅ No functions with NLOC > 100 (`run.bat analyze`)
- ✅ No flake8 style violations (`run.bat analyze`)
- ✅ No type errors (`run.bat analyze`)

**CI will reject PRs that fail these checks.**

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

1. Check that `run.bat build` / `run.sh build` has the `--exclude-module` flags in the PyInstaller command
2. Clean old build artifacts: `rmdir /s /q build dist` (Windows) or `rm -rf build dist` (Linux/macOS)
3. Rebuild

## See Also

- [Architecture](architecture.md) - System design, layers, signal patterns
- [Coding Standards](coding-standards.md) - Code style guidelines
- [Release Process](RELEASE_PROCESS.md) - How to create releases
