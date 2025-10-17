# Instant Task Lane Architecture

## Overview

USDXFixGap uses a dual-lane task scheduling system to provide responsive UI while processing long-running operations:

- **Standard Lane**: Sequential processing of heavy tasks (gap detection, normalization, scan all songs)
- **Instant Lane**: Immediate execution of user-triggered tasks (waveform creation, light reload)

## Architecture

### Two-Lane Concurrency Model

```
┌─────────────────────────────────────────────────────────┐
│ WorkerQueueManager                                      │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Standard Lane (Sequential)        Instant Lane        │
│  ┌────────────────────┐            ┌────────────┐     │
│  │ queued_tasks[]     │            │ queued_    │     │
│  │                    │            │ instant_   │     │
│  │ [Task3, Task4...]  │            │ tasks[]    │     │
│  └────────────────────┘            │            │     │
│           │                        │ [Task1...] │     │
│           ↓                        └────────────┘     │
│  ┌────────────────────┐                   │           │
│  │ running_tasks{}    │                   ↓           │
│  │                    │            ┌────────────┐     │
│  │ {id: Task2}        │            │ running_   │     │
│  │                    │            │ instant_   │     │
│  │ (max 1)            │            │ task       │     │
│  └────────────────────┘            │            │     │
│                                    │ Task1      │     │
│                                    │            │     │
│                                    │ (max 1)    │     │
│                                    └────────────┘     │
│                                                         │
│  At most: 1 standard + 1 instant running concurrently  │
└─────────────────────────────────────────────────────────┘
```

### Task Classification

**Standard Tasks (`is_instant=False`)**:
- **DetectGap**: AI-powered gap detection
- **NormalizeAudio**: Audio normalization
- **LoadAllSongs**: Batch song scanning
- **SeparateAudio**: Vocal separation (Demucs)

**Instant Tasks (`is_instant=True`)**:
- **CreateWaveform**: Waveform image generation (selected song only)
- **LightReload** (future): Metadata-only reload without status changes

## Implementation Details

### IWorker Base Class

```python
class IWorker(QObject):
    def __init__(self, is_instant: bool = False):
        super().__init__()
        self.is_instant = is_instant  # Classifies task for scheduler
        # ... other initialization
```

### WorkerQueueManager Scheduling

```python
def add_task(self, worker: IWorker, start_now=False):
    if worker.is_instant:
        # Route to instant lane
        self.queued_instant_tasks.append(worker)
        if start_now and self.running_instant_task is None:
            self.start_next_instant_task()
    else:
        # Route to standard lane
        self.queued_tasks.append(worker)
        if start_now or not self.running_tasks:
            self.start_next_task()
```

### Concurrency Guarantees

1. **Standard lane**: Maximum 1 task running at a time (sequential)
2. **Instant lane**: Maximum 1 task running at a time
3. **Combined**: Maximum 1 standard + 1 instant = 2 tasks total
4. **Isolation**: Lanes don't block each other

### start_now Parameter Semantics

- **Standard tasks**: `start_now=True` starts immediately if no standard task is running
- **Instant tasks**: `start_now=True` starts immediately if no instant task is running
- **Typical usage**: Instant tasks always use `start_now=True` for immediate execution

## Usage Patterns

### Creating Instant Waveform Task

```python
# In AudioActions._create_waveform()
worker = CreateWaveform(
    song,
    config,
    audio_file,
    waveform_file,
    is_instant=True  # Mark as instant
)
self.worker_queue.add_task(worker, start_now=True)  # Execute immediately
```

### Preventing Mass Waveform Generation

```python
# In SongActions._on_song_loaded()
# DO NOT create waveforms automatically - prevents viewport churn
# Waveforms only created when:
# 1. User selects song (MediaPlayerComponent.on_song_changed)
# 2. Gap detection completes (GapActions)
```

### Selected Song Waveform Creation

```python
# In MediaPlayerComponent.on_song_changed()
if not WaveformPathService.waveforms_exists(song, tmp_path):
    audio_actions._create_waveforms(
        song, 
        overwrite=False, 
        use_queue=True  # Uses instant lane with start_now=True
    )
```

## Status Discipline

**Critical Rule**: Instant tasks MUST NOT change `Song.status`

- `Song.status` only changes from:
  - Gap detection (DetectGap worker)
  - Normalization (NormalizeAudio worker)
  - Error conditions (set_error/clear_error)

- Instant tasks preserve status:
  - Light reload: Loads metadata, keeps status unchanged
  - Waveform creation: Generates images, keeps status unchanged

## Behavioral Scenarios

### Scenario 1: User Clicks Song During Gap Detection

1. **User action**: Clicks song in list
2. **Instant task**: CreateWaveform queued, starts immediately
3. **Standard task**: DetectGap continues running (unaffected)
4. **Result**: Waveform appears ~1s, gap detection completes ~10s later
5. **Status**: Preserved from gap detection, not touched by waveform

### Scenario 2: User Scrolls Through Songs

