# GitHub Copilot Instructions — USDXFixGap

**Project:** Python/PySide6 GUI for UltraStar song gap detection (Demucs + ffmpeg).

⚠️ **DO NOT bump version numbers** - Maintainer controls versioning manually.

**Read First:** `docs/architecture.md` (includes signal patterns), `docs/coding-standards.md`.

---

## 0) Do-First Checklist

* Scan `src/actions/`, `src/ui/`, `src/services/`, `src/model/`, `tests/` to **reuse** patterns.
* If a similar feature exists, **extend it**; don't re-implement.
* Plan the **smallest change** that fits existing structure.

---

## 1) Core Rules

* **No backward-compat code.** Don't keep legacy shims/flags/APIs—modernize instead.
* **One source of truth.** Edit in place; don't create parallel files.
* **Keep it simple.** Early returns > deep nesting; avoid workaround branches.
* **Strong types & clean interfaces:** prefer `@dataclass` / `pydantic` / Protocols over `Dict[str, Any]`.
  Avoid `hasattr/getattr`—define a proper interface.
* **File naming & responsibility:** filenames must reflect content; each file does **one** thing.
  If purpose changes, **rename**; if mixed concerns, **split**.
* **Size triggers:** propose refactor if file > ~500 lines or function > ~80–100 lines.

---

## 2) Architecture Rules (AppData + Actions + Signals + Workers)

* **DI via `AppData`:** access `config`, `songs`, `worker_queue`, `selected_songs`.
* **Actions pattern:** classes inherit from `BaseActions(data: AppData)` and delegate to specialized modules.
* **Signals:**

  * ✅ `self.data.songs.updated.emit(song)` (model changed)
  * ✅ `self.data.songs.listChanged.emit()` (list structure changed)
  * ❌ No direct per-object signals from actions.
* **Workers:** queue only

  * ✅ `self.worker_queue.add_task(worker)`
  * ❌ No `threading.Thread(...)` directly.

---

## 3) File & Docs Management

