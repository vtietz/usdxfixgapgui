# GitHub Copilot Instructions for USDXFixGap

This file provides specific instructions for GitHub Copilot to assist with development in the USDXFixGap project. These instructions are based on the current implementation and focus on immediate productivity.

## **General Principles**

- **Never maintain backward compatibility with outdated code or patterns.** Always modernize and refactor as needed.
- **Always update or add tests and documentation** when making changes. Code changes must be accompanied by relevant test and doc updates.
- **Run tests automatically after code changes** to validate functionality. No approval needed for test execution.
- **Read existing architecture and coding documentation first.** Check `docs/` folder for architecture.md, coding-standards.md, signals.md and apply their guidelines.
- **If any code file (including tests) grows beyond ~500 lines, propose and implement a refactor** to split it into smaller, more maintainable modules.
- **Maintain a concise changelog document after each major feature or refactoring change, ideally with date.**

## **Project Context**

USDXFixGap is a Python GUI application built with PySide6 for audio processing and gap detection in karaoke songs. It uses AI-powered vocal separation (Spleeter) to detect timing gaps in UltraStar Deluxe song files.

### **Technology Stack**
- **Python 3.8+** with **PySide6** (Qt for Python)
- **Spleeter** for AI vocal separation, **ffmpeg** for audio processing
- **pytest** for testing, **PyInstaller** for builds
- **Architecture**: Actions-based pattern with dependency injection via `AppData`

### **Directory Structure**
```
src/
├── actions/          # BaseActions + specialized modules
├── services/         # Business logic (GapInfoService, SongService)
├── model/            # Song, Songs, GapInfo (snake_case dirs)
├── ui/               # PySide6 components
├── workers/          # Background tasks with IWorker base
├── app/              # AppData container
└── utils/            # Shared utilities
```

## **Core Architecture**

**Read `docs/architecture.md`, `docs/coding-standards.md`, and `docs/signals.md` for detailed guidelines.**

### **Key Components**
- **AppData**: Central dependency container with `config`, `songs`, `worker_queue`, `selected_songs`
- **Actions**: Composition pattern - main Actions class delegates to specialized modules
- **Models**: Song/Songs with signal integration via Songs collection
- **Services**: Business logic layer with error handling patterns
- **Workers**: Background tasks managed by worker queue

### **Signal Flow**
```python
# ✅ Use Songs collection signals
self.data.songs.updated.emit(song)      # Model state changed
self.data.songs.listChanged.emit()     # List structure changed

# ❌ Avoid direct signals from actions
self.song_updated.emit(song)  # NO - use data.songs.updated
```

## **Development Patterns**

**Refer to existing code in `src/actions/`, `src/ui/`, `tests/` for implementation patterns.**

### **Standard Patterns**
- **Actions**: Inherit from `BaseActions`, use dependency injection, standard error handling
- **Workers**: Background tasks via `self.worker_queue.add_task(worker)`
- **Error Handling**: `song.set_error("message")` / `song.clear_error()`
- **Imports**: `from model.song import Song` (snake_case directories)

## Code Quality
* **Remove Unused Code**: Delete unused imports, variables, and helper functions after refactoring. Don't leave dead code.
* **Use Standard Library**: Prefer built-in modules (copy.deepcopy, functools.lru_cache) over custom implementations.
* **Performance Awareness**: Cache expensive operations (normalization, OAuth sessions), use connection pooling, avoid redundant work.
* **Type Hints**: Add type hints to function signatures for better IDE support and self-documentation.
* **Avoid Nested If Statements**: Use early returns/exits to reduce nesting. Check failure conditions first and return early, then handle the success path in the main flow. This improves readability and reduces cognitive load.

**Example - Bad (nested):**
```python
if condition1:
    if condition2:
        if condition3:
            # Do work
            return result
```

**Example - Good (early returns):**
```python
if not condition1:
    return
if not condition2:
    return
if not condition3:
    return
# Do work
return result
```

### **Testing**

**IMPORTANT: Always use the conda environment via run.bat**

The project uses a conda environment for consistent dependencies. Never run tests or commands directly - always use `run.bat`:

