# Coding Standards

This document outlines the coding standards, principles, and best practices for the USDXFixGap project. These guidelines ensure maintainable, readable, and robust code across all components.

## **1. Core Principles**

### **DRY (Don't Repeat Yourself)**
Avoid code duplication by extracting common functionality into reusable components.

#### **✅ Good Examples:**

**Generic Error Handling:**
```python
# ✅ Single generic error method in models
class Song:
    def set_error(self, error_message: str):
        """Generic error setter for any operation"""
        self.status = SongStatus.ERROR
        self.error_message = error_message
    
    def clear_error(self):
        """Clear any error state, resetting to neutral ready state (NOT_PROCESSED)"""
        self.status = SongStatus.NOT_PROCESSED  # Neutral ready state
        self.error_message = None

# Used for any operation
song.set_error("Delete failed")
song.set_error("Processing failed") 
song.set_error("Validation failed")
```

**Note**: Calling `clear_error()` sets status to `NOT_PROCESSED`, which represents the neutral ready state (loaded, but not yet processed).

**Shared Service Utilities:**
```python
# ✅ Common file operations in a utility service
class FileService:
    @staticmethod
    def safe_delete(path: str) -> bool:
        """Safely delete file/folder with error handling"""
        try:
            if os.path.isfile(path):
                os.remove(path)
            elif os.path.isdir(path):
                shutil.rmtree(path)
            return True
        except (OSError, PermissionError):
            return False

# Used across multiple services
class SongService:
    def delete_song(self, song: Song) -> bool:
        return FileService.safe_delete(song.folder_path)

class CacheService:
    def clear_cache(self, cache_path: str) -> bool:
        return FileService.safe_delete(cache_path)
```

#### **❌ Anti-patterns to Avoid:**

**Duplicate Error Handling:**
```python
# ❌ Multiple specific error methods doing the same thing
class Song:
    def set_delete_error(self, message):
        self.status = SongStatus.ERROR
        self.error_message = message
    
    def set_processing_error(self, message):
        self.status = SongStatus.ERROR  # Same logic!
        self.error_message = message
    
    def set_validation_error(self, message):
        self.status = SongStatus.ERROR  # Same logic!
        self.error_message = message
```

**Duplicate File Operations:**
```python
# ❌ Repeated file deletion logic
class SongService:
    def delete_song(self, song):
        try:
            if os.path.exists(song.folder_path):
                shutil.rmtree(song.folder_path)
        except Exception:
            return False

class CacheService:
    def clear_cache(self, cache_path):
        try:
            if os.path.exists(cache_path):  # Same logic!
                shutil.rmtree(cache_path)
        except Exception:
            return False
```

### **SOLID Principles**

#### **Single Responsibility Principle (SRP)**
Each class should have one reason to change.

```python
# ✅ Good: Each class has a single responsibility
class Song:
    """Represents song data and state only"""
    def __init__(self, name: str, path: str):
        self.name = name
        self.path = path

class SongService:
    """Handles song file operations only"""
    def delete_song(self, song: Song) -> bool:
        return FileService.safe_delete(song.folder_path)

class SongActions:
    """Orchestrates song operations only"""
    def delete_selected_song(self):
        # Coordination logic only
        pass

# ❌ Bad: Song class doing too many things
class Song:
    def __init__(self, name: str, path: str):
        self.name = name
        self.path = path
    
    def delete_files(self):  # File operations - not Song's responsibility
        shutil.rmtree(self.path)
    
    def emit_ui_signal(self):  # UI concerns - not Song's responsibility
        self.signal.emit()
```

#### **Open/Closed Principle (OCP)**
Classes should be open for extension, closed for modification.

```python
# ✅ Good: Extensible error handling
class Song:
    def set_error(self, error_message: str):
        """Base error handling - no need to modify for new error types"""
        self.status = SongStatus.ERROR
        self.error_message = error_message

# New error types don't require modifying Song class
song.set_error("Delete failed")      # Delete errors
song.set_error("Network timeout")    # Network errors  
song.set_error("Invalid format")     # Validation errors
```

#### **Dependency Inversion Principle (DIP)**
Depend on abstractions, not concretions.

**Preferred Pattern - Service Injection:**
```python
# ✅ Best: Actions receive service instances via dependency injection
class SongActions:
    def __init__(self, data: AppData):
        self.data = data
        self.song_service = data.song_service  # Injected via AppData
    
    def delete_song(self, song: Song):
        success = self.song_service.delete_song(song)
        if not success:
            song.set_error("Delete failed")
```

