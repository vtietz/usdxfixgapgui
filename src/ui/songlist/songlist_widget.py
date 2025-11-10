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
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.selectedStatuses = []
        self.textFilter = ""

    def filterAcceptsRow(self, source_row, source_parent):
        # Fast-path: skip filtering if no filters are active
        if not self.selectedStatuses and not self.textFilter:
            return True

        # Access the source model's data for the given row
        source_model = cast(SongTableModel, self.sourceModel())
        song: Song = source_model.songs[source_row]

        # Implement filtering logic
        statusMatch = song.status.name in self.selectedStatuses if self.selectedStatuses else True

        # Prefer cached lowercase strings from model if available
        cache_entry = source_model._row_cache.get(song.path) if hasattr(source_model, "_row_cache") else None
        if cache_entry:
            textMatch = self.textFilter in cache_entry["artist_lower"] or self.textFilter in cache_entry["title_lower"]
        else:
            # Fallback to direct lowercase conversion
            textMatch = self.textFilter in song.artist.lower() or self.textFilter in song.title.lower()

        return statusMatch and textMatch


class SongListWidget(QWidget):
    def __init__(self, songs_model: Songs, actions: Actions, data: AppData, parent=None):
        super().__init__(parent)
        # actions are passed to the view; no instance attribute to avoid clashing with QWidget.actions()

        # Store actions and data for button handling
        self._actions = actions
        self._data = data
        self._selected_songs: List[Song] = []

        # Create the table model and proxy model
        self.songs_model = songs_model
        self.tableModel = SongTableModel(songs_model, data)
        self.proxyModel = CustomSortFilterProxyModel()
        self.proxyModel.setSourceModel(self.tableModel)
        # Ensure proxy dynamically re-sorts/refilters on source changes
        self.proxyModel.setDynamicSortFilter(True)

        self.tableView = SongListView(self.proxyModel, actions)
        # Propagate data refreshes across proxy/view and re-trigger viewport lazy-loading
        self.tableModel.dataChanged.connect(lambda *args: self.proxyModel.invalidate())
        self.proxyModel.dataChanged.connect(lambda *args: self.tableView.reset_viewport_loading())
        self.tableModel.dataChanged.connect(lambda *args: self.tableView.reset_viewport_loading())
        # Also refresh action buttons when any data changes (status updates etc.)
        self.tableModel.dataChanged.connect(lambda *args: self._refresh_action_buttons())

        # Create action buttons (moved from MenuBar)
        self.detectButton = QPushButton("Detect")
        # Wrap detect in a handler so we can unload media first (prevents player locks/freezes)
        self.detectButton.clicked.connect(self.onDetectClicked)
        # Initial tooltip (will be updated based on capabilities in updateButtonStates)
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

        # Create song count label
        self.countLabel = QLabel()

        # Create bottom bar layout with buttons on left and count on right
        bottom_bar = QHBoxLayout()
        bottom_bar.setContentsMargins(0, 5, 0, 0)
        bottom_bar.setSpacing(2)

        # Left side: action buttons
        bottom_bar.addWidget(self.detectButton)
        bottom_bar.addWidget(self.openFolderButton)
        bottom_bar.addWidget(self.open_usdx_button)
        bottom_bar.addWidget(self.reload_button)
        bottom_bar.addWidget(self.normalize_button)
        bottom_bar.addWidget(self.delete_button)

        # Stretch to push count label to the right
        bottom_bar.addStretch()

        # Right side: song count
        bottom_bar.addWidget(self.countLabel)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.tableView)
        layout.addLayout(bottom_bar)
        self.setLayout(layout)

        # Connect signals to update the filter and status label
        self.songs_model.filterChanged.connect(self.updateFilter)

        # Connect model signals to update count when data changes
        self.tableModel.rowsInserted.connect(self.updateCountLabel)
        self.tableModel.rowsRemoved.connect(self.updateCountLabel)
        self.tableModel.modelReset.connect(self.updateCountLabel)
        self.proxyModel.rowsInserted.connect(self.updateCountLabel)
        self.proxyModel.rowsRemoved.connect(self.updateCountLabel)
        self.proxyModel.modelReset.connect(self.updateCountLabel)

        # Connect to selected songs changed signal
        self._data.selected_songs_changed.connect(self.onSelectedSongsChanged)
        # Update buttons when any song is updated (e.g., status changes to/from QUEUED/PROCESSING)
        self.songs_model.updated.connect(self._on_song_updated)

        # Streaming state
        self._streaming_songs: List[Song] = []
        self._streaming_index = 0
        self._streaming_timer = QTimer()
        self._streaming_timer.timeout.connect(self._append_next_chunk)

        # Initial update of the count label and button states
        self.updateCountLabel()
        self.onSelectedSongsChanged([])  # Initial state

    def _refresh_action_buttons(self):
        """Recompute and apply action button enabled/tooltip states for current selection."""
        self.onSelectedSongsChanged(self._selected_songs)

    def _on_song_updated(self, song: Song):
        """Refresh buttons if an updated song is currently selected (status change, etc.)."""
        if not self._selected_songs:
            return
        # Compare by identity or stable key (txt_file) to detect if affected
        sel_txts = {s.txt_file for s in self._selected_songs if getattr(s, 'txt_file', None)}
        if (song in self._selected_songs) or (getattr(song, 'txt_file', None) in sel_txts):
            # If status transitioned to PROCESSING for any selected song, request media unload
            try:
                if hasattr(song, 'status') and song.status == SongStatus.PROCESSING:
                    # Emit unload signal once (idempotent for multiple songs)
                    self._data.media_unload_requested.emit()
            except Exception:
                pass
            self._refresh_action_buttons()

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

        # Enable buttons if at least one song is selected
        has_selection = num_selected > 0
        # Disable actions if any selected song is queued or processing
        is_busy_selection = has_selection and any(
            s.status in (SongStatus.QUEUED, SongStatus.PROCESSING) for s in songs
        )

        self.openFolderButton.setEnabled(has_selection and not is_busy_selection)
        self.reload_button.setEnabled(has_selection and not is_busy_selection)
        self.delete_button.setEnabled(has_selection and not is_busy_selection)

        # Update tooltips to clarify busy state for disabled actions
        if is_busy_selection:
            busy_tip = "Disabled while selected song(s) are queued or processing"
            self.reload_button.setToolTip(busy_tip)
            self.delete_button.setToolTip(busy_tip)
        else:
            self.reload_button.setToolTip("Reload song data from file")
            self.delete_button.setToolTip("Delete selected song directories (permanently)")

        # Enable detect if at least one selected song has audio file AND system can detect
        can_detect_songs = has_selection and any(s.audio_file for s in songs)
        system_can_detect = self._data.capabilities and self._data.capabilities.can_detect

        # Check if any selected song already has a detect task queued/running
        has_queued_detect = False
        if can_detect_songs and system_can_detect:
            for song in songs:
                if song.audio_file and self._data.worker_queue.is_task_queued_for_song(
                    song.txt_file, "DetectGapWorker"
                ):
                    has_queued_detect = True
                    break

        can_detect = can_detect_songs and system_can_detect and not has_queued_detect and not is_busy_selection
        self.detectButton.setEnabled(can_detect)

        # Update tooltip based on capability status
        if is_busy_selection:
            self.detectButton.setToolTip("Gap detection disabled: selected song(s) are queued or processing")
        elif not system_can_detect:
            if self._data.capabilities and not self._data.capabilities.has_torch:
                self.detectButton.setToolTip(
                    "Gap detection disabled: PyTorch not available\n"
                    "→ Reinstall the application or install PyTorch manually"
                )
            elif self._data.capabilities and not self._data.capabilities.has_ffmpeg:
                self.detectButton.setToolTip(
                    "Gap detection disabled: FFmpeg not available\n" "→ Install FFmpeg and add to system PATH"
                )
            else:
                self.detectButton.setToolTip("Gap detection disabled: System requirements not met")
        elif not can_detect_songs:
            self.detectButton.setToolTip("Select songs with audio files to detect gap")
        elif has_queued_detect:
            self.detectButton.setToolTip("Gap detection already queued/running for selected song(s)")
        else:
            # Show current detection mode in tooltip
            if self._data.capabilities and self._data.capabilities.has_cuda:
                mode = "GPU"
            else:
                mode = "CPU"
            self.detectButton.setToolTip(f"Run gap detection on selected songs (Mode: {mode})")

        # Enable normalize if at least one selected song is suitable
        can_normalize_songs = has_selection and any(s.audio_file for s in songs)

        # Check if any selected song already has a normalize task queued/running
        has_queued_normalize = False
        if can_normalize_songs:
            for song in songs:
                if song.audio_file and self._data.worker_queue.is_task_queued_for_song(
                    song.txt_file, "NormalizeAudioWorker"
                ):
                    has_queued_normalize = True
                    break

        can_normalize = can_normalize_songs and not has_queued_normalize and not is_busy_selection
        self.normalize_button.setEnabled(can_normalize)

        # Update tooltip for normalize button
        if is_busy_selection:
            self.normalize_button.setToolTip("Audio normalization disabled: selected song(s) are queued or processing")
        elif has_queued_normalize:
            self.normalize_button.setToolTip("Audio normalization already queued/running for selected song(s)")
        else:
            self.normalize_button.setToolTip("Normalize audio volume of selected songs")

        # Enable USDB only if exactly one song is selected and has a valid usdb_id
        # usdb_id is Optional[int], so check for None and 0
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
        self.countLabel.setText(f"Showing {shown_songs} of {total_songs} songs")

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
