# Performance Issues Analysis - UI Freezing Problems

**Date**: October 12, 2025  
**Severity**: High - Application freezes on normalize and filter operations  
**Impact**: Core user operations (normalize audio, filter songs) cause complete UI freeze

## Reported Issues

1. **Normalize Button**: Clicking "Normalize" causes application to freeze
2. **Status Filter**: Selecting a status filter causes application to freeze

## Root Cause Analysis

### Issue 1: Normalize Operation Blocking UI Thread

**Location**: `src/actions/audio_actions.py` - `normalize_song()` method (line 27)

**Problem**: The normalize operation triggers a chain of synchronous operations that block the UI:

```python
def normalize_song(self):
    selected_songs = self.data.selected_songs
    # ...
    if len(selected_songs) == 1:
        self._normalize_song_if_valid(selected_songs[0], True)
    else:
        for song in selected_songs:
            self._normalize_song_if_valid(song, False)
```

**Freeze Trigger Chain**:
1. `normalize_song()` → calls `_normalize_song()` for each song
2. `_normalize_song()` → creates `NormalizeAudioWorker` 
3. Worker emits `finished` signal
4. **BLOCKING**: `finished.connect(lambda: self.song_actions.reload_song(specific_song=song))`
5. `reload_song()` → creates `ReloadSongWorker` and starts immediately (`add_task(worker, True)`)
6. `ReloadSongWorker` loads entire song data synchronously
7. Emits `songReloaded` signal
8. Updates UI model → triggers table refresh for **ALL** visible rows

**Why It Freezes**:
- Each normalize operation triggers a full song reload
- Song reload is synchronous and loads all song data from disk
- Multiple songs = multiple sequential reloads
- Each reload triggers Qt model update → UI repaints
- No batching or throttling of UI updates
- Main thread is blocked waiting for file I/O operations

### Issue 2: Filter Operation Triggering Full Table Scan

**Location**: `src/ui/songlist/songlist_widget.py` - `updateFilter()` method (line 91)

**Problem**: Filter changes trigger expensive operations on the main UI thread:

```python
def updateFilter(self):
    self.proxyModel.selectedStatuses = self.songs_model.filter
    self.proxyModel.textFilter = self.songs_model.filter_text.lower()
    self.proxyModel.invalidateFilter()  # ← BLOCKING OPERATION
    self.updateCountLabel()
```

**Freeze Trigger Chain**:
1. User changes filter → `Songs.filter` setter called
2. Emits `filterChanged` signal
3. `updateFilter()` called synchronously on main thread
4. **BLOCKING**: `proxyModel.invalidateFilter()` forces immediate re-evaluation of **ALL** rows
5. For each row, calls `filterAcceptsRow()` which:
   - Accesses song properties
   - Performs string comparisons (lowercase)
   - May access cache or compute values on-demand
6. Large song lists (>1000 songs) = seconds of UI freeze

**Location**: `src/ui/songlist/songlist_widget.py` - `filterAcceptsRow()` method (line 23)

```python
def filterAcceptsRow(self, source_row, source_parent):
    song: Song = self.sourceModel().songs[source_row]
    
    statusMatch = song.status.name in self.selectedStatuses if self.selectedStatuses else True
    
    # Cache lookup or fallback to expensive lowercase conversion
    if hasattr(source_model, '_row_cache') and song.path in source_model._row_cache:
        cache_entry = source_model._row_cache[song.path]
        textMatch = (self.textFilter in cache_entry['artist_lower'] or 
                    self.textFilter in cache_entry['title_lower'])
    else:
        # EXPENSIVE: Called for every row on every filter change
        textMatch = self.textFilter in song.artist.lower() or self.textFilter in song.title.lower()
    
    return statusMatch and textMatch
```

## Architecture Issues

### 1. **Synchronous Signal-Slot Chains**
- Signals are connected synchronously (default Qt behavior)
- One user action triggers cascade of immediate operations
- No async/await or deferred execution patterns
- Main thread blocked during entire operation chain

### 2. **Missing UI Thread Protection**
- Worker queue exists but not used effectively
- Reload operations happen on worker thread but signal handling is synchronous
- No QTimer-based deferred updates
- No batching of model updates

### 3. **Inefficient Model Updates**
- Each song update emits `Songs.updated` signal
- Signal directly connected to Qt model
- Qt model triggers row update → view repaint
- No update batching or throttling
- Multiple rapid updates = multiple repaints

### 4. **Filter Implementation**
- `QSortFilterProxyModel.invalidateFilter()` is synchronous and blocks
- Re-evaluates ALL rows immediately
- No pagination or virtual scrolling optimization
- Large datasets cause proportional freeze time

### 5. **Cache Misses**
- Row cache (`_row_cache`) may not be populated when filter runs
- Fallback to expensive operations (lowercase conversion, string matching)
- Cache invalidation strategy unclear

## Performance Impact

**Normalize Operation** (1 song):
- File I/O: ~50-200ms (read song files from disk)
- Song reload: ~100-500ms (parse USDX file, load metadata)
- Model update: ~10-50ms per visible row
- Total: **~200-1000ms freeze per song**

