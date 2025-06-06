
## **1. Target Architecture Overview** -- not yet achieved!

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
  - Manages the `SongList` and handles operations like selecting songs or clearing the list.
  - Emits signals (e.g., `selected_songs_changed`, `song_added`) to notify other components about changes.
  - Delegates low-level operations (e.g., adding/removing songs) to the `SongList`.

- **`WorkerManager`**:
  - Manages worker tasks (e.g., queuing, running, canceling).
  - Emits signals to notify the UI about task progress or completion.
  - Encapsulates worker-related logic to keep it separate from the UI.

- **`ConfigManager`**:
  - Manages application configuration (e.g., directories, temporary paths).
  - Provides a clean interface for accessing and updating configuration values.

#### **Services**
- **`GapInfoService`**:
  - Handles gap detection logic for songs.
  - Stateless and reusable across the application.

- **`WaveformPathService`**:
  - Manages file paths for waveform generation.
  - Provides utility methods for creating or validating paths.

#### **Application State**
- **`AppState`**:
  - Manages global state (e.g., `selected_songs`, `is_loading_songs`).
  - Forwards signals from managers to simplify access for the UI.
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
   - Services perform stateless operations (e.g., gap detection) and return results to managers.
   - Managers update the models or emit signals based on the results.

---

### **4. Dependency Injection**

- Use dependency injection to pass managers and services to components that need them.
- For example, `AppData` can act as a dependency injection container:
  ```python
  class AppData(QObject):
      def __init__(self):
          super().__init__()
          self.config_manager = ConfigManager(Config())
          self.song_manager = SongManager(Songs())
          self.worker_manager = WorkerManager()
  ```

### **5. Example Workflow**

#### **Use Case: Reloading a Song**
1. The user clicks "Reload Song" in the UI.
2. The UI calls `SongManager.reload_song()`.
3. `SongManager` delegates the reload operation to a service (e.g., `SongService`).
4. The service reloads the song and returns the updated data to `SongManager`.
5. `SongManager` updates the `SongList` and emits a `song_updated` signal.
6. The UI listens to the `song_updated` signal and refreshes the displayed song.

### **6. Folder Structure**

```
src/
  ├── app/
  │   ├── app_data.py        # Centralized application state
  │   ├── app_state.py       # Global state management
  │
  ├── managers/
  │   ├── __init__.py
  │   ├── song_manager.py    # Manages song selection and operations
  │   ├── worker_manager.py  # Manages worker tasks
  │   ├── config_manager.py  # Manages configuration
  │
  ├── models/
  │   ├── __init__.py
  │   ├── song.py            # Represents a single song
  │   ├── songs.py           # Manages a list of songs
  │
  ├── services/
  │   ├── __init__.py
  │   ├── gap_info_service.py    # Handles gap detection logic
  │   ├── waveform_path_service.py # Manages waveform paths
  │
  ├── ui/
  │   ├── __init__.py
  │   ├── task_queue_viewer.py   # Displays the task queue
  │   ├── media_player.py        # Handles media playback
  │
  ├── workers/
  │   ├── __init__.py
  │   ├── worker_queue_manager.py # Manages worker queues
  │   ├── worker_components.py    # Worker base classes and signals
```

### **7. Benefits of the Target Architecture**

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