**Acceptable Alternative - Static Service Methods:**
```python
# ✅ Acceptable: Static service method calls (simpler, less testable)
from services.song_service import SongService

class SongActions:
    def delete_song(self, song: Song):
        success = SongService.delete_song(song)
        if not success:
            song.set_error("Delete failed")
```

**Anti-Pattern:**
```python
# ❌ Bad: Actions creating concrete dependencies
class SongActions:
    def delete_song(self, song: Song):
        # Directly creating concrete dependency
        if os.path.exists(song.path):
            shutil.rmtree(song.path)  # Tight coupling to file system
```

**Note**: Service injection improves testability (easier mocking), but static service methods are acceptable for initial adoption. Prefer injection where testing is critical.

**Service Usage Patterns - USDX File Operations:**

```python
# ✅ CORRECT: Use USDXFileService for file operations
from model.usdx_file import USDXFile
from services.usdx_file_service import USDXFileService
from utils.async_utils import run_async  # For calling async from sync context

async def update_gap_in_file_async(song: Song, new_gap: int):
    # Create temporary USDXFile instance
    usdx_file = USDXFile(song.txt_file)
    
    # Load file content through service
    await USDXFileService.load(usdx_file)
    
    # Update GAP tag through service
    await USDXFileService.write_gap_tag(usdx_file, new_gap)
    
    # Note: Service automatically saves changes

# ✅ CORRECT: Wrap async service calls when in synchronous context (e.g., Actions)
def update_gap_in_file(song: Song, new_gap: int):
    """Sync wrapper using run_async for event-loop integration"""
    async def _update():
        usdx_file = USDXFile(song.txt_file)
        await USDXFileService.load(usdx_file)
        await USDXFileService.write_gap_tag(usdx_file, new_gap)
    
    run_async(_update())  # run_async handles event loop management

# ❌ WRONG: Don't access non-existent song.usdx_file property
def update_gap_bad(song: Song, new_gap: int):
    # This will crash - Song has no usdx_file property!
    song.usdx_file.write_gap_tag(new_gap)  # AttributeError!
```

**Note**: Use `run_async(...)` when calling async service methods from synchronous action code. This wrapper ensures proper event loop integration.

**Service Usage Patterns - GapInfo Persistence:**

```python
# ✅ CORRECT: Use GapInfoService.save() for persistence
from services.gap_info_service import GapInfoService
from utils.async_utils import run_async

async def update_gap_info_async(song: Song):
    song.gap_info.detected_gap = 1200
    song.gap_info.status = GapInfoStatus.MATCH
    
    # Persist through service
    await GapInfoService.save(song.gap_info)

# ✅ CORRECT: Wrap async call when in synchronous context
def update_gap_info(song: Song):
    """Sync wrapper for gap info update"""
    async def _update():
        song.gap_info.detected_gap = 1200
        song.gap_info.status = GapInfoStatus.MATCH
        await GapInfoService.save(song.gap_info)
    
    run_async(_update())  # Use run_async for event loop integration

# ❌ WRONG: Don't call save() method on model
def update_gap_info_bad(song: Song):
    song.gap_info.detected_gap = 1200
    
    # Model-bound persistence violates service layer separation
    await song.gap_info.save()  # Don't do this - use service instead
```

**Note**: Service methods are async (`async def`). When calling from synchronous action code, wrap the async call in a local async function and use `run_async(...)` to execute it.

**Note Time Recalculation Pattern:**

```python
# ✅ CORRECT: Recalculate notes using song's BPM/gap data
def recalculate_note_times(song: Song):
    """Update note timings based on current song gap/bpm settings"""
    if not song.notes or not song.bpm:
        return
    
    beats_per_ms = (song.bpm / 60 / 1000) * 4
    
    for note in song.notes:
        if song.is_relative:
            note.start_ms = note.StartBeat / beats_per_ms
            note.end_ms = (note.StartBeat + note.Length) / beats_per_ms
        else:
            note.start_ms = song.gap + (note.StartBeat / beats_per_ms)
            note.end_ms = song.gap + ((note.StartBeat + note.Length) / beats_per_ms)
        note.duration_ms = note.end_ms - note.start_ms

# ❌ WRONG: Don't assume USDXFile instance exists on Song
def recalculate_bad(song: Song):
    song.usdx_file.calculate_note_times()  # AttributeError - no such property!
```

## **2. Clean Code Practices**

### **Meaningful Names**