**Normalize Operation** (10 songs):
- Sequential processing: 10x single song time
- Total: **~2-10 seconds freeze**

**Filter Operation** (1000 songs):
- filterAcceptsRow() called 1000 times
- String operations: ~0.1-0.5ms per row
- Total: **~100-500ms freeze**

**Filter Operation** (5000+ songs):
- Total: **~500ms-2.5s freeze**

## Recommended Solutions

### Immediate Fixes (Low Effort, High Impact)

1. **Defer Filter Updates**
   ```python
   def updateFilter(self):
       self.proxyModel.selectedStatuses = self.songs_model.filter
       self.proxyModel.textFilter = self.songs_model.filter_text.lower()
       
       # Defer invalidation to next event loop iteration
       QTimer.singleShot(0, self.proxyModel.invalidateFilter)
       QTimer.singleShot(10, self.updateCountLabel)
   ```

2. **Batch Model Updates**
   ```python
   # In Songs model
   def batch_update(self, songs: List[Song]):
       """Update multiple songs with single signal emission"""
       for song in songs:
           # Update internal state without emitting
           pass
       # Emit once after all updates
       self.listChanged.emit()
   ```

3. **Throttle Reload Operations**
   ```python
   # Don't reload immediately after normalize
   # Use a timer to batch multiple normalizations
   def _normalize_song(self, song: Song, start_now=False):
       worker = NormalizeAudioWorker(song)
       # Remove immediate reload connection
       # worker.signals.finished.connect(lambda: self.song_actions.reload_song(specific_song=song))
       
       # Instead, queue reload for later
       worker.signals.finished.connect(lambda: self._schedule_reload(song))
   ```

### Medium-Term Fixes (Moderate Effort, High Impact)

4. **Use Qt Concurrent for Filter Operations**
   ```python
   from PySide6.QtCore import QRunnable, QThreadPool
   
   class FilterTask(QRunnable):
       def run(self):
           # Run filtering in thread pool
           pass
   ```

5. **Implement Progressive Loading**
   - Already have chunked loading infrastructure (`CHUNK_SIZE`, `_append_next_chunk`)
   - Apply same pattern to filter results
   - Show first 500 filtered results immediately
   - Load rest progressively

6. **Add Debouncing to Filter**
   ```python
   def updateFilter(self):
       # Cancel pending filter update
       if hasattr(self, '_filter_timer'):
           self._filter_timer.stop()
       
       # Debounce filter by 150ms
       self._filter_timer = QTimer.singleShot(150, self._apply_filter)
   ```

### Long-Term Fixes (High Effort, Highest Impact)

7. **Implement Virtual Scrolling**
   - Only render visible rows
   - Use QTableView's built-in virtual scrolling properly
   - Implement data fetch on-demand

8. **Pre-compute Filter Indices**
   - Maintain filtered index in background thread
   - Swap indices when ready
   - No UI thread blocking

9. **Separate UI and Data Layers**
   - Move all file I/O to worker threads
   - Use message queue pattern
   - UI only consumes pre-processed data

10. **Optimize Song Reload**
    - Don't reload entire song after normalize
    - Only update normalized flag
    - Defer full reload until user selects song

## Code Locations Requiring Changes

### Critical (Immediate):
1. `src/ui/songlist/songlist_widget.py:91` - `updateFilter()` 
2. `src/actions/audio_actions.py:57` - `_normalize_song()` reload connection
3. `src/model/songs.py:62` - Add batch update method

### Important (Medium-term):
4. `src/ui/songlist/songlist_widget.py:23` - `filterAcceptsRow()` optimization
5. `src/actions/song_actions.py:22` - `reload_song()` make async-friendly
6. `src/ui/songlist/songlist_model.py:154` - `data()` method caching

### Nice-to-Have (Long-term):
7. Entire model/view architecture refactor
8. Worker queue priority system
9. Global update throttling mechanism

## Testing Recommendations

1. **Load Test**: Test with 5000+ songs
2. **Filter Test**: Rapid filter changes
3. **Normalize Test**: Normalize 50+ songs at once
4. **Concurrent Test**: Normalize while filtering
5. **Memory Test**: Monitor for memory leaks during rapid updates

## Measurements Needed

Before implementing fixes, measure:
- Time spent in `invalidateFilter()`
- Time spent in `filterAcceptsRow()` per row
- Number of `Songs.updated` signals per normalize operation
- Qt event queue depth during freeze
- Main thread CPU usage during operations

## References

- Qt Performance: https://doc.qt.io/qt-6/performance.html
- QSortFilterProxyModel: https://doc.qt.io/qt-6/qsortfilterproxymodel.html
- Qt Concurrent: https://doc.qt.io/qt-6/qtconcurrent-index.html
- Signal/Slot Performance: https://doc.qt.io/qt-6/signalsandslots.html

---

**Conclusion**: The freezing is caused by synchronous operations on the UI thread, particularly filter invalidation and cascading reload operations. Quick wins are available by deferring operations with QTimer and batching updates. Full solution requires architectural changes to move heavy operations off the main thread.