1. **User action**: Scrolls viewport, loads 20 songs
2. **Viewport loading**: Uses `reload_song_light()` with `run_async` (non-blocking)
3. **No tasks queued**: Light reload doesn't use WorkerQueueManager
4. **No waveforms created**: `_on_song_loaded()` guard prevents mass generation
5. **Status**: All songs remain `NOT_PROCESSED`
6. **UI responsiveness**: Selection is instant; metadata loads asynchronously in background

### Scenario 3: Rapid Song Selection

1. **User action**: Clicks multiple songs quickly
2. **First click**: CreateWaveform starts in instant lane
3. **Second click**: CreateWaveform queued (instant slot occupied)
4. **Third click**: Deduplicated by in-flight guard (if same song)
5. **Result**: Tasks execute sequentially in instant lane, UI stays responsive

## Testing

### Manual Test: Instant + Standard Concurrency

```bash
# Start gap detection (standard lane)
1. Select a song
2. Click "Detect Gap"
3. Observe: Task Queue shows "Detecting gap..."

# Immediately select different song (instant lane)
4. Click another song in list
5. Observe: Waveform creation starts immediately
6. Observe: Both tasks run in parallel
7. Verify: Waveform appears within 1-2 seconds
8. Verify: Gap detection completes independently
```

### Test: No Mass Waveform Generation

```bash
1. Load folder with 100+ songs
2. Scroll rapidly through song list
3. Observe: Task Queue remains empty (no waveform tasks)
4. Verify: Status remains NOT_PROCESSED for all songs
5. Click a single song
6. Verify: Only 2 waveform tasks appear (audio + vocals)
```

## Migration Notes

### Existing Workers

All existing workers default to `is_instant=False` (standard lane):
- `DetectGap`
- `NormalizeAudio`
- `LoadAllSongs`
- `SeparateAudio`

Behavior unchanged - they continue to run sequentially.

### New Instant Workers

`CreateWaveform` now defaults to `is_instant=True`:
```python
class CreateWaveform(IWorker):
    def __init__(self, ..., is_instant: bool = True):
        super().__init__(is_instant=is_instant)
```

Can be overridden if needed for batch operations.

## Performance Impact

### Before Instant Lane

- User clicks song → Full reload queued → Waits for gap detection to finish
- Result: 10+ second delay before waveform appears
- UI feels unresponsive during heavy operations

### After Instant Lane

- User clicks song → Waveform creation starts immediately in parallel
- Result: ~1 second delay for waveform, independent of other tasks
- UI stays responsive during gap detection

### Memory/CPU Impact

- **CPU**: 2 tasks running simultaneously (1 heavy + 1 light)
- **Memory**: Minimal increase (waveform generation is lightweight)
- **I/O**: No contention (different files accessed)
- **Overall**: Acceptable trade-off for improved UX

## Async Conversion

### reload_song_light() Non-Blocking Pattern

**Problem**: `reload_song_light()` previously used `run_sync()`, blocking the GUI thread during file I/O.

**Solution**: Converted to `run_async()` with callback pattern:

```python
# Before (blocking):
reloaded_song = run_sync(song_service.load_song_metadata_only(song.txt_file))
# ... apply changes directly ...

# After (non-blocking):
run_async(
    song_service.load_song_metadata_only(song.txt_file),
    callback=lambda reloaded_song, s=song: self._apply_light_reload(s, reloaded_song)
)
```

**Benefits**:
- Song selection is instant (UI updates immediately)
- Metadata loads asynchronously in background thread
- No GUI freeze on clicking songs
- Works with Qt event loop via `QTimer.singleShot(0)` deferral

### Encoding Detection for International Characters

**Problem**: Files with German umlauts (ä, ö, ü) or special characters failed to load:
```
UnicodeDecodeError: 'utf-8' codec can't decode byte 0xe4 in position 12
```

**Solution**: `load_notes_only()` now detects encoding before reading:

```python
async def load_notes_only(usdx_file: USDXFile) -> List[Note]:
    # Detect encoding if not already set
    if usdx_file.encoding is None:
        await USDXFileService.determine_encoding(usdx_file)
    
    # Use async I/O with detected encoding
    async with aiofiles.open(usdx_file.filepath, 'r', encoding=usdx_file.encoding) as f:
        lines = await f.readlines()
    # ... parse notes ...
```

**Encoding Detection Order**: UTF-8 → UTF-16 → UTF-32 → cp1252 → cp1250 → latin-1 → windows-1252 → iso-8859-1

## Future Enhancements

### Potential Instant Tasks

1. **Quick Metadata Update**: Update song tags without full reload
2. **Thumbnail Generation**: Create cover art thumbnails on selection

### Priority System

Future extension: Add priority to instant tasks
- High priority: User-clicked waveform
- Medium priority: Viewport prefetch
- Low priority: Background cache warming

## References

### Key Files

- **Worker Framework**: `src/managers/worker_queue_manager.py`
- **Instant Task Example**: `src/workers/create_waveform.py`
- **Waveform Actions**: `src/actions/audio_actions.py`
- **Media Player Integration**: `src/ui/mediaplayer/component.py`
- **Viewport Guard**: `src/actions/song_actions.py` (`_on_song_loaded`)

### Related Docs

- `docs/architecture.md`: Overall system architecture
- `docs/signals.md`: Signal flow and communication
- `docs/coding-standards.md`: Development patterns
