
### **1. When to Use Signals**
Signals are best used for **asynchronous communication** between components, especially when:
- **UI updates** are required based on background tasks (e.g., workers).
- **Decoupling** is needed between components (e.g., workers and UI).
- **Event-driven behavior** is required (e.g., notifying when a task is completed).

#### **Good Use Cases for Signals**
- **Workers**: Signals are ideal for notifying the UI or other components about the progress, completion, or errors of background tasks.
- **UI Updates**: Signals can notify the UI to refresh when data changes (e.g., 

songs.updated.emit()

).
- **Inter-component Communication**: Signals can decouple actions, services, and UI components.

#### **Avoid Using Signals**
- For **direct method calls** where synchronous behavior is expected (e.g., calling a service method from an action).
- For **internal logic** within a single class or tightly coupled components. Use direct method calls instead.

### **2. Encapsulation and Layers**
Your current architecture already has a separation of concerns with **actions**, **workers**, **services**, and **UI components**. This is a good start, but there are areas where encapsulation can be improved.

#### **Recommended Layer Responsibilities**
1. **Workers**:
   - Perform long-running or asynchronous tasks.
   - Emit signals (

started

, 

finished

, 

error

, etc.) to notify about task progress or completion.
   - Should not directly interact with the UI or services.

2. **Services**:
   - Handle business logic and data manipulation (e.g., loading songs, saving gap info).
   - Should not emit signals directly. Instead, return results or raise exceptions for actions to handle.
   - Should be stateless and reusable.

3. **Actions**:
   - Act as the **controller** layer, orchestrating workers, services, and UI updates.
   - Connect worker signals to appropriate handlers (e.g., updating the UI or triggering further actions).
   - Should encapsulate signal handling logic to avoid cluttering the UI or services.

4. **UI Components**:
   - Should only handle user interactions and display updates.
   - Connect to signals from actions or data models to update the UI.
   - Avoid directly interacting with workers or services.

### **3. Recommendations for Signal Usage**
#### **a. Centralize Signal Handling in Actions**
- Actions should act as the **bridge** between workers, services, and the UI.
- Workers should emit signals, but the actions should handle them and decide how to update the UI or trigger further logic.

**Example:**
```python
# In GapActions
def _on_detect_gap_finished(self, song: Song, result: GapDetectionResult):
    # Update song data
    song.gap_info.detected_gap = result.detected_gap
    song.gap_info.status = result.status
    self.data.songs.updated.emit(song)  # Notify UI indirectly via data model
```

#### **b. Use Signals for UI Updates**
- Use signals to notify the UI about changes in the data model (

songs.updated.emit()

).
- Avoid directly modifying the UI from workers or services.

**Example:**
```python
# In TaskQueueViewer
def updateTaskList(self):
    # Connect to workerQueueManager.on_task_list_changed signal
    self.workerQueueManager.on_task_list_changed.connect(self.updateTaskList)
```

#### **c. Avoid Overusing Signals**
- Do not emit signals for trivial operations or internal logic. Use direct method calls instead.
- For example, instead of emitting a signal every time a song attribute changes, emit a signal when the entire song list is updated.

### **4. Signal Encapsulation**
To avoid signal clutter and tightly coupled code, encapsulate signals within specific layers:
- **Workers**: Emit task-specific signals (

started

, 

finished

, 

error

).
- **Actions**: Handle worker signals and emit higher-level signals if needed (e.g., 

gap_detection_finished

).
- **Data Models**: Emit signals for changes in the data (e.g., 

songs.updated.emit()

).
- **UI Components**: Connect to signals from actions or data models.

**Example Workflow:**
1. **UI triggers an action** (e.g., "Detect Gap" button clicked).
2. **Action starts a worker** and connects its signals to handlers.
3. **Worker emits signals** (

finished

, 

error

) when the task is done.
4. **Action handles the worker signals**, updates the data model, and emits higher-level signals if needed.
5. **UI listens to data model signals** and updates itself.

### **5. Example Refactoring**
Here’s how you can refactor your signal usage for better encapsulation:

#### **Before:**
- Workers directly emit signals to the UI.
- UI components handle worker signals directly.

#### **After:**
- Workers emit signals to actions.
- Actions handle worker signals, update the data model, and emit higher-level signals.
- UI components listen to data model signals.

**Refactored Example:**
```python
# In GapActions
def detect_gap(self, overwrite=False):
    selected_songs = self.data.selected_songs
    for song in selected_songs:
        options = DetectGapWorkerOptions(...)
        worker = DetectGapWorker(options)
        worker.signals.finished.connect(lambda result: self._on_detect_gap_finished(song, result))
        self.worker_queue.add_task(worker)

def _on_detect_gap_finished(self, song: Song, result: GapDetectionResult):
    song.gap_info.detected_gap = result.detected_gap
    self.data.songs.updated.emit(song)  # Notify UI indirectly
```

```python
# In TaskQueueViewer (UI)
def updateTaskList(self):
    self.data.songs.updated.connect(self.refreshUI)  # Listen to data model signals
```

### **6. Summary**
- **Use signals sparingly**: Only for asynchronous communication or decoupling.
- **Encapsulate signal handling**: Workers → Actions → Data Models → UI.
- **Centralize logic in actions**: Let actions handle worker signals and update the data model.
- **Emit high-level signals**: From actions or data models to notify the UI.
- **Avoid direct UI updates**: Workers and services should not directly modify the UI.