#### **Classes and Methods:**
```python
# ✅ Good: Clear, descriptive names
class SongDeletionService:
    def delete_song_files(self, song: Song) -> bool:
        """Delete all files associated with a song"""
        pass
    
    def validate_song_exists(self, song: Song) -> bool:
        """Check if song files exist on disk"""
        pass

# ❌ Bad: Vague, unclear names
class SongMgr:
    def do_stuff(self, s):
        pass
    
    def check(self, s):
        pass
```

#### **Variables:**
```python
# ✅ Good: Descriptive variable names
selected_songs = self.get_selected_songs()
deletion_successful = self.song_service.delete_song(song)
error_message = f"Failed to delete {song.name}"

# ❌ Bad: Cryptic abbreviations
sel_s = self.get_sel()
del_ok = self.svc.del(s)
err_msg = f"Fail {s.n}"
```

### **Function Size and Complexity**

#### **Keep Functions Small:**
```python
# ✅ Good: Small, focused functions
class SongActions:
    def delete_selected_song(self):
        """Delete the currently selected song"""
        song = self._get_selected_song()
        if not song:
            return
        
        self._attempt_song_deletion(song)
    
    def _get_selected_song(self) -> Optional[Song]:
        """Get the currently selected song"""
        selected = self.data.songs.get_selected()
        return selected[0] if selected else None
    
    def _attempt_song_deletion(self, song: Song):
        """Attempt to delete a song and handle result"""
        try:
            success = self.song_service.delete_song(song)
            self._handle_deletion_result(song, success)
        except Exception as e:
            song.set_error(f"Delete error: {str(e)}")
            self.data.songs.updated.emit(song)
    
    def _handle_deletion_result(self, song: Song, success: bool):
        """Handle the result of song deletion"""
        if success:
            self.data.songs.remove_song(song)
        else:
            song.set_error("Failed to delete song files")
            self.data.songs.updated.emit(song)

# ❌ Bad: Large, complex function doing everything
class SongActions:
    def delete_selected_song(self):
        selected = self.data.songs.get_selected()
        if not selected:
            return
        song = selected[0]
        try:
            if self.song_service.delete_song(song):
                self.data.songs.remove_song(song)
                self.data.songs.list_changed.emit()
            else:
                song.status = SongStatus.ERROR
                song.error_message = "Failed to delete song files"
                self.data.songs.updated.emit(song)
        except Exception as e:
            song.status = SongStatus.ERROR
            song.error_message = f"Delete error: {str(e)}"
            self.data.songs.updated.emit(song)
```

### **Error Handling**

#### **Consistent Error Patterns:**
```python
# ✅ Good: Consistent error handling across the application
class SongActions:
    def process_song(self, song: Song):
        """Process a song with consistent error handling"""
        try:
            result = self.service.process_song(song)
            self._handle_process_success(song, result)
            # Clear error only after successful completion
            if song.status == SongStatus.ERROR:
                song.clear_error()
        except ValidationError as e:
            song.set_error(f"Validation failed: {str(e)}")
            self._emit_song_update(song)
        except ProcessingError as e:
            song.set_error(f"Processing failed: {str(e)}")
            self._emit_song_update(song)
        except Exception as e:
            song.set_error(f"Unexpected error: {str(e)}")
            self._emit_song_update(song)
    
    def _emit_song_update(self, song: Song):
```

**⚠️ Transient Status Flicker Warning:**

Calling `clear_error()` immediately before setting transient states (QUEUED/PROCESSING) may cause brief UI flicker as the status transitions through NOT_PROCESSED:

```python
# ⚠️ May cause flicker: ERROR → NOT_PROCESSED → QUEUED
song.clear_error()  # Sets NOT_PROCESSED
song.status = SongStatus.QUEUED  # Immediate transition

# ✅ Better: Let workflow transitions handle clearing
# Only clear errors after successful completion, or rely on gap_info.status updates
# to naturally override error states
```

**Recommendation**: Only call `clear_error()` after successful operation completion or when explicitly resetting song state. During normal workflows, let status transitions happen through `gap_info.status` updates which override error states automatically.
        """Emit update signal via data model"""
        self.data.songs.updated.emit(song)

# ❌ Bad: Inconsistent error handling
class SongActions:
    def process_song(self, song: Song):
        try:
            result = self.service.process_song(song)
        except:  # Too broad exception handling
            song.status = SongStatus.ERROR  # Direct model manipulation
            print("Error occurred")  # Poor error reporting