* **Prefer extending existing files.** Only add new files if necessary.
* If replacing, **rename/reuse** (don't keep old + new).
* **Docs:** integrate updates into existing pages.
  Temporary plans/notes → put in `temp/` and clean up.
* **Imports:** snake_case dirs; e.g., `from model.song import Song`.
* **No side effects at import time.**

---

## 4) Coding Standards (short version)

* **KISS, DRY, SRP.** Small, single-purpose functions; minimize branching/side-effects.
* **Errors:** raise typed exceptions; no silent `except:`; log with context.
* **PEP 8 (120 cols), 4-space indent, grouped imports, no unused imports.**
* **Types:** add type hints; normalize external data to typed models at the boundary.
* **Performance:** avoid repeated heavy ops; reuse/cache when safe.

---

## 5) Testing Strategy

* **Always test changes.** Use wrapper scripts only.
* **Prefer extending existing tests**; add new files only if coverage is missing.
* **When unit tests suffice:** parsing/validation, prompt/formatting, selection/routing logic, pure services.
* **When integration tests needed:** Demucs/ffmpeg piping, worker queue behavior, signals/UI sync, real file IO paths.
* **Mocking:** e.g., `patch('actions.module.Service')`.
* **Naming:** `tests/test_*.py`; temporary experiments go to `temp/` and are cleaned.

---

## 6) Commands (use wrappers only)

> **Never** run `python`/`pytest` directly—use the project wrappers.

**Windows (PowerShell/cmd)**

```bash
.\run.bat install    # setup env
.\run.bat start      # run app
.\run.bat test       # run tests
.\run.bat analyze    # flake8/lizard/etc.
.\run.bat build      # build exe
```

**Linux/macOS**

```bash
./run.sh install
./run.sh start
./run.sh test
./run.sh build
```

---

## 7) Common Gotchas (quick)

```python
# ✅ connect to Songs signals
self.data.songs.updated.connect(self.refresh_ui)
self.data.songs.listChanged.connect(self.rebuild_list)

# ✅ queue workers
self.worker_queue.add_task(SomeWorker(params))

# ❌ per-object signals from actions
# ❌ direct threading
```

---

## 8) Code Quality Gate (quick)

* Run `run.bat analyze`; fix CCN > 15, very long functions, style and import warnings.
* Ensure **no `Dict[str, Any]` in core logic**; model with dataclass/pydantic.
* Verify filename matches responsibility; split if mixed.

---

## 9) Task Report (add to PR)

* **Summary:** 1–2 lines of what/why.
* **Changed files:** list exact paths.
* **Deleted files:** list exact paths.
  *(Optional)* Created / Moved (`old → new`).
* **Tests & results:** updated/added and pass status.
* **Docs:** which pages updated (integrated, not appended dumps).

---

## 10) CHANGELOG & Release Notes Format

**Always use one-liner format with category prefix:**

**Categories:**
- `New:` - New features, capabilities, or additions
- `Fix:` - Bug fixes, error corrections
- `Chore:` - Maintenance, refactoring, dependencies, tooling
- `Change:` - Modifications to existing behavior

**Format Rules:**
- One line per change, 120 chars max
- Start with category prefix
- Be specific but concise
- Use active voice, present tense
- Include key details in parentheses if needed

**Examples:**
```markdown
### Added
- New: Resizable UI panels with drag splitters (song list, waveform, task/log views)
- New: Smart startup dialog auto-checks "Don't show again" when system configured

### Fixed
- Fix: MDX gap detection for late expected gaps (distance-based band gating)
- Fix: UI freezes during gap detection (media player unloads before processing)

### Changed
- Chore: Config schema added `main_splitter_pos` to Window section
- Chore: Fixed 56 type errors for better IDE support
```

**Apply to:**
- `CHANGELOG.md` - All RC and release entries
- `docs/releases/vX.Y.Z.md` - Release notes

---

## 11) Commit Message Format

**Always start commit messages with category prefix matching CHANGELOG format:**

**Format:** `<Category>: <imperative description>`

**Categories:**
- `New:` - New features, capabilities, or additions
- `Fix:` - Bug fixes, error corrections
- `Chore:` - Maintenance, refactoring, dependencies, tooling
- `Change:` - Modifications to existing behavior

**Rules:**
- One line, imperative mood, 72 chars max
- Capitalize after colon
- No period at end
- Be specific about what changed

**Examples:**
```
Fix: MDX gap detection for late expected gaps and prevent UI freezes
New: Watch mode for real-time song monitoring with auto-reload
Chore: Upgrade pytest to 8.0 and fix deprecated warnings
Change: Media player now auto-unloads when detection starts
```

---

## 12) Pre-Commit Checklist

**MANDATORY before every commit:**

1. **Run tests:** `.\run.bat test` (Windows) or `./run.sh test` (Linux/macOS)
   - **ALL tests must pass** - no exceptions
   - If tests fail, **FIX THEM FIRST** before committing
   - Update tests if behavior intentionally changed
2. **Propose commit message** using format from section 11
3. Only then proceed with `git add` and `git commit`

**If you commit with failing tests, IMMEDIATELY:**
- Fix the failing tests
- Commit the fix with: `Fix: Update tests to match <changed behavior>`


---

## 0) Do-First Checklist

* Scan `src/actions/`, `src/ui/`, `src/services/`, `src/model/`, `tests/` to **reuse** patterns.
* If a similar feature exists, **extend it**; don’t re-implement.
* Plan the **smallest change** that fits existing structure.

---

## 1) Core Rules

* **No backward-compat code.** Don’t keep legacy shims/flags/APIs—modernize instead.
* **One source of truth.** Edit in place; don’t create parallel files.
* **Keep it simple.** Early returns > deep nesting; avoid workaround branches.
* **Strong types & clean interfaces:** prefer `@dataclass` / `pydantic` / Protocols over `Dict[str, Any]`.
  Avoid `hasattr/getattr`—define a proper interface.
* **File naming & responsibility:** filenames must reflect content; each file does **one** thing.
  If purpose changes, **rename**; if mixed concerns, **split**.
* **Size triggers:** propose refactor if file > ~500 lines or function > ~80–100 lines.

---

## 2) Architecture Rules (AppData + Actions + Signals + Workers)

* **DI via `AppData`:** access `config`, `songs`, `worker_queue`, `selected_songs`.
* **Actions pattern:** classes inherit from `BaseActions(data: AppData)` and delegate to specialized modules.
* **Signals:**

  * ✅ `self.data.songs.updated.emit(song)` (model changed)
  * ✅ `self.data.songs.listChanged.emit()` (list structure changed)
  * ❌ No direct per-object signals from actions.
* **Workers:** queue only

  * ✅ `self.worker_queue.add_task(worker)`
  * ❌ No `threading.Thread(...)` directly.

---

## 3) File & Docs Management

* **Prefer extending existing files.** Only add new files if necessary.
* If replacing, **rename/reuse** (don’t keep old + new).
* **Docs:** integrate updates into existing pages.
  Temporary plans/notes → put in `temp/` and clean up.
* **Imports:** snake_case dirs; e.g., `from model.song import Song`.
* **No side effects at import time.**

---

## 4) Coding Standards (short version)

* **KISS, DRY, SRP.** Small, single-purpose functions; minimize branching/side-effects.
* **Errors:** raise typed exceptions; no silent `except:`; log with context.
* **PEP 8 (120 cols), 4-space indent, grouped imports, no unused imports.**
* **Types:** add type hints; normalize external data to typed models at the boundary.
* **Performance:** avoid repeated heavy ops; reuse/cache when safe.

---

## 5) Testing Strategy

* **Always test changes.** Use wrapper scripts only.
* **Prefer extending existing tests**; add new files only if coverage is missing.
* **When unit tests suffice:** parsing/validation, prompt/formatting, selection/routing logic, pure services.
* **When integration tests needed:** Demucs/ffmpeg piping, worker queue behavior, signals/UI sync, real file IO paths.
* **Mocking:** e.g., `patch('actions.module.Service')`.
* **Naming:** `tests/test_*.py`; temporary experiments go to `temp/` and are cleaned.

---

## 6) Commands (use wrappers only)

> **Never** run `python`/`pytest` directly—use the project wrappers.

**Windows (PowerShell/cmd)**

```bash
.\run.bat install    # setup env
.\run.bat start      # run app
.\run.bat test       # run tests
.\run.bat analyze    # flake8/lizard/etc.
.\run.bat build      # build exe
```

**Linux/macOS**

```bash
./run.sh install
./run.sh start
./run.sh test
./run.sh build
```

---

## 7) Common Gotchas (quick)

```python
# ✅ connect to Songs signals
self.data.songs.updated.connect(self.refresh_ui)
self.data.songs.listChanged.connect(self.rebuild_list)

# ✅ queue workers
self.worker_queue.add_task(SomeWorker(params))

# ❌ per-object signals from actions
# ❌ direct threading
```

---

## 8) Code Quality Gate (quick)

* Run `run.bat analyze`; fix CCN > 15, very long functions, style and import warnings.
* Ensure **no `Dict[str, Any]` in core logic**; model with dataclass/pydantic.
* Verify filename matches responsibility; split if mixed.

---

## 9) Task Report (add to PR)

* **Summary:** 1–2 lines of what/why.
* **Changed files:** list exact paths.
* **Deleted files:** list exact paths.
  *(Optional)* Created / Moved (`old → new`).
* **Tests & results:** updated/added and pass status.
* **Docs:** which pages updated (integrated, not appended dumps).

---

## 10) Final Steps

1. `run.bat test` must pass.
2. Propose a **one-line, imperative** commit message, e.g.
   *“Refactor gap detection actions to use typed models and Songs signals”*.
