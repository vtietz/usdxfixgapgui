
## **1. Architecture Overview**

> **📋 Related Documentation:**
> - [Coding Standards](coding-standards.md) - DRY principle, clean code practices, and implementation guidelines

### **Layers**
1. **Models (Data Layer)**:
   - Represents the core data structures of the application (e.g., `Song`, `Songs`).
   - Contains only the data and logic directly related to the data (e.g., validation, derived properties).
   - Should be independent of any UI or framework (e.g., PySide6).

2. **Managers (Controller Layer)**:
   - Acts as intermediaries between the models and other parts of the application (e.g., UI, services).
   - Encapsulates business logic and coordinates operations on models (e.g., managing selected songs, handling worker tasks).
   - Emits signals to notify other components about state changes.
   - Should be reusable and testable.

3. **Services (Business Logic Layer)**:
   - Handles reusable, stateless operations (e.g., file I/O, audio processing, gap detection).
   - Provides functionality that is independent of the application's state.
   - Should not emit signals or depend on the UI.

4. **UI Components (Presentation Layer)**:
   - Handles user interactions and displays data.
   - Connects to signals from managers or view models to update the UI reactively.
   - Should not contain business logic or directly manipulate models.

5. **Application State (Global State Layer)**:
   - Provides a centralized place to manage application-wide state (e.g., `AppData` or `AppState`).
   - Integrates managers and forwards their signals for convenience.
   - Acts as a dependency injection container for managers and services.

### **2. Key Components**

#### **Models**
- **`Song`**:
  - Represents a single song with metadata, audio analysis data, and status.
  - Contains only song-specific logic (e.g., derived properties like `path`).

- **`SongList`** (or `Songs`):
  - A pure data structure for managing a list of `Song` objects.
  - Provides methods for adding, removing, and filtering songs.
  - Does not emit signals or depend on any framework.

#### **Managers**
- **`SongManager`**:
  - Manages song loading, selection, and directory handling.
  - Handles auto-loading from the last directory.
  - Delegates song operations to the `Songs` collection.

- **`WorkerQueueManager`**:
  - Manages worker tasks (e.g., queuing, running, canceling).
  - Emits signals to notify the UI about task progress or completion.
  - Encapsulates worker-related logic to keep it separate from the UI.

- **`WatchModeController`**:
  - Manages file system watching for automatic song reloading.
  - Handles watch mode activation and file change detection.

#### **Services**
- **`SystemCapabilitiesService`**:
  - **Single source of truth for system capabilities** (PyTorch, CUDA, FFmpeg availability).
  - Initialized once at startup via `check()` method with results cached.
  - Provides `SystemCapabilities` dataclass with:
    - `has_torch`, `torch_version`, `torch_error` - PyTorch availability
    - `has_cuda`, `cuda_version`, `gpu_name` - CUDA/GPU detection
    - `has_ffmpeg`, `has_ffprobe`, `ffmpeg_version` - FFmpeg availability
    - `can_detect` - Whether gap detection is possible (requires torch + ffmpeg)
  - Emits `capabilities_changed` signal when refreshed (e.g., after GPU Pack install).
  - Singleton pattern ensures consistent state across application.
  - Usage:
    ```python
    from services.system_capabilities import check_system_capabilities, get_capabilities

    # At startup (with optional progress callback)
    caps = check_system_capabilities(log_callback=dialog.log)

    # Later in application
    caps = get_capabilities()  # Returns cached result
    if caps and caps.can_detect:
        # Proceed with detection
    ```

- **`GapInfoService`**:
  - Handles gap detection logic for songs.
  - Stateless and reusable across the application.

- **`WaveformPathService`**:
  - Manages file paths for waveform generation.
  - Provides utility methods for creating or validating paths.

#### **Application State**
- **`AppData`**:
  - Manages global application state (e.g., `selected_songs`, `is_loading_songs`).
  - Provides access to configuration via lazy-loaded `Config` instance.
  - Forwards signals from the `Songs` collection to simplify access for the UI.
  - Acts as a dependency injection container for managers and services.