```

### **Comments and Documentation**

#### **When to Comment:**
```python
# ✅ Good: Comments explain WHY, not WHAT
class SongService:
    def delete_song(self, song: Song) -> bool:
        """
        Delete all files associated with a song.
        
        Returns False for permission errors (soft failure),
        raises exception for unexpected errors (hard failure).
        This allows actions to handle different error types appropriately.
        """
        try:
            # Use safe deletion to handle locked files gracefully
            return FileService.safe_delete(song.folder_path)
        except PermissionError:
            # Soft failure - song remains in UI with error status
            return False
        except Exception:
            # Hard failure - let action handle unexpected errors
            raise

# ❌ Bad: Comments stating the obvious
class SongService:
    def delete_song(self, song: Song) -> bool:
        # Delete the song
        try:
            # Call delete method
            return FileService.safe_delete(song.folder_path)
        except PermissionError:
            # Return False
            return False
```

### **Method and Class Organization**

#### **Logical Grouping:**
```python
# ✅ Good: Well-organized class with logical grouping
class Song:
    """Represents a song with its metadata and state"""
    
    # --- Initialization ---
    def __init__(self, name: str, path: str):
        self.name = name
        self.path = path
        self.status = SongStatus.NOT_PROCESSED
        self.error_message = None
    
    # --- Property Access ---
    @property
    def folder_path(self) -> str:
        return os.path.dirname(self.path)
    
    @property
    def has_error(self) -> bool:
        return self.status == SongStatus.ERROR
    
    # --- State Management ---
    def set_error(self, error_message: str):
        """Set error state with message"""
        self.status = SongStatus.ERROR
        self.error_message = error_message
    
    def clear_error(self):
        """Clear error state, resetting to neutral ready state"""
        self.status = SongStatus.NOT_PROCESSED
        self.error_message = None
    
    # --- Validation ---
    def validate(self) -> bool:
        """Validate song data integrity"""
        return os.path.exists(self.path)
```

## **3. Architecture Compliance**

### **Centralized Status Mapping**

**GapInfo is the single source of truth for status mapping.**

#### **Status Write Policy Quick Reference:**

| Status | Direct Write | Required Pattern |
|--------|-------------|------------------|
| `QUEUED` | ✅ Allowed | `song.status = SongStatus.QUEUED` before queuing workers |
| `PROCESSING` | ✅ Allowed | `song.status = SongStatus.PROCESSING` when workers start |
| `NOT_PROCESSED` | ✅ Allowed | Via `song.clear_error()` only |
| `MATCH` | ❌ Forbidden | Set `gap_info.status = GapInfoStatus.MATCH` |
| `MISMATCH` | ❌ Forbidden | Set `gap_info.status = GapInfoStatus.MISMATCH` |
| `UPDATED` | ❌ Forbidden | Set `gap_info.status = GapInfoStatus.UPDATED` |
| `SOLVED` | ❌ Forbidden | Set `gap_info.status = GapInfoStatus.SOLVED` |
| `ERROR` | ✅ Conditional | Via `song.set_error()` for non-gap errors; gap errors use `gap_info.status = GapInfoStatus.ERROR` |

#### **Code Examples:**
```python
# ✅ ALLOWED: Transient workflow states (QUEUED, PROCESSING)
song.status = SongStatus.QUEUED      # Before worker starts
song.status = SongStatus.PROCESSING  # When worker begins

# ✅ ALLOWED: Error handling via set_error()
song.set_error("File not found")  # Non-gap errors

# ❌ FORBIDDEN: Direct mapped status writes
song.status = SongStatus.MATCH      # WRONG - use gap_info.status
song.status = SongStatus.MISMATCH   # WRONG - use gap_info.status
song.status = SongStatus.UPDATED    # WRONG - use gap_info.status
song.status = SongStatus.SOLVED     # WRONG - use gap_info.status
song.status = SongStatus.ERROR      # WRONG - use set_error() or gap_info.status
```

#### **Correct Status Update Patterns:**
```python
# ✅ Good: Update gap_info.status - Song.status updates automatically
class GapActions:
    def _on_detect_gap_finished(self, song: Song, result):
        song.gap_info.detected_gap = result.detected_gap
        song.gap_info.diff = result.gap_diff
        song.gap_info.status = result.status  # Triggers _gap_info_updated()
        # Song.status is now automatically set via owner hook
        self.data.songs.updated.emit(song)
    
    def update_gap_value(self, song: Song, gap: int):
        song.gap = gap
        song.gap_info.updated_gap = gap
        song.gap_info.status = GapInfoStatus.UPDATED  # Automatic mapping
        self.data.songs.updated.emit(song)

