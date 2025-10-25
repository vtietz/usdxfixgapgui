from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QMessageBox
from PySide6.QtCore import QSortFilterProxyModel, QTimer
from actions import Actions
from app.app_data import AppData
from model.song import Song
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
            textMatch = (self.textFilter in cache_entry['artist_lower'] or
                         self.textFilter in cache_entry['title_lower'])
        else:
            # Fallback to direct lowercase conversion
            textMatch = (self.textFilter in song.artist.lower() or
                         self.textFilter in song.title.lower())

        return statusMatch and textMatch

class SongListWidget(QWidget):
    def __init__(self, songs_model: Songs, actions: Actions, data: AppData,parent=None):
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

        # Create action buttons (moved from MenuBar)
        self.detectButton = QPushButton("Detect")
        self.detectButton.clicked.connect(lambda: self._actions.detect_gap(overwrite=True))

        self.openFolderButton = QPushButton("Open Folder")
        self.openFolderButton.clicked.connect(lambda: self._actions.open_folder())

        self.open_usdx_button = QPushButton("Open in USDB")
        self.open_usdx_button.clicked.connect(lambda: self._actions.open_usdx())

        self.reload_button = QPushButton("Reload")
        self.reload_button.clicked.connect(lambda: self._actions.reload_song())

        self.normalize_button = QPushButton("Normalize")
        self.normalize_button.clicked.connect(lambda: self._actions.normalize_song())

        self.delete_button = QPushButton("Delete")
        self.delete_button.clicked.connect(self.onDeleteButtonClicked)

        # Create song count label
        self.countLabel = QLabel()

        # Create bottom bar layout with buttons on left and count on right
        bottom_bar = QHBoxLayout()
        bottom_bar.setContentsMargins(0, 5, 0, 0)
        bottom_bar.setSpacing(5)

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

        # Streaming state
        self._streaming_songs: List[Song] = []
        self._streaming_index = 0
        self._streaming_timer = QTimer()
        self._streaming_timer.timeout.connect(self._append_next_chunk)

        # Initial update of the count label and button states
        self.updateCountLabel()
        self.onSelectedSongsChanged([])  # Initial state

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
        self.openFolderButton.setEnabled(has_selection)
        self.reload_button.setEnabled(has_selection)
        self.delete_button.setEnabled(has_selection)

        # Enable detect if at least one selected song has audio file
        can_detect = has_selection and any(s.audio_file for s in songs)
        self.detectButton.setEnabled(can_detect)

        # Enable normalize if at least one selected song is suitable
        can_normalize = has_selection and any(s.audio_file for s in songs)
        self.normalize_button.setEnabled(can_normalize)

        # Enable USDB only if exactly one song is selected and has a valid usdb_id
        can_open_usdb = bool(
            (num_selected == 1)
            and (first_song is not None)
            and (first_song.usdb_id is not None)
            and (first_song.usdb_id != "")
            and (first_song.usdb_id != "0")
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
        chunk = self._streaming_songs[self._streaming_index:end_index]

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
        if hasattr(self.tableView, 'apply_resize_policy'):
            self.tableView.apply_resize_policy()

        # Trigger viewport-based lazy loading for visible songs
        if hasattr(self.tableView, 'reset_viewport_loading'):
            self.tableView.reset_viewport_loading()

        # Clear streaming state
        self._streaming_songs = []
        self._streaming_index = 0
