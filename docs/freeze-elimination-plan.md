# Implementation Plan: Eliminate UI Freezes During Song Selection

**Status:** Planning  
**Priority:** High  
**Created:** 2025-10-22

## Problem Statement

When playing vocals and selecting another song, the UI freezes. This occurs because:
- Long-running MDX separation blocks the main thread
- GPU operations happen synchronously on the UI thread
- Audio playback resources aren't released before starting new operations
- Waveform generation and disk I/O block selection transitions
- Rapid selection changes create overlapping, uncancellable tasks

## Goals

- Keep the UI thread responsive during all song selection transitions
- Ensure long-running MDX separation, waveform generation, disk I/O, and GPU work run in isolated workers with cooperative cancellation
- Prevent resource leaks (audio device, GPU memory, file locks) and stale results when switching songs rapidly
- Provide clear observability (logs, metrics) to confirm no blocking on the main thread

---

## Phase 0 — Instrumentation and Watchdog

**Goal:** Detect and measure UI stalls before fixing them.

### Tasks

1. **Main-thread heartbeat watchdog**
   - Add a periodic tick scheduled on the UI loop
   - If ticks stop arriving for > 2 seconds, log "UI stall" with context
   - Place setup early in `src/usdxfixgap.py`
   - Use UI framework's timer (PySide6: `QTimer`) to avoid extra threads

2. **Structured logging with correlation IDs**
   - On every song selection, generate a `selection_id`
   - Include `selection_id` in all logs across UI, actions, services, MDX, cache
   - Extend logging utilities in `src/utils/logging_utils.py` (create if needed)
   - Emit JSON-style log lines with context dicts

3. **Add timing spans across selection lifecycle**
   - Entry in UI model: `src/ui/songlist/songlist_model.py`
   - Actions layer: `src/actions/core_actions.py`
   - MDX provider/pipeline: `src/utils/providers/mdx_provider.py`, `src/utils/providers/mdx/scanner/pipeline.py`
   - Caching: `src/utils/providers/mdx/vocals_cache.py`
   - Waveform: `src/utils/waveform.py`, `src/utils/waveform_json.py`

### Acceptance Criteria

- Logs show consistent `selection_id` propagation
- Heartbeat alerts fire only under synthetic blocking
- Timers indicate which step stalls if any

---

## Phase 1 — UI Reentrancy Guard and Debounce

**Goal:** Prevent overlapping transitions and collapse rapid selection storms.

### Tasks

1. **Reentrancy guard**
   - Keep state: `transition_in_progress` and `latest_requested_song`
   - If new selection arrives during transition, mark pending
   - Drain pending request once current transition completes
   - Implement in `src/ui/songlist/songlist_model.py`

2. **Debounce rapid selections**
   - Add 150–300ms debounce window
   - Collapse rapid arrow key / mouse wheel events
   - Enqueue only last selection within debounce window
   - Implement at UI layer

### Acceptance Criteria

- Rapid selections no longer start overlapping transitions
- Logs show collapsed requests
- UI remains responsive during debounce

---

## Phase 2 — SongTaskManager Orchestrator

**Goal:** Central orchestrator to own per-song task lifecycle.

### Tasks

1. **Create dedicated service**
   - New module: `src/services/song_task_manager.py`
   - Responsibilities:
     - Maintain single "active transition" with cancellation token
     - Sequence subtasks: stop-playback → load metadata → workers → integrate
     - Guard against stale results (only apply if `selection_id` matches)
     - Expose `cancel_active_then_start(song)` API

2. **State machine transitions**
   - Clear logging of state changes
   - No overlapping worker sets
   - Stale outputs discarded

### Acceptance Criteria

- Clear state machine transitions in logs
- No overlapping worker sets
- Stale outputs discarded based on `selection_id`

---

## Phase 3 — Background Workers (Process Preferred)

**Goal:** Isolate CPU/GPU-heavy work from UI thread.

### Tasks

1. **Process worker pool**
   - Use OS process workers for MDX separation (GPU-bound)
   - Size: 1–2 workers
   - Use `spawn` on Windows for clean isolation
   - Threads acceptable only for lightweight I/O

2. **Communication design**
   - Use queues/pipes for IPC
   - Return incremental progress + final artifacts
   - Attach `selection_id` to all messages
   - Bound execution with timeouts

3. **Cancellation protocol**
   - Send cancellation token on cancel
   - If unresponsive, escalate to hard termination (Phase 5)

### Touch Points

- `src/utils/providers/mdx/separator.py`
- `src/utils/providers/mdx/scanner/pipeline.py`
- `src/utils/waveform.py`

### Acceptance Criteria

- Workers never run in UI process
- UI thread has no long-running sync calls
- No GPU work on main thread

