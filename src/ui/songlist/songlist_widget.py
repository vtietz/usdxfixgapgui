from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QMessageBox
from PySide6.QtCore import QSortFilterProxyModel, QTimer
from actions import Actions
from app.app_data import AppData
from model.song import Song, SongStatus
from model.songs import Songs
from ui.songlist.songlist_view import SongListView
from ui.songlist.songlist_model import SongTableModel
from typing import List, cast
import logging

logger = logging.getLogger(__name__)

# Configuration for chunked loading
CHUNK_SIZE = 400  # Songs per chunk
CHUNK_DELAY_MS = 16  # Delay between chunks (60 FPS)


class CustomSortFilterProxyModel(QSortFilterProxyModel):
    def __init__(self, app_data: AppData, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.selectedStatuses: list[str] = []  # List of status names (strings)
        self.textFilter: str = ""
        self.app_data = app_data  # Reference to AppData for selected songs

    def filterAcceptsRow(self, source_row, source_parent):
        # Access the source model's data for the given row
        source_model = cast(SongTableModel, self.sourceModel())
        song: Song = source_model.songs[source_row]

        # Always show selected songs regardless of filters
        if hasattr(self.app_data, "selected_songs") and song in self.app_data.selected_songs:
            return True

        # Fast-path: skip filtering if no filters are active
        if not self.selectedStatuses and not self.textFilter:
            return True

        # Implement filtering logic
        statusMatch = song.status.name in self.selectedStatuses if self.selectedStatuses else True

        # Prefer cached lowercase strings from model if available
        cache_entry = source_model._row_cache.get(song.path) if hasattr(source_model, "_row_cache") else None
        if cache_entry:
            textMatch = (
                self.textFilter in cache_entry["artist_lower"]
                or self.textFilter in cache_entry["title_lower"]
                or self.textFilter in cache_entry.get("relative_path_lower", "")
            )
        else:
            # Fallback to direct lowercase conversion
            from utils import files

            relative_path = files.get_relative_path(source_model.app_data.directory, song.path).lower()
            textMatch = (
                self.textFilter in song.artist.lower()
                or self.textFilter in song.title.lower()
                or self.textFilter in relative_path
            )

        return statusMatch and textMatch


class SongListWidget(QWidget):
    def __init__(self, songs_model: Songs, actions: Actions, data: AppData, parent=None):
        super().__init__(parent)
        self._actions = actions
        self._data = data
        self._selected_songs: List[Song] = []

        # Initialize models and view
        self.songs_model = songs_model
        self.tableModel = SongTableModel(songs_model, data)
        self.proxyModel = self._create_proxy_model()
        self.tableView = SongListView(self.proxyModel, actions)

        # Create UI components
        self._create_action_buttons()
        self.countLabel = QLabel()

        # Setup layout
        self._setup_layout()

        # Connect signals
        self._connect_model_signals()
        self._connect_action_signals()

        # Initialize streaming state
        self._streaming_songs: List[Song] = []
        self._streaming_index = 0
        self._streaming_timer = QTimer()
        self._streaming_timer.timeout.connect(self._append_next_chunk)

        # Initial UI update
        self.updateCountLabel()
        self.onSelectedSongsChanged([])

    def _create_proxy_model(self) -> CustomSortFilterProxyModel:
        """Create and configure the proxy model for filtering and sorting."""
        proxy = CustomSortFilterProxyModel(self._data)
        proxy.setSourceModel(self.tableModel)
        proxy.setDynamicSortFilter(True)
        return proxy

    def _create_action_buttons(self):
        """Create all action buttons with tooltips and click handlers."""
        self.detectButton = QPushButton("Detect")
        self.detectButton.clicked.connect(self.onDetectClicked)
        self.detectButton.setToolTip("Run gap detection on selected songs")

        self.openFolderButton = QPushButton("Open Folder")
        self.openFolderButton.clicked.connect(lambda: self._actions.open_folder())
        self.openFolderButton.setToolTip("Open song folder in file explorer")

        self.open_usdx_button = QPushButton("Open in USDB")
        self.open_usdx_button.clicked.connect(lambda: self._actions.open_usdx())
        self.open_usdx_button.setToolTip("Open song page on UltraStar Database website")

        self.reload_button = QPushButton("Reload")
        self.reload_button.clicked.connect(lambda: self._actions.reload_song())
        self.reload_button.setToolTip("Reload song data from file")

        self.normalize_button = QPushButton("Normalize")
        self.normalize_button.clicked.connect(lambda: self._actions.normalize_song())
        self.normalize_button.setToolTip("Normalize audio volume of selected songs")

        self.delete_button = QPushButton("Delete")
        self.delete_button.clicked.connect(self.onDeleteButtonClicked)
        self.delete_button.setToolTip("Delete selected song directories (permanently)")

    def _setup_layout(self):
        """Setup the widget layout with table view and action buttons."""
        bottom_bar = QHBoxLayout()
        bottom_bar.setContentsMargins(0, 5, 0, 0)
        bottom_bar.setSpacing(2)
        bottom_bar.addWidget(self.detectButton)
        bottom_bar.addWidget(self.openFolderButton)
        bottom_bar.addWidget(self.open_usdx_button)
        bottom_bar.addWidget(self.reload_button)
        bottom_bar.addWidget(self.normalize_button)
        bottom_bar.addWidget(self.delete_button)
        bottom_bar.addStretch()
        bottom_bar.addWidget(self.countLabel)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.tableView)
        layout.addLayout(bottom_bar)
        self.setLayout(layout)

    def _connect_model_signals(self):
        """Connect model data change signals to UI update handlers."""
        self.tableModel.dataChanged.connect(lambda *args: self.proxyModel.invalidate())
        self.proxyModel.dataChanged.connect(lambda *args: self.tableView.reset_viewport_loading())
        self.tableModel.dataChanged.connect(lambda *args: self.tableView.reset_viewport_loading())
        self.tableModel.dataChanged.connect(lambda *args: self._refresh_action_buttons())

        self.tableModel.rowsInserted.connect(self.updateCountLabel)
        self.tableModel.rowsRemoved.connect(self.updateCountLabel)
        self.tableModel.modelReset.connect(self.updateCountLabel)
        self.proxyModel.rowsInserted.connect(self.updateCountLabel)
        self.proxyModel.rowsRemoved.connect(self.updateCountLabel)
        self.proxyModel.modelReset.connect(self.updateCountLabel)

    def _connect_action_signals(self):
        """Connect action and filter signals to handlers."""
        self.songs_model.filterChanged.connect(self.updateFilter)
        self._data.selected_songs_changed.connect(self.onSelectedSongsChanged)
        self.songs_model.updated.connect(self._on_song_updated)

    def _refresh_action_buttons(self):
        """Recompute and apply action button enabled/tooltip states for current selection."""
        self.onSelectedSongsChanged(self._selected_songs)

    def _on_song_updated(self, song: Song):
        """Refresh buttons if an updated song is currently selected (status change, etc.)."""
        if not self._selected_songs:
            # Only invalidate filter if song is not selected (selected songs always visible)
            # Use longer delay to batch multiple updates
            QTimer.singleShot(100, self.proxyModel.invalidate)
            return
        # Compare by identity or stable key (txt_file) to detect if affected
        sel_txts = {s.txt_file for s in self._selected_songs if getattr(s, "txt_file", None)}
        if (song in self._selected_songs) or (getattr(song, "txt_file", None) in sel_txts):
            # If status transitioned to PROCESSING for any selected song, request media unload
            try:
                if hasattr(song, "status") and song.status == SongStatus.PROCESSING:
                    # Emit unload signal once (idempotent for multiple songs)
                    self._data.media_unload_requested.emit()
            except Exception:
                pass
            self._refresh_action_buttons()
            # Only invalidate filter if this affects visibility
            QTimer.singleShot(100, self.proxyModel.invalidate)

    def onDetectClicked(self):
        """Handle Detect button: unload current media then start gap detection.

        Unloading first prevents the player holding file handles while workers
        read/normalize audio, reducing freeze risk on Windows file locks.
        """
        try:
            self._data.media_unload_requested.emit()
        except Exception:
            pass
        # Proceed with gap detection (overwrite=True keeps previous results logic)
        self._actions.detect_gap(overwrite=True)

    def onDeleteButtonClicked(self):
        """Handle delete button click with confirmation dialog."""
        if not self._selected_songs:
            return

        count = len(self._selected_songs)
        if count == 1:
            msg_text = f"Are you sure you want to delete the following directory?\r\n{self._selected_songs[0].path}?"
        else:
            msg_text = f"Are you sure you want to delete the {count} selected song directories?"

        msgBox = QMessageBox()
        msgBox.setIcon(QMessageBox.Icon.Warning)
        msgBox.setText(msg_text)
        msgBox.setWindowTitle("Delete Confirmation")
        msgBox.setStandardButtons(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)

        returnValue = msgBox.exec()
        if returnValue == QMessageBox.StandardButton.Ok:
            self._actions.delete_selected_song()

    def onSelectedSongsChanged(self, songs: List[Song]):
        """Update button states based on selected songs."""
        self._selected_songs = songs
        num_selected = len(songs)
        first_song = songs[0] if num_selected > 0 else None

        has_selection = num_selected > 0
        is_busy_selection = has_selection and any(s.status in (SongStatus.QUEUED, SongStatus.PROCESSING) for s in songs)

        self._update_basic_action_buttons(has_selection, is_busy_selection)
        self._update_detect_button(songs, has_selection, is_busy_selection)
        self._update_normalize_button(songs, has_selection, is_busy_selection)
        self._update_usdb_button(num_selected, first_song)

        # Invalidate filter to show/hide songs based on new selection
        # (selected songs are always visible regardless of filter)
        QTimer.singleShot(0, self.proxyModel.invalidate)

    def _update_basic_action_buttons(self, has_selection: bool, is_busy_selection: bool):
        """Update open folder, reload, and delete button states."""
        # Open folder and reload are safe even when queued/processing
        self.openFolderButton.setEnabled(has_selection)
        self.reload_button.setEnabled(has_selection)

        # Delete is dangerous - keep disabled when busy
        delete_enabled = has_selection and not is_busy_selection
        self.delete_button.setEnabled(delete_enabled)

        if is_busy_selection:
            busy_tip = "Disabled while selected song(s) are queued or processing"
            self.delete_button.setToolTip(busy_tip)
        else:
            self.reload_button.setToolTip("Reload song data from file")
            self.delete_button.setToolTip("Delete selected song directories (permanently)")

    def _update_detect_button(self, songs: List[Song], has_selection: bool, is_busy_selection: bool):
        """Update detect button state and tooltip based on selection and system capabilities."""
        can_detect_songs = has_selection and any(s.audio_file for s in songs)
        system_can_detect = self._data.capabilities and self._data.capabilities.can_detect

        has_queued_detect = False
        if can_detect_songs and system_can_detect:
            has_queued_detect = self._check_queued_task(songs, "DetectGapWorker")

        can_detect = can_detect_songs and system_can_detect and not has_queued_detect and not is_busy_selection
        self.detectButton.setEnabled(can_detect)

        # Update tooltip
        if is_busy_selection:
            tooltip = "Gap detection disabled: selected song(s) are queued or processing"
        elif not system_can_detect:
            tooltip = self._get_detect_disabled_reason()
        elif not can_detect_songs:
            tooltip = "Select songs with audio files to detect gap"
        elif has_queued_detect:
            tooltip = "Gap detection already queued/running for selected song(s)"
        else:
            mode = "GPU" if self._data.capabilities and self._data.capabilities.has_cuda else "CPU"
            tooltip = f"Run gap detection on selected songs (Mode: {mode})"

        self.detectButton.setToolTip(tooltip)

    def _get_detect_disabled_reason(self) -> str:
        """Get the reason why gap detection is disabled based on system capabilities."""
        if not self._data.capabilities:
            return "Gap detection disabled: System requirements not met"

        if not self._data.capabilities.has_torch:
            return (
                "Gap detection disabled: PyTorch not available\n"
                "→ Reinstall the application or install PyTorch manually"
            )

        if not self._data.capabilities.has_ffmpeg:
            return "Gap detection disabled: FFmpeg not available\n→ Install FFmpeg and add to system PATH"

        return "Gap detection disabled: System requirements not met"

    def _update_normalize_button(self, songs: List[Song], has_selection: bool, is_busy_selection: bool):
        """Update normalize button state and tooltip."""
        can_normalize_songs = has_selection and any(s.audio_file for s in songs)
        has_queued_normalize = self._check_queued_task(songs, "NormalizeAudioWorker") if can_normalize_songs else False
        can_normalize = can_normalize_songs and not has_queued_normalize and not is_busy_selection
        self.normalize_button.setEnabled(can_normalize)

        if is_busy_selection:
            tooltip = "Audio normalization disabled: selected song(s) are queued or processing"
        elif has_queued_normalize:
            tooltip = "Audio normalization already queued/running for selected song(s)"
        else:
            tooltip = "Normalize audio volume of selected songs"

        self.normalize_button.setToolTip(tooltip)

    def _check_queued_task(self, songs: List[Song], worker_name: str) -> bool:
        """Check if any selected song has a specific worker task queued/running."""
        for song in songs:
            if song.audio_file and self._data.worker_queue.is_task_queued_for_song(song.txt_file, worker_name):
                return True
        return False

    def _update_usdb_button(self, num_selected: int, first_song: Song | None):
        """Update USDB button state (enabled only for single song with valid usdb_id)."""
        can_open_usdb = bool(
            (num_selected == 1)
            and (first_song is not None)
            and (first_song.usdb_id is not None)
            and (first_song.usdb_id != 0)
        )
        self.open_usdx_button.setEnabled(can_open_usdb)

    def updateFilter(self):
        """Update filter with deferred invalidation to prevent UI freeze."""
        self.proxyModel.selectedStatuses = self.songs_model.filter
        self.proxyModel.textFilter = self.songs_model.filter_text.lower()

        # Defer filter invalidation to next event loop iteration
        # This prevents blocking the UI thread during filter evaluation
        QTimer.singleShot(0, self._apply_deferred_filter)

    def _apply_deferred_filter(self):
        """Apply the filter invalidation in a deferred manner."""
        # Use invalidate() to refresh both filtering and sorting mappings
        self.proxyModel.invalidate()
        # Update count after filter is applied
        QTimer.singleShot(10, self.updateCountLabel)

    def updateCountLabel(self):
        total_songs = len(self.songs_model.songs)
        shown_songs = self.proxyModel.rowCount()
        label_text = f"Showing {shown_songs} of {total_songs} songs"
        self.countLabel.setText(label_text)
        logger.debug("Song count updated: %s", label_text)

    def start_chunked_load(self, songs: List[Song]):
        """Start chunked loading for large song lists."""
        if not songs:
            return

        # If the dataset is small, load directly
        if len(songs) <= CHUNK_SIZE:
            logger.info(f"Small dataset ({len(songs)} songs), loading directly")
            return  # Let normal signal-based loading handle it

        logger.info(f"Starting chunked loading for {len(songs)} songs")

        # Disable sorting and dynamic filtering during streaming
        self.tableView.setSortingEnabled(False)
        self.proxyModel.setDynamicSortFilter(False)

        # Prepare streaming
        self._streaming_songs = songs
        self._streaming_index = 0

        # Start the streaming process
        self.tableModel.load_data_async_start(len(songs))

        # Start chunked append with timer
        self._streaming_timer.start(CHUNK_DELAY_MS)

    def _append_next_chunk(self):
        """Append the next chunk of songs during streaming."""
        if self._streaming_index >= len(self._streaming_songs):
            # Streaming complete
            self._streaming_timer.stop()
            self._complete_chunked_load()
            return

        # Get next chunk
        end_index = min(self._streaming_index + CHUNK_SIZE, len(self._streaming_songs))
        chunk = self._streaming_songs[self._streaming_index : end_index]

        # Append to model
        self.tableModel.load_data_async_append(chunk)

        # Update progress
        self._streaming_index = end_index
        progress = (self._streaming_index / len(self._streaming_songs)) * 100
        logger.debug(f"Streaming progress: {progress:.1f}% ({self._streaming_index}/{len(self._streaming_songs)})")

    def _complete_chunked_load(self):
        """Complete chunked loading and restore UI features."""
        logger.info("Chunked loading complete, restoring UI features")

        # Complete streaming
        self.tableModel.load_data_async_complete()

        # Re-enable sorting and filtering
        self.proxyModel.setDynamicSortFilter(True)
        self.tableView.setSortingEnabled(True)

        # Apply column resizing if needed
        if hasattr(self.tableView, "apply_resize_policy"):
            self.tableView.apply_resize_policy()

        # Trigger viewport-based lazy loading for visible songs
        if hasattr(self.tableView, "reset_viewport_loading"):
            self.tableView.reset_viewport_loading()

        # Clear streaming state
        self._streaming_songs = []
        self._streaming_index = 0
