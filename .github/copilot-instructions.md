# GitHub Copilot Instructions for USDXFixGap# GitHub Copilot Instructions for USDXFixGap



Python/PySide6 GUI app for karaoke song gap detection using AI vocal separation. See `docs/` for architecture.md, coding-standards.md, signals.md.This file provides specific instructions for GitHub Copilot to assist with development in the USDXFixGap project. These instructions are based on the current implementation and focus on immediate productivity.



## Core Rules## **General Principles**



1. **Examine before implementing** - Check `src/actions/`, `src/ui/`, `tests/` to avoid duplicates and reuse existing patterns- **Never maintain backward compatibility with outdated code or patterns.** Always modernize and refactor as needed.

2. **Always test changes** - Use `run.bat test` (conda env required). Auto-run after code changes- **Always update or add tests and documentation** when making changes. Code changes must be accompanied by relevant test and doc updates.

3. **Modernize, don't maintain backward compatibility** - Refactor outdated patterns- **Run tests automatically after code changes** to validate functionality. No approval needed for test execution.

4. **Use early returns** - Avoid nesting, check failures first- **Read existing architecture and coding documentation first.** Check `docs/` folder for architecture.md, coding-standards.md, signals.md and apply their guidelines.

5. **Clean as you go** - Remove unused code, add type hints, use stdlib over custom- **Before implementing anything, examine the existing codebase and tests thoroughly** to:

  - Avoid duplicate implementations or reimplementing existing functionality

## Architecture (Dependency Injection via AppData)  - Identify opportunities to extend existing tests with simple assertions rather than creating complete new test files

  - Understand current patterns and conventions to maintain consistency

```python  - Find reusable components, services, or utilities that already exist

# Actions pattern- **If any code file (including tests) grows beyond ~500 lines, propose and implement a refactor** to split it into smaller, more maintainable modules.

class MyActions(BaseActions):- **Maintain a concise changelog document after each major feature or refactoring change, ideally with date.**

    def __init__(self, data: AppData):

        self.data = data  # config, songs, worker_queue, selected_songs## **Project Context**



# Signal flow - ALWAYS use Songs collectionUSDXFixGap is a Python GUI application built with PySide6 for audio processing and gap detection in karaoke songs. It uses AI-powered vocal separation (Demucs MDX) to detect timing gaps in UltraStar Deluxe song files.

self.data.songs.updated.emit(song)      # ✅ Model state changed

self.data.songs.listChanged.emit()     # ✅ List structure changed### **Technology Stack**

self.song_updated.emit(song)           # ❌ NO - direct signals- **Python 3.8+** with **PySide6** (Qt for Python)

- **Demucs** for AI vocal separation, **ffmpeg** for audio processing

# Background tasks- **pytest** for testing, **PyInstaller** for builds

worker = MyWorker(params)- **Architecture**: Actions-based pattern with dependency injection via `AppData`

self.worker_queue.add_task(worker)     # ✅ Managed queue

threading.Thread(target=...).start()   # ❌ NO - direct threading### **Directory Structure**

```

# Error handlingsrc/

song.set_error("message")├── actions/          # BaseActions + specialized modules

song.clear_error()├── services/         # Business logic (GapInfoService, SongService)

├── model/            # Song, Songs, GapInfo (snake_case dirs)

# Imports (snake_case directories)├── ui/               # PySide6 components

from model.song import Song├── workers/          # Background tasks with IWorker base

from actions.base_actions import BaseActions├── app/              # AppData container

```└── utils/            # Shared utilities

```

## Development Commands (Windows)

## **Core Architecture**

```bash

run.bat test              # Run tests (ALWAYS use this, not pytest directly)**Read `docs/architecture.md`, `docs/coding-standards.md`, and `docs/signals.md` for detailed guidelines.**

run.bat start             # Start application

run.bat install           # Setup conda env### **Key Components**

run.bat analyze           # Code quality (CCN, length, style)- **AppData**: Central dependency container with `config`, `songs`, `worker_queue`, `selected_songs`

build.bat                 # Build executable- **Actions**: Composition pattern - main Actions class delegates to specialized modules

```- **Models**: Song/Songs with signal integration via Songs collection

- **Services**: Business logic layer with error handling patterns

**Never run `python` or `pytest` directly** - conda env via `run.bat` required.- **Workers**: Background tasks managed by worker queue



## Testing Strategy### **Signal Flow**

```python

**When to test bug fixes:**# ✅ Use Songs collection signals

- ✅ Data corruption/silent failures (locale parsing, infinite loops)self.data.songs.updated.emit(song)      # Model state changed

- ✅ Edge cases not in existing tests (missing files, invalid data)self.data.songs.listChanged.emit()     # List structure changed

- ✅ Critical user features (song loading, gap detection, UI sync)

- ❌ Typos, logging messages, cosmetic UI, documentation# ❌ Avoid direct signals from actions

self.song_updated.emit(song)  # NO - use data.songs.updated

**Prefer extending existing tests** - Add assertions to existing files vs creating new test files.```



Example: `patch('actions.module.Service')` for mocking services.## **Development Patterns**



## Code Quality (Before Commit)**Refer to existing code in `src/actions/`, `src/ui/`, `tests/` for implementation patterns.**