---

## Phase 4 — Cooperative Cancellation in MDX Pipeline

**Goal:** Enable fast, clean cancellation of in-progress work.

### Tasks

1. **Frequent cancellation checks**
   - Insert checks at chunk boundaries
   - Insert checks in scan loop iterations
   - Early-exit strategy: stop compute ASAP, free intermediates

2. **Honor cancellation in I/O**
   - Check before committing vocals cache writes
   - Check before committing waveform JSON
   - Touch points:
     - `src/utils/providers/mdx/vocals_cache.py`
     - `src/utils/waveform_json.py`
     - `src/utils/providers/mdx/scanner/chunk_iterator.py`
     - `src/utils/providers/mdx/scanner/pipeline.py`

### Acceptance Criteria

- Cancellation stops work within < 500ms (at next chunk boundary)
- No partial artifacts applied
- Memory freed promptly

---

## Phase 5 — Hard Termination Fallback

**Goal:** Handle stuck workers that don't respond to cancellation.

### Tasks

1. **Kill path**
   - If worker doesn't ACK cancel within 5–10s, terminate process
   - Guarantee GPU memory release
   - Close file handles
   - Clear temp files

2. **Health checks**
   - Verify parent process remains healthy
   - No leaked locks or dead threads
   - Recreate worker on next task

### Acceptance Criteria

- Stuck worker killed and replaced
- No cumulative memory growth
- UI unaffected by worker termination

---

## Phase 6 — Audio Playback Stop/Dispose First

**Goal:** Prevent resource conflicts from audio device locks.

### Tasks

1. **Audio session abstraction**
   - New module: `src/services/audio_session.py` (or integrate with current player)
   - Centralize audio lifecycle management

2. **Sequential ordering**
   - Stop playback → cancel workers → start new transition
   - Enforced by `SongTaskManager`

### Acceptance Criteria

- No device or file locks block MDX/cache writes
- Smooth switching while audio playing

---

## Phase 7 — GPU Session Lifecycle Management

**Goal:** Prevent GPU memory leaks and "device busy" errors.

### Tasks

1. **GPU session abstraction**
   - New module: `src/services/gpu_session.py`
   - Own model load, device handle, memory lifecycle
   - Reuse session across compatible tasks

2. **Memory management**
   - Free memory on cancel with library-specific calls
   - Reinitialize session on failure

### Acceptance Criteria

- GPU memory stays within bounds across rapid switches
- No "device busy" errors
- Automatic reinit on failure

---

## Phase 8 — Atomic, Non-Blocking Cache Writes

**Goal:** Prevent corrupted cache files on cancellation.

### Tasks

1. **Atomic write pattern**
   - Write to temp path (unique per `selection_id`)
   - Atomically rename to final path after success
   - Never hold long-lived locks across selections

2. **Update cache helpers**
   - `src/utils/providers/mdx/vocals_cache.py`
   - `src/utils/download/chunk_writer.py`

### Acceptance Criteria

- No corrupted cache files on cancellation
- Concurrent reads see either old or new complete files
- No long-lived locks

---

## Phase 9 — Configuration Knobs

**Goal:** Make behavior tunable with sane defaults.

### Tasks

1. **Add tunables**
   - `debounce_ms` (default: 200)
   - `worker_timeout_ms` (default: 30000)
   - `cancellation_grace_ms` (default: 500)
   - `gpu_release_on_cancel` (default: true)
   - `max_concurrent_workers` (default: 1)
   - `cache_atomic_writes` (default: true)

2. **Documentation**
   - Document in `docs/configuration.md`
   - Wire into existing config loader
   - Add validation (use `tests/test_config_validator.py` pattern)

### Acceptance Criteria

- All knobs user-adjustable
- Validated on load
- Defaults perform well on typical machines

---

## Phase 10 — Tests for Concurrency, Cancellation, Storms

**Goal:** Ensure correctness under stress.

### Tasks

1. **Extend existing tests**
   - Cancellation in MDX: `tests/test_mdx_scanner.py`
   - Gap detection under cancel: `tests/test_gap_detection.py`
   - Atomic writes: `tests/test_downloader.py`, `tests/test_cancellable_process_success.py`

2. **New orchestration tests**
   - Create: `tests/test_song_task_manager.py`
   - Simulate rapid selection storms
   - Confirm reentrancy guards
   - Verify cancellation behavior
   - Check stale result suppression

### Acceptance Criteria

- Tests pass consistently on Windows
- Stress tests with rapid selections don't freeze
- No flaky failures

---

## Phase 11 — Operational Runbook and Observability

**Goal:** Enable diagnosis and tuning in production.

### Tasks

