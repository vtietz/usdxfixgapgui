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
  Use code examples and snippets very rarely - better never.
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
# GitHub Copilot Instructions — USDXFixGap (Concise)

**Project:** Python/PySide6 GUI for UltraStar gap detection (Demucs + ffmpeg)

⚠️ **Never bump version numbers** – maintainer controls `VERSION` and releases.

Read first: `docs/architecture.md`, `docs/coding-standards.md`.

---
## Core Workflow
1. Reuse patterns from `src/actions/`, `src/services/`, `src/ui/`, `src/model/`, `tests/`.
2. Extend existing code; avoid parallel replacements.
3. Plan the smallest change; early returns over deep nesting.

## Architecture Essentials
- Access shared state via `AppData` (config, songs, worker_queue, selected_songs).
- Actions: subclass `BaseActions` and delegate; never emit per-object signals.
- Signals: use `songs.updated.emit(song)` (model change) and `songs.listChanged.emit()` (list mutation).
- Workers: enqueue (`worker_queue.add_task(worker)`), no manual threads.

## Coding Standards (Snapshot)
- Strong typing: dataclasses / pydantic / Protocols; no raw `Dict[str, Any]` in core.
- One file = one responsibility; rename when purpose changes.
- Refactor threshold: file > ~500 lines or function > ~80–100 lines.
- Avoid `hasattr` probing; define interfaces.
- Log typed exceptions; no bare `except:`.
- 120 col limit, grouped imports, remove unused.

## Logging Rules
- **Parameterized format:** Use `logger.debug("msg %s", var)` NOT `logger.debug(f"msg {var}")`.
- **Why:** Deferred formatting (performance when log level disabled), avoids F541 lint, structured logging support, consistency.
- **Refactor on sight:** Convert f-string loggers to parameterized style when editing nearby code.
- **Plain strings OK:** If no variables, use plain string `logger.info("Starting process")` (no f-prefix needed).

## Testing
- Use wrappers: `run.bat test` / `run.sh test` (never direct `pytest`).
- Extend existing tests; add only when missing coverage.
- Unit: pure logic (parsing, selection, formatting). Integration: Demucs/ffmpeg, workers, UI+signals, file IO.
- Name tests `tests/test_*.py`; temporary experiments → `temp/`.

## Commands (Wrappers Only)
```bash
run.bat install | start | test | analyze | build
run.sh   install | start | test | build
```

## Common Gotchas
```python
self.data.songs.updated.connect(self.refresh_ui)
self.data.songs.listChanged.connect(self.rebuild_list)
self.worker_queue.add_task(worker)         # ✅
# ❌ Direct threading
# ❌ Per-object custom signals
```

## Quality Gate
- `run.bat analyze`: fix complexity >15, long functions, style warnings.
- No orphan `Dict[str, Any]` – use models.
- Ensure filename matches content.

## PR Task Report
- Summary (1–2 lines why/change)
- Changed / Deleted files (exact paths)
- Tests added/updated + status
- Docs updated (integrated edits only)

## Changelog & Release Notes
Categories: `New:` `Fix:` `Chore:` `Change:` (one line, ≤120 chars). Active voice.
Example:
```
New: Resizable waveform/task panels
Fix: Prevent UI freeze during gap detection (player unload timing)
Chore: Add splitter position to config schema
Change: Startup dialog forces GPU activation prompt when pack present
```

## Commit Message Format
`<Category>: <Imperative description>` (<=72 chars, no period)
Examples:
```
Fix: Handle late expected gaps in MDX detection
New: Watch mode auto-reloads modified songs
Chore: Upgrade pytest and fix deprecations
Change: Auto-unload media player before MDX run
```

## Pre-Commit Checklist
1. Run tests – all must pass.
2. Stage changes; draft commit message.
3. If tests fail, fix + retest before commit.
4. If tests updated due to intentional behavior change, mention it.

## Task Completion Report
After completing any task, provide a one-line commit message using the format:
`<Category>: <Imperative description>` (≤72 chars, no period)

Example: `Fix: Preserve USDB ID when reloading songs from disk`

## GPU & Performance (Summary)
- CPU torch bundled; GPU Pack optional (demucs speedup 5–10x).
- Bootstrap loads GPU Pack early; falls back cleanly to CPU if validation fails.
- No forced torch re-import if already loaded (stability > aggressiveness).

## Final Steps for Any Change
1. `run.bat test` green.
2. Provide concise commit + PR task report.
3. Avoid scope creep; list larger ideas as follow-ups.

---
**Remember:** Keep changes focused, typed, and aligned with existing patterns.
* **When integration tests needed:** Demucs/ffmpeg piping, worker queue behavior, signals/UI sync, real file IO paths.
