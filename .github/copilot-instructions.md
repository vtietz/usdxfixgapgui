# GitHub Copilot Instructions — USDXFixGap

**Project:** Python/PySide6 GUI for UltraStar song gap detection (Demucs + ffmpeg).
**Current Version:** v2.0.0 (in development)

⚠️ **DO NOT bump version numbers** - Maintainer controls versioning manually.

**Read First:** `docs/architecture.md` (includes signal patterns), `docs/coding-standards.md`.

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
build.bat            # build exe
```

**Linux/macOS**

```bash
./run.sh install
./run.sh start
./run.sh test
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