1. **Create runbook**
   - New file: `docs/runbook.md`
   - Content:
     - How to enable verbose logs
     - Interpret `selection_id` traces
     - Detect UI stalls via heartbeat warnings
     - Diagnose GPU memory leaks
     - Diagnose stuck workers
     - Diagnose cache contention
     - Knob adjustment guidance (low-end vs high-end machines)

2. **Add metrics**
   - `stall_count`
   - `cancel_latency_ms`
   - `worker_restart_count`
   - Emit periodically to logs

### Acceptance Criteria

- Runbook enables quick diagnosis
- Metrics show operational health

---

## Rollout Plan

1. **Phase 0–2** (Instrumentation + Guards) — Ship first, observe real behavior
2. **Wait 48 hours** — Collect logs from typical use
3. **Phase 3–5** (Workers + Cancellation) — Roll out isolation layer
4. **Wait 48 hours** — Collect more logs
5. **Phase 6–8** (Audio + GPU + Cache) — Add lifecycle safeguards
6. **Phase 9–11** (Config + Tests + Docs) — Finalize and document

---

## Acceptance Criteria (Overall)

✅ UI remains responsive during/after multiple rapid selections while vocals playing  
✅ No freezes or stalls for ≥5 minutes of stress testing  
✅ Memory footprint stable; GPU memory reclaimed on cancel  
✅ No lingering processes  
✅ No corrupted or partial cache artifacts  
✅ Stale results never applied to wrong selection  
✅ Logs contain consistent `selection_id` traces  
✅ Cancellation latencies below thresholds  

---

## Key Files to Modify or Add

### Modify

- `src/usdxfixgap.py` — heartbeat watchdog, bootstrap logging context
- `src/ui/songlist/songlist_model.py` — debounce and reentrancy guard
- `src/actions/core_actions.py` — route selections through SongTaskManager
- `src/utils/providers/mdx_provider.py` — delegate heavy work to workers, propagate selection_id
- `src/utils/providers/mdx/scanner/pipeline.py` — cooperative cancellation checks
- `src/utils/providers/mdx/scanner/chunk_iterator.py` — cooperative cancellation checks
- `src/utils/providers/mdx/vocals_cache.py` — atomic writes, non-blocking I/O
- `src/utils/download/chunk_writer.py` — atomic writes

### Add

- `src/services/song_task_manager.py` — central orchestrator
- `src/services/audio_session.py` — audio lifecycle abstraction
- `src/services/gpu_session.py` — GPU/model session lifecycle
- `src/utils/logging_utils.py` — structured logging with context (if doesn't exist)
- `tests/test_song_task_manager.py` — orchestration and storm scenarios
- `docs/runbook.md` — operational diagnostics guide

---

## Architecture Diagram

```mermaid
flowchart LR
  UI[UI: Song List] -->|debounced selection| STM[SongTaskManager]
  STM -->|stop playback| Audio[Audio Session]
  STM -->|spawn task: MDX + Waveform| WP[Worker Process]
  WP -->|progress/results + selection_id| STM
  STM -->|apply if selection_id matches| UI
  STM -->|cancel on new selection| WP
  STM -->|GPU handle| GPU[GPU Session]
  WP -->|cache writes (atomic)| Cache[Vocals Cache + Waveform JSON]
  subgraph Observability
    Log[Structured Logs + Heartbeat Watchdog]
  end
  UI --> Log
  STM --> Log
  WP --> Log
  Cache --> Log
```

---

## Risk Mitigations

| Risk | Mitigation |
|------|------------|
| GPU libraries resist cooperative cancellation | Rely on bounded hard termination + fast worker recreation |
| Cache filesystem semantics differ | Use temp+rename strategy (Windows same-volume renames) |
| UI changes break existing behavior | Keep changes minimal, confined to selection handling |
| Worker pool overhead | Start with pool size=1, measure before increasing |
| Debugging becomes harder | Rich logging with selection_id correlation |

---

## Next Steps

**Immediate:** Implement Phase 0 (watchdog + logging) and Phase 1 (debounce + reentrancy guard) to confirm improved responsiveness before adding workers and cancellation.

**Success Metrics:** After Phase 0–1, measure:
- Baseline freeze duration/frequency
- Selection_id trace completeness
- Debounce effectiveness (requests collapsed)

---

## Related Documents

- `docs/architecture.md` — Overall system architecture
- `docs/signals.md` — Signal/slot patterns for async coordination
- `docs/coding-standards.md` — Code quality standards
- `tests/test_worker_queue_manager.py` — Existing worker patterns

---

## Change Log

| Date | Phase | Change |
|------|-------|--------|
| 2025-10-22 | Planning | Initial plan created |