# ❌ Bad: Direct Song.status writes for mapped statuses
class GapActions:
    def _on_detect_gap_finished(self, song: Song, result):
        song.gap_info.status = result.status
        song.status = SongStatus.MATCH  # DUPLICATE - already set by mapping!
        # This creates duplicate writes and violates single source of truth
```

#### **Error Handling Patterns:**
```python
# ✅ Good: Gap-related errors via gap_info.status
if detection_failed:
    gap_info.status = GapInfoStatus.ERROR
    # Song.status = ERROR automatically via mapping

# ✅ Good: Non-gap errors via set_error()
try:
    load_file(song.txt_file)
except FileNotFoundError as e:
    song.set_error(f"File not found: {e}")
    # Song.status = ERROR and error_message set

# ❌ Bad: Direct status assignment
song.status = SongStatus.ERROR  # WRONG - bypasses error message
```

### **Layer Responsibility Adherence**

#### **Models - Data Only:**
```python
# ✅ Good: Model focuses on data and data-related logic only
class Song:
    def set_error(self, error_message: str):
        """Set error state - data operation only"""
        self.status = SongStatus.ERROR
        self.error_message = error_message
    
    @property
    def folder_path(self) -> str:
        """Derived property - data logic only"""
        return os.path.dirname(self.path)

# ❌ Bad: Model doing business logic or UI operations
class Song:
    def delete_files(self):  # Business logic - belongs in service
        shutil.rmtree(self.path)
    
    def emit_signal(self):  # UI concern - belongs in action/manager
        self.signal.emit()
```

#### **Services - Business Logic Only:**
```python
# ✅ Good: Service focuses on business operations only
class SongService:
    def delete_song(self, song: Song) -> bool:
        """Business logic for song deletion"""
        return FileService.safe_delete(song.folder_path)
    
    def validate_song_format(self, song: Song) -> bool:
        """Business logic for format validation"""
        return song.path.endswith(('.mp3', '.wav', '.flac'))

# ❌ Bad: Service manipulating model state or UI
class SongService:
    def delete_song(self, song: Song) -> bool:
        result = FileService.safe_delete(song.folder_path)
        if not result:
            song.set_error("Delete failed")  # Model state - belongs in action
        return result
```

#### **Actions - Orchestration Only:**
```python
# ✅ Good: Action orchestrates between layers
class SongActions:
    def delete_selected_song(self):
        """Orchestrate song deletion across layers"""
        song = self._get_selected_song()
        if not song:
            return
        
        # Use service for business logic
        success = self.song_service.delete_song(song)
        
        # Update model state based on result
        if success:
            self.data.songs.remove_song(song)
        else:
            song.set_error("Failed to delete song files")
            self.data.songs.updated.emit(song)

# ❌ Bad: Action doing business logic directly
class SongActions:
    def delete_selected_song(self):
        song = self._get_selected_song()
        # Direct business logic - should use service
        if os.path.exists(song.path):
            shutil.rmtree(song.path)