```bash### **Standard Patterns**

run.bat analyze  # Check: CCN > 15, NLOC > 100, style, imports- **Actions**: Inherit from `BaseActions`, use dependency injection, standard error handling

```- **Workers**: Background tasks via `self.worker_queue.add_task(worker)`

- **Error Handling**: `song.set_error("message")` / `song.clear_error()`

- **Nested logic** → Extract helper functions- **Imports**: `from model.song import Song` (snake_case directories)

- **Long functions** → Split into single-responsibility functions  

- **Style** → PEP 8 + 120 char line length## Code Quality

- **Files > 500 lines** → Refactor into smaller modules* **Remove Unused Code**: Delete unused imports, variables, and helper functions after refactoring. Don't leave dead code.

* **Use Standard Library**: Prefer built-in modules (copy.deepcopy, functools.lru_cache) over custom implementations.

## Final Actions* **Performance Awareness**: Cache expensive operations (normalization, OAuth sessions), use connection pooling, avoid redundant work.

* **Type Hints**: Add type hints to function signatures for better IDE support and self-documentation.

1. Run `run.bat test` to validate changes* **Avoid Nested If Statements**: Use early returns/exits to reduce nesting. Check failure conditions first and return early, then handle the success path in the main flow. This improves readability and reduces cognitive load.

2. Propose concise commit message (imperative mood: "Fix bug", "Add feature")

3. Update README.md for user-facing changes only**Example - Bad (nested):**

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

**IMPORTANT: Always use the project wrapper scripts**

The project uses a local virtual environment (.venv) for consistent dependencies. Never run tests or commands directly - always use `run.bat` (Windows) or `run.sh` (Linux/macOS).

**⚠️ Windows PowerShell Note:** Use `.\run.bat` syntax in PowerShell (the `.\` prefix is required)

```bash
# ✅ CORRECT - Run tests using wrapper
.\run.bat test            # Windows PowerShell (note the .\ prefix)
run.bat test              # Windows cmd
./run.sh test             # Linux/macOS

# ❌ WRONG - Don't run tests directly
python -m pytest tests/ -v  # May fail due to missing dependencies
pytest tests/ -v            # May use wrong Python version

# Other useful wrapper commands (Windows PowerShell examples):
.\run.bat start           # Start the application
.\run.bat install         # Install/update dependencies
.\run.bat install --gpu   # Install with GPU/CUDA support
.\run.bat clean           # Clean cache and temporary files
.\run.bat shell           # Interactive Python shell
.\run.bat info            # Show environment info
.\run.bat analyze         # Code quality analysis
.\run.bat cleanup         # Code cleanup tools
```

**Test patterns:**
- Use existing test patterns from `tests/` directory
- Tests auto-import from `src/` when run via wrappers
- Mock services with `patch('actions.module.Service')`
- Follow pytest conventions for test naming: `test_*.py` and `test_*()` functions

**Bug fix testing guidelines:**
- **Consider creating tests for bug fixes** when the bug involves:
  - Data corruption or silent failures (e.g., locale parsing errors, infinite loops)
  - Edge cases that aren't covered by existing tests (e.g., missing files, invalid data)
  - Critical user-facing features (e.g., song loading, gap detection, UI synchronization)
- **Skip creating tests** for trivial bugs like:
  - Simple typos or cosmetic UI issues
  - Logging message corrections
  - Documentation updates
- **Prefer extending existing tests** over creating new files:
  - Add a simple assertion to an existing test if it covers the same code path
  - Only create a new test file if the bug involves untested functionality
- **Example**: Locale decimal parsing bug (comma vs period) warrants a test because it causes silent data corruption for international users

## **Development Setup**

**Windows:**
```bash
# ✅ Initial setup (run.bat handles environment creation automatically)
run.bat install           # Creates .venv and installs dependencies

# ✅ Run application
run.bat start

# ✅ Run tests
run.bat test

# ✅ Build executable
build.bat  # PyInstaller with assets
```

**Linux/macOS:**
```bash
# ✅ Initial setup (run.sh handles environment creation automatically)
./run.sh install          # Creates .venv and installs dependencies

# ✅ Run application
./run.sh start

# ✅ Run tests
./run.sh test
```

**Requirements:**
- Python 3.8+ installed (python3 on Linux/macOS, python or py launcher on Windows)
- ffmpeg on PATH (for audio processing)
- Virtual environment automatically created by wrapper scripts in `.venv`

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

# Code Quality Standards

## Goals
- Keep code simple, small, and safe.
- Prefer clear types & interfaces over dynamic dicts/strings.
- Changes must pass local quality gates before commit/PR.

## Design & Clean Code (musts)
- Single responsibility: each file/class/function has one clear job. If a file exceeds the limits below, split it.
- APIs over ad-hoc dicts: use dataclasses/TypedDict/Pydantic (or language equivalent). Avoid getattr/hasattr tricks.
- Small units: default max function length 80 lines; file length 500–800 lines; cyclomatic complexity ≤10 (warn) / ≤15 (fail).
- Explicit errors: raise typed exceptions; no silent excepts. Log with context.
- Dependency hygiene: minimize imports; no side effects at import time.
- Naming: descriptive, consistent, no abbreviations without reason.
- Immutability by default: avoid mutating global state.

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