```bash
# ✅ CORRECT - Run tests using conda environment
run.bat test              # Runs pytest with proper environment

# ❌ WRONG - Don't run tests directly
python -m pytest tests/ -v  # May fail due to missing dependencies
pytest tests/ -v            # May use wrong Python version

# Other useful run.bat commands:
run.bat start             # Start the application
run.bat install           # Install/update dependencies
run.bat clean             # Clean cache and temporary files
run.bat shell             # Interactive Python shell
run.bat info              # Show environment info
```

**Test patterns:**
- Use existing test patterns from `tests/` directory
- Tests auto-import from `src/` when run via `run.bat test`
- Mock services with `patch('actions.module.Service')`
- Follow pytest conventions for test naming: `test_*.py` and `test_*()` functions

## **Development Setup**

**Windows:**
```bash
# ✅ Initial setup (run.bat handles environment creation automatically)
run.bat install           # Creates conda env and installs dependencies

# ✅ Run application
run.bat start

# ✅ Run tests
run.bat test

# ✅ Build executable
build.bat  # PyInstaller with assets
```

**Requirements:**
- Anaconda or Miniconda installed and in PATH
- ffmpeg on PATH (for audio processing)
- Python 3.8+ (managed by conda environment)

## **Common Gotchas**

```python
# ✅ Connect to Songs signals, not individual objects
self.data.songs.updated.connect(self.refresh_ui)
self.data.songs.listChanged.connect(self.rebuild_list)

# ✅ Use existing utilities
from utils.files import get_app_dir, resource_path
app_dir = get_app_dir()  # User data directory

# ✅ Use worker queue, not direct threading
worker = SomeWorker(params)
self.worker_queue.add_task(worker)  # Managed queue

# ❌ Don't create individual object signals
song.status_changed.connect(...)  # Not implemented

# ❌ Avoid direct threading
threading.Thread(target=...).start()  # Don't do this
```

## **Quick Reference**

### **Key Patterns**
- Actions inherit from `BaseActions(data: AppData)`
- Use `self.worker_queue.add_task(worker)` for background tasks
- Emit signals via `self.data.songs.updated.emit(song)`
- Error handling: `song.set_error("message")` and `song.clear_error()`
- Tests: Mock services with `patch('actions.module.Service')`

### **Common Commands**
```bash
# Use run.bat for all commands to ensure proper environment
run.bat test              # Run tests with pytest
run.bat start             # Start the application
run.bat install           # Install/update dependencies
run.bat clean             # Clean cache files
run.bat shell             # Interactive Python shell
run.bat info              # Show environment information
build.bat                 # Build Windows executable
```

### **File Patterns**
- Use existing patterns from the codebase as templates
- Check `src/actions/`, `src/ui/`, `tests/` for examples
- Follow import patterns: `from model.song import Song`

# Required final actions
* Run tests to ensure all changes pass.
* After your summary always propose clear, concise, one-liner commit message.
* Use the imperative mood in the subject line (e.g., "Add feature", "Fix bug", "Update docs").

## Code Quality Analysis
* **When to Run**: After bigger implementations, refactorings, or before committing significant changes
* **How to Run**:
  - `run.bat analyze` - Analyze only changed files (default, quick)
  - `run.bat analyze all` - Analyze entire project (comprehensive)
  - `run.bat analyze files <path>` - Analyze specific files
* **What to Check**:
  - **Complexity (Lizard)**: Functions with CCN > 15 need refactoring. Extract logic into smaller functions.
  - **Function Length**: Functions > 100 lines (NLOC) should be split into smaller, focused functions.
  - **Style (flake8)**: Fix any reported style issues. Project uses 120 char line length.
  - **Types (mypy)**: Optional but helpful. Add type hints to new functions.
* **Addressing Issues**:
  - **High Complexity**: Extract nested logic into helper functions, use early returns to reduce nesting
  - **Long Functions**: Split into multiple functions with clear single responsibilities
  - **Style Issues**: Follow PEP 8 with project-specific rules (120 char line length, Black-compatible)
  - **Import Issues**: Remove unused imports, organize imports logically

  ## Documentation
* **Update README.md**: Document new features, changed behavior, and important configuration options.
* **Docstrings Matter**: Write clear docstrings explaining what services do, their parameters, and return values.
* **No Unrequested Artifacts**: Don't create summary files or documentation unless explicitly requested.