```

## **4. Testing Standards**

### **Test Organization**
```python
# ✅ Good: Well-organized test class
class TestSongDeletion:
    """Test song deletion functionality"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.song = Mock(spec=Song)
        self.service = Mock(spec=SongService)
        self.actions = SongActions(self.service)
    
    # --- Success Cases ---
    def test_delete_selected_song_success(self):
        """Test successful song deletion"""
        # Arrange
        self.service.delete_song.return_value = True
        
        # Act
        self.actions.delete_selected_song()
        
        # Assert
        self.service.delete_song.assert_called_once()
        # ... more assertions
    
    # --- Error Cases ---
    def test_delete_selected_song_service_failure(self):
        """Test deletion when service returns failure"""
        # Arrange
        self.service.delete_song.return_value = False
        
        # Act
        self.actions.delete_selected_song()
        
        # Assert
        self.song.set_error.assert_called_with("Failed to delete song files")
```

### **Mock Usage**
```python
# ✅ Good: Appropriate mocking with specifications
def test_song_deletion_with_mocked_service():
    song = Mock(spec=Song)  # Spec ensures we only use Song methods
    service = Mock(spec=SongService)  # Spec ensures we only use service methods
    
    service.delete_song.return_value = True
    actions = SongActions(service)
    
    # Test behavior, not implementation details
    result = actions.delete_selected_song()
    service.delete_song.assert_called_once_with(song)

# ❌ Bad: Over-mocking or mocking without specs
def test_song_deletion_bad():
    song = Mock()  # No spec - can call any method
    service = Mock()
    
    # Mocking implementation details instead of behavior
    song.path = "/test/path"
    service.delete_song.return_value = True
```

### **Static Analysis and Architectural Policy Enforcement**

Add automated checks to detect forbidden patterns and enforce architectural policies:

#### **Forbidden Direct Mapped-Status Writes:**
```python
# Recommended: Add static check for forbidden status patterns
# Example: tests/test_architecture_violations.py

import os

def test_no_direct_mapped_status_writes():
    """Ensure no code directly sets mapped statuses (MATCH, MISMATCH, UPDATED, SOLVED, ERROR)"""
    forbidden_patterns = [
        "song.status = SongStatus.MATCH",
        "song.status = SongStatus.MISMATCH",
        "song.status = SongStatus.UPDATED",
        "song.status = SongStatus.SOLVED",
        "song.status = SongStatus.ERROR",  # Use set_error() or gap_info.status instead
    ]
    
    # Allowed patterns (for reference)
    allowed_patterns = [
        "song.status = SongStatus.QUEUED",
        "song.status = SongStatus.PROCESSING",
        "song.set_error(",  # Allowed error setter
        "gap_info.status =",  # Allowed - source of truth
    ]
    
    violations = []
    for root, dirs, files in os.walk("src/actions"):
        for file in files:
            if file.endswith(".py"):
                filepath = os.path.join(root, file)
                with open(filepath) as f:
                    for line_num, line in enumerate(f, 1):
                        for pattern in forbidden_patterns:
                            if pattern in line:
                                violations.append(f"{file}:{line_num} - {pattern}")
    
    assert not violations, f"Found forbidden status writes:\\n" + "\\n".join(violations)
```

**Enforcement Guidelines:**
- **Run in CI/CD**: Add this test to continuous integration pipelines
- **Pre-commit Hook**: Consider adding as a pre-commit check
- **Only Allow**:
  - Transient states: `song.status = SongStatus.QUEUED/PROCESSING`
  - Error methods: `song.set_error()` / `song.clear_error()`
  - GapInfo mapping: `gap_info.status = GapInfoStatus.*`
- **Forbidden**: Direct writes to MATCH, MISMATCH, UPDATED, SOLVED, ERROR
- **Advanced**: Use AST parsing for more sophisticated detection of context-aware violations

## **5. Code Review Checklist**

### **Before Submitting Code:**
- [ ] **DRY**: Is there any duplicated logic that could be extracted?
- [ ] **SRP**: Does each class/method have a single responsibility?
- [ ] **Layer Compliance**: Are models, services, and actions staying in their lanes?
- [ ] **Error Handling**: Is error handling consistent and using `set_error`/`clear_error`?
- [ ] **Naming**: Are all names clear and descriptive?
- [ ] **Function Size**: Are functions small and focused?
- [ ] **Tests**: Are there tests covering the new functionality?
- [ ] **Documentation**: Are complex decisions explained in comments?

### **Common Anti-patterns to Watch For:**
- Methods longer than 20 lines
- Classes with more than one reason to change
- Models calling services directly
- Services manipulating model state
- Duplicate error handling logic
- Hard-coded magic numbers or strings
- Missing error handling
- Tests that test implementation details instead of behavior

---

## **6. Examples in Current Codebase**

### **Well-Implemented Patterns:**

**Generic Error Handling (`src/model/song.py`):**
```python
def set_error(self, error_message: str):
    """Generic error setter - follows DRY principle"""
    self.status = SongStatus.ERROR
    self.error_message = error_message

def clear_error(self):
    """Clear error state - single responsibility, resets to neutral ready state"""
    self.status = SongStatus.NOT_PROCESSED
    self.error_message = None
```

**Proper Layer Separation (`src/actions/song_actions.py`):**
```python
def delete_selected_song(self):
    """Orchestrates deletion - doesn't do business logic directly"""
    try:
        success = self.song_service.delete_song(song)  # Uses service
        if success:
            self.data.songs.remove_song(song)  # Updates model
        else:
            song.set_error("Failed to delete song files")  # Sets model state
            self.data.songs.updated.emit(song)  # Emits via data model
    except Exception as e:
        song.set_error(f"Delete error: {str(e)}")
        self.data.songs.updated.emit(song)
```

These standards should be followed consistently across the codebase to maintain high code quality and architectural integrity.