#### **UI Components**
- **`TaskQueueViewer`**:
  - Displays the current task queue and its status.
  - Connects to signals from `WorkerManager` to update the UI reactively.

- **`MediaPlayerComponent`**:
  - Handles media playback and waveform visualization.
  - Connects to `SongManager` signals to update the displayed song.

### **3. Signal Flow**

1. **From Managers to UI**:
   - Managers emit signals (e.g., `selected_songs_changed`, `on_task_list_changed`) to notify the UI about state changes.
   - The UI connects to these signals to update itself reactively.

2. **From UI to Managers**:
   - The UI triggers actions (e.g., selecting a song, starting a task) by calling methods on managers.
   - Managers handle the logic and update the models or state as needed.

3. **From Services to Managers**:
   - Services perform stateless operations (e.g., gap detection) and return results to actions.
   - Actions update the models or emit signals based on the results.

4. **Capability Checking Flow** (System Requirements):
   - **Startup**: `SystemCapabilitiesService.check()` called from `StartupDialog`
     - Checks PyTorch availability and version
     - Detects CUDA/GPU if PyTorch available
     - Checks FFmpeg/FFprobe in PATH
     - Computes `can_detect` flag (requires torch + ffmpeg)
     - Results cached in singleton service
     - Dialog displays real-time progress with log callbacks
     - Offers GPU Pack download if GPU detected but CUDA unavailable

   - **Dependency Injection**: Capabilities stored in `AppData.capabilities`
     - Passed from StartupDialog to `create_and_run_gui()`
     - Available throughout application lifetime
     - Single source of truth for all components

   - **UI Integration**: Components check `AppData.capabilities`
     - `SongListWidget`: Disable Detect button if `can_detect = False`
     - `MainWindow`: Show detection mode (GPU/CPU/Disabled) in status bar
     - Tooltips explain missing dependencies with actionable guidance
     - Early validation prevents user confusion

   - **Factory Guard**: `ProviderFactory.get_detection_provider(capabilities)`
     - Final safety check before provider creation
     - Raises `ProviderInitializationError` if `can_detect = False`
     - Defense in depth (UI already prevents this)

   - **Health Check**: CLI `--health-check` uses capabilities service
     - Shows same info as startup splash
     - Validates exe build integrity
     - Used by CI/CD to verify builds

   **Benefits**:
   - ✅ Centralized detection (no scattered torch imports)
   - ✅ User sees status immediately at startup
   - ✅ Clear error messages before attempting detection
   - ✅ Clean separation (UI doesn't import torch/ffmpeg)
   - ✅ Testable (mock capabilities in tests)

---

### **4. Dependency Injection**

- Use dependency injection to pass managers and services to components that need them.
- For example, `AppData` can act as a dependency injection container:
  ```python
  class AppData(QObject):
      def __init__(self):
          super().__init__()
          self.config = Config()
          self.songs = Songs()
          self.worker_queue = WorkerQueueManager()

          # Service instances for injection (optional - static methods also acceptable)
          self.gap_info_service = GapInfoService()
          self.usdx_file_service = USDXFileService()
          self.song_service = SongService()
  ```

**Note**: Services can be used statically (e.g., `USDXFileService.load(...)`) for simplicity, but injecting service instances via `AppData` improves testability and allows for easier mocking in unit tests.

### **5. Example Workflow**

#### **Use Case: Reloading a Song**
1. The user clicks "Reload Song" in the UI.
2. The UI calls an action method (e.g., `SongActions.reload_song()`).
3. The action delegates the reload operation to a service (e.g., `SongService`).
4. The service reloads the song and returns the updated data to the action.
5. The action updates the song and emits `songs.updated` signal.
6. The UI listens to the `songs.updated` signal and refreshes the displayed song.

### **6. Folder Structure**

```
src/
  ├── app/
  │   ├── app_data.py        # Centralized application state and DI container
  │
  ├── actions/
  │   ├── __init__.py
  │   ├── base_actions.py    # Base class for all actions
  │   ├── main_actions.py    # Main orchestration actions
  │   ├── song_actions.py    # Song-related actions
  │   ├── gap_actions.py     # Gap detection actions
  │   ├── audio_actions.py   # Audio processing actions
  │   ├── ui_actions.py      # UI-specific actions
  │   ├── core_actions.py    # Core application actions
  │   ├── watch_mode_actions.py # Watch mode actions
  │
  ├── managers/
  │   ├── __init__.py
  │   ├── base_manager.py    # Base class for all managers
  │   ├── song_manager.py    # Song loading and directory management
  │   ├── worker_queue_manager.py  # Manages worker tasks
  │   ├── watch_mode_controller.py # File system watching
  │
  ├── model/
  │   ├── __init__.py
  │   ├── song.py            # Represents a single song
  │   ├── songs.py           # Manages a list of songs (collection with signals)
  │   ├── gap_info.py        # Gap detection information
  │
  ├── services/
  │   ├── __init__.py
  │   ├── gap_info_service.py    # Handles gap detection logic
  │   ├── waveform_path_service.py # Manages waveform paths
  │   ├── song_service.py        # Song-related services
  │   ├── usdx_file_service.py   # USDX file I/O operations
  │   ├── audio_service.py       # Audio processing services
  │
  ├── ui/
  │   ├── __init__.py
  │   ├── task_queue_viewer.py   # Displays the task queue
  │   ├── mediaplayer/           # Media playback components
  │
  ├── workers/
  │   ├── __init__.py
  │   ├── worker_components.py    # Worker base classes and signals
  │   # ... various worker implementations
```

### **7. Benefits of the Architecture**

1. **Separation of Concerns**:
   - Each layer has a clear responsibility, reducing coupling and improving maintainability.

2. **Testability**:
   - Models and services are independent of the UI, making them easier to test.
   - Managers encapsulate logic, allowing for isolated testing of business rules.

3. **Scalability**:
   - Adding new features (e.g., new services or UI components) is easier because of the modular design.

4. **Reusability**:
   - Services and models can be reused across different parts of the application.

5. **Flexibility**:
   - Dependency injection allows for easy replacement or extension of components (e.g., swapping out `WorkerManager` for a different implementation).

### **8. Error Handling Patterns**

#### **Model Error State Management**
Models should manage their own error states via dedicated methods:

```python
class Song:
    def set_error(self, error_message: str):
        """Set error status and message"""
        self.status = SongStatus.ERROR
        self.error_message = error_message

    def clear_error(self):
        """Clear error status and message, resetting to neutral ready state (NOT_PROCESSED)"""
        self.status = SongStatus.NOT_PROCESSED  # Neutral ready state
        self.error_message = None
```

**Note**: `SongStatus.NOT_PROCESSED` represents the neutral ready state - the song is loaded and ready for operations, but no gap detection or processing has occurred yet.

#### **Centralized Status Mapping via GapInfo**
**GapInfo is the single source of truth for MATCH/MISMATCH/UPDATED/SOLVED/ERROR statuses.**

Actions/services/workers must update `gap_info` fields and status; `Song.status` updates automatically via the owner hook in `_gap_info_updated()`.

**Status Write Policy:**

| Status | Allowed Direct Write | Required Pattern |
|--------|---------------------|------------------|
| `QUEUED` | ✅ Yes | Set by actions before queuing workers |
| `PROCESSING` | ✅ Yes | Set by actions when workers start |
| `NOT_PROCESSED` | ✅ Yes | Via `clear_error()` only |
| `MATCH` | ❌ No | Set `gap_info.status = GapInfoStatus.MATCH` |
| `MISMATCH` | ❌ No | Set `gap_info.status = GapInfoStatus.MISMATCH` |
| `UPDATED` | ❌ No | Set `gap_info.status = GapInfoStatus.UPDATED` |
| `SOLVED` | ❌ No | Set `gap_info.status = GapInfoStatus.SOLVED` |
| `ERROR` | ✅ Conditional | Via `set_error()` for non-gap errors only; gap errors use `gap_info.status = GapInfoStatus.ERROR` |

**Correct pattern:**
```python
class GapActions:
    def _on_detect_gap_finished(self, song: Song, result: GapDetectionResult):
        # ✅ Update gap_info - status mapping happens via owner hook
        song.gap_info.detected_gap = result.detected_gap
        song.gap_info.diff = result.gap_diff
        song.gap_info.status = result.status  # Triggers _gap_info_updated()

        # ❌ DO NOT set song.status directly
        # song.status = SongStatus.MATCH  # WRONG!

        self.data.songs.updated.emit(song)

    def update_gap_value(self, song: Song, gap: int):
        # ✅ Update gap_info.status - Song.status updates automatically
        song.gap_info.updated_gap = gap
        song.gap_info.status = GapInfoStatus.UPDATED

        # ❌ DO NOT set song.status directly
        # song.status = SongStatus.UPDATED  # WRONG!
```

**Workflow sequence diagram:**
```
UI → Actions: Detect gap
Actions: set song.status = QUEUED  (✅ allowed transient state)
Actions → Worker: enqueue
Worker → Actions: started
Actions: set song.status = PROCESSING  (✅ allowed transient state)
Worker → Actions: finished(result)
Actions: set gap_info.status = result.status  (✅ correct pattern)
GapInfo → Song: owner hook triggers _gap_info_updated()  (automatic)
Song → UI: status updated via data model signal
```

**Error handling:**
```python
# Gap-related errors: set gap_info.status
gap_info.status = GapInfoStatus.ERROR

# Non-gap errors (I/O, loading, etc.): use set_error()
song.set_error("File not found")
```

### **9. Worker Queue Patterns**

#### **Asynchronous Task Queuing**

All long-running operations should be queued through the worker queue manager rather than executed inline. This ensures:
- UI responsiveness (non-blocking operations)
- Consistent task tracking and status visibility
- Proper cancellation support
- Sequential task execution when needed

**Queue via WorkerQueue, not inline execution:**

```python
# ✅ CORRECT: Queue worker for asynchronous execution
def _on_detect_gap_finished(self, song: Song, result: GapDetectionResult):
    # Update model state
    song.gap_info.detected_gap = result.detected_gap
    song.gap_info.status = result.status

    # Queue follow-up tasks (like auto-normalization)
    if self.config.auto_normalize and song.audio_file:
        logger.info(f"Queueing auto-normalization for {song}")
        # start_now=False lets queue manager schedule it properly
        # Implementation Contract: _normalize_song MUST create a worker and call
        # self.worker_queue.add_task(worker, start_now) - never execute inline!
        audio_actions._normalize_song(song, start_now=False)

# ❌ WRONG: Inline execution blocks UI and bypasses queue
def _on_detect_gap_finished_bad(self, song: Song, result: GapDetectionResult):
    song.gap_info.status = result.status

    # Inline call bypasses queue - blocks UI, no status tracking
    if self.config.auto_normalize:
        audio_actions._normalize_song(song)  # Executes immediately!
```

**Required Implementation Pattern for `_normalize_song`:**
```python
def _normalize_song(self, song: Song, start_now=False):
    """Queue normalization worker - NEVER execute inline!"""
    worker = NormalizeAudioWorker(song)
    # ... connect signals ...
    song.status = SongStatus.QUEUED
    self.data.songs.updated.emit(song)
    # REQUIRED: Use worker queue, not direct execution
    self.worker_queue.add_task(worker, start_now)
```

**start_now parameter usage:**

```python
# start_now=True: Execute immediately (for single user-initiated action)
worker_queue.add_task(worker, start_now=True)

# start_now=False: Let queue schedule (for chained/follow-up tasks)
worker_queue.add_task(worker, start_now=False)
```

**Benefits of proper queueing:**
- **UI Responsiveness**: Long operations don't block the event loop
- **Status Tracking**: WorkerStatus enum provides visibility (WAITING, RUNNING, FINISHED, ERROR)
- **Cancellation**: Users can cancel queued tasks
- **Sequential Execution**: Queue ensures proper ordering of dependent tasks
- **Error Isolation**: Worker failures don't crash the application

#### **Action Error Orchestration**
Actions should orchestrate error handling without directly manipulating model state:

```python
class SongActions:
    def process_song(self, song):
        try:
            result = self.service.process(song)
            if song.status == SongStatus.ERROR:
                song.clear_error()  # Clear errors after success
        except Exception as e:
            song.set_error(f"Processing failed: {str(e)}")
            self.data.songs.updated.emit(song)  # Signal via data model
```

**⚠️ Transient Status Flicker Caution:**

Clearing errors sets status to `NOT_PROCESSED`. Calling `clear_error()` immediately before queuing workers may cause momentary UI flicker:

```python
# ⚠️ May cause flicker: ERROR → NOT_PROCESSED → QUEUED
song.clear_error()  # Sets NOT_PROCESSED
song.status = SongStatus.QUEUED  # UI updates twice

# ✅ Better: Clear only after completion or let gap_info.status override errors
if song.status == SongStatus.ERROR:
    song.clear_error()  # Only clear after successful workflow completion
```

**Recommendation**: Clear errors only after successful operation completion. During workflows, status transitions via `gap_info.status` updates naturally override error states.

#### **Service Error Communication**
Services should return results or raise exceptions, not set model state:

```python
class SongService:
    def delete_song(self, song: Song) -> bool:
        """Returns True if successful, False if failed, raises exception for errors"""
        try:
            # Deletion logic here
            return True
        except PermissionError:
            return False  # Soft failure
        except Exception:
            raise  # Hard failure - let action handle it
```

### **9. Testing Strategy by Layer**

#### **Model Testing**
- Test data validation and derived properties
- Test state management methods (e.g., `set_error`)
- Mock external dependencies if any
- Focus on pure data logic

```python
def test_song_set_error():
    song = Song()
    song.set_error("Test error")
    assert song.status == SongStatus.ERROR
    assert song.error_message == "Test error"
```

#### **Service Testing**
- Test business logic in isolation
- Mock external dependencies (file system, network)
- Test error conditions and edge cases
- Services should be stateless and easily testable

```python
def test_song_service_delete_success():
    service = SongService()
    with patch('utils.files.delete_folder') as mock_delete:
        mock_delete.return_value = None
        result = service.delete_song(mock_song)
        assert result is True
```

### **10. Code Quality and Standards**

This architecture relies on consistent application of clean code principles:

- **DRY Principle**: Common functionality is extracted into reusable components (e.g., generic `set_error` method, shared service utilities)
- **SOLID Principles**: Each layer has single responsibilities, and components depend on abstractions
- **Clean Code**: Meaningful names, small functions, consistent error handling patterns
- **Layer Compliance**: Models handle data, services handle business logic, actions orchestrate

For detailed coding standards, clean code practices, and implementation guidelines, see [Coding Standards](coding-standards.md).

### **11. Signal Communication Patterns**

#### **When to Use Signals**

Use signals for **asynchronous communication** between components:
- **UI updates** based on background tasks (worker completed/errored)
- **Decoupling** components (e.g., workers ↔ UI)
- **Event-driven behavior** (e.g., notifying when a task completes)

**Good use cases:**
- Workers: Notify UI about progress, completion, errors
- Model changes: `songs.updated.emit(song)` when data changes
- Inter-component communication: Decouple actions, services, and UI

**Avoid signals for:**
- Direct method calls where synchronous behavior is expected
- Internal logic within a single class or tightly coupled components
- Actions emitting UI signals directly (update models instead, emit via data model)

#### **Signal Anti-Patterns**

**❌ Actions Emitting Signals Directly:**
Actions should NOT emit their own signals. Instead, update models and emit through data model aggregators like `self.data.songs.updated.emit(song)`.

**❌ Models Calling Services:**
Models should NOT import or call services. Services operate on models, not vice versa.

**❌ Services Emitting Signals:**
Services should NOT emit signals. They return results or raise exceptions. Actions handle results and emit signals.

#### **Signal Usage Guidelines**

**✅ Data Models Emit Signals:**
Data model classes (e.g., `Songs`) emit signals when their data changes:
- `self.data.songs.updated.emit(song)` - Single song changed
- `self.data.songs.listChanged.emit()` - List structure changed

**✅ Actions Orchestrate and Emit Via Data Model:**
Actions update models, then signal through the data model aggregator, not directly.

**✅ Workers Emit Task Signals:**
Workers emit `started`, `finished`, `error` signals to notify about task progress.

**✅ Always Wire Worker Error Signals:**
Worker error signals carry exception context that must be forwarded to error handlers. Lambda connectors must accept and forward the exception parameter.

#### **Layer-Specific Signal Responsibilities**

**Workers:**
- Perform long-running or asynchronous tasks
- Emit signals (`started`, `finished`, `error`) to notify about task progress
- Should NOT directly interact with UI or services

**Services:**
- Handle business logic and data manipulation
- Should NOT emit signals
- Return results or raise exceptions for actions to handle
- Should be stateless and reusable

**Actions:**
- Act as the controller layer, orchestrating workers, services, and UI updates
- Connect worker signals to appropriate handlers
- Update models based on results
- Signal changes through data model aggregators

**UI Components:**
- Handle user interactions and display updates
- Connect to signals from actions or data models
- Avoid directly interacting with workers or services

#### **Signal Encapsulation**

Encapsulate signals within specific layers:
- **Workers**: Emit task-specific signals (`started`, `finished`, `error`)
- **Data Models**: Emit signals for data changes (`songs.updated`, `songs.listChanged`)
- **UI Components**: Connect to signals from data models or actions

**Workflow:**
1. UI triggers action (e.g., "Detect Gap" button clicked)
2. Action starts worker and connects signals to handlers
3. Worker emits signals (`finished`, `error`) when task completes
4. Action handles worker signals, updates data model
5. Data model emits signals (e.g., `songs.updated.emit(song)`)
6. UI listens to data model signals and updates itself

### **12. Documentation References**

- **[Coding Standards](coding-standards.md)**: DRY principle, SOLID principles, clean code practices, testing standards
- **[Development Guide](DEVELOPMENT.md)**: Setup, testing, code quality tools
- **[Media Backends](MEDIA_BACKENDS.md)**: Backend architecture, VLC vs Qt, platform-specific strategies, interpolation details, limitations
- **[GitHub Copilot Instructions](../.github/copilot-instructions.md)**: AI assistance guidelines for consistent code generation

### **13. Testing Strategy by Layer**

#### **Model Testing**
- Test data validation and derived properties
- Test state management methods (e.g., `set_error`)
- Mock external dependencies if any
- Focus on pure data logic

#### **Service Testing**
- Test business logic in isolation
- Mock external dependencies (file system, network)
- Test error conditions and edge cases
- Services should be stateless and easily testable

#### **Action Testing**
- Test orchestration logic
- Mock services and verify they're called correctly
- Test error handling paths
- Verify correct model state updates and signal emissions

```python
def test_delete_song_action_with_service_failure():
    with patch('actions.song_actions.SongService') as mock_service:
        mock_service.return_value.delete_song.return_value = False
        actions.delete_selected_song()
        song.set_error.assert_called_with("Failed to delete song files")
```
