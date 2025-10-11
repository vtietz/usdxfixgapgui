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
```python
# Use existing test patterns from tests/ directory
python -m pytest tests/ -v  # Auto-imports from src/
```

## **Development Setup**

```bash
# ✅ Dependencies
pip install PySide6 spleeter pillow aiofiles pytest
# Requires ffmpeg on PATH

# ✅ Build (Windows)
build.bat  # PyInstaller with assets
```

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
python -m pytest tests/ -v        # Run tests
build.bat                          # Build Windows executable
```

### **File Patterns**
- Use existing patterns from the codebase as templates
- Check `src/actions/`, `src/ui/`, `tests/` for examples
- Follow import patterns: `from model.song import Song`

## Documentation
* **Update README.md**: Document new features, changed behavior, and important configuration options.
* **Docstrings Matter**: Write clear docstrings explaining what services do, their parameters, and return values.
* **No Unrequested Artifacts**: Don't create summary files or documentation unless explicitly requested.

# Required final actions
* Run tests to ensure all changes pass.
* After your summary always propose clear, concise commit messages that accurately describe the changes made.
* Use the imperative mood in the subject line (e.g., "Add feature", "Fix bug", "Update docs").