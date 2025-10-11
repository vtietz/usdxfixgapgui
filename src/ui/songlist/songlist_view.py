from PySide6.QtWidgets import QHeaderView, QTableView, QAbstractItemView
from PySide6.QtCore import Signal, Qt, QTimer
import logging

from actions import Actions
from model.song import Song
from ui.songlist.songlist_model import SongTableModel

logger = logging.getLogger(__name__)

# CRITICAL: ResizeToContents is a major performance killer!
# Always use fixed widths for large datasets
LARGE_DATASET_THRESHOLD = 100  # Very low threshold - favor performance
RESIZE_DEBOUNCE_MS = 200  # Delay before re-enabling expensive operations after resize

class SongListView(QTableView):
    selected_songs_changed = Signal(list) # Emits list of selected Song objects

    def __init__(self, model: SongTableModel, actions: Actions, parent=None):
        super().__init__(parent)
        self.setModel(model)
        self.tableModel = model
        self.actions = actions

        # Connect selection changed signal
        self.selectionModel().selectionChanged.connect(self.onSelectionChanged)
        # Connect the view's signal to the action handler
        self.selected_songs_changed.connect(actions.set_selected_songs)
        
        # Resize optimization state
        self._resize_timer = QTimer()
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(RESIZE_DEBOUNCE_MS)
        self._resize_timer.timeout.connect(self._on_resize_finished)
        self._is_resizing = False
        self._original_header_modes = {}  # Store original header resize modes
        self._auto_fit_enabled = True  # Allow auto-fit for small datasets

        self.setupUi()

    def setupUi(self):
        self.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        # Allow selecting multiple rows
        self.setSelectionMode(QTableView.SelectionMode.ExtendedSelection)
        self.setSortingEnabled(True)
        self.horizontalHeader().setSortIndicatorShown(True)
        self.horizontalHeader().setSectionsClickable(True)

        # CRITICAL PERFORMANCE OPTIMIZATIONS
        # Scroll per pixel for smoother experience
        self.setVerticalScrollMode(QTableView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollMode(QTableView.ScrollMode.ScrollPerPixel)
        
        # Fixed vertical header to prevent row height recalculation
        # This effectively gives us uniform row heights (24px for all rows)
        self.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.verticalHeader().setDefaultSectionSize(24)  # Standard row height

        # Apply initial resize policy (conservative for large datasets)
        self.apply_resize_policy()

        self.setColumnWidth(9, 100)

        # Sorting by the first column initially
        self.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        
        # Capture original header modes after setup for restore during resize
        self._capture_header_modes()
    
    def apply_resize_policy(self):
        """Apply column resize policy based on dataset size."""
        # Get the source model to check row count
        source_model = None
        if hasattr(self.model(), 'sourceModel'):
            source_model = self.model().sourceModel()
        else:
            source_model = self.model()
        
        row_count = source_model.rowCount() if source_model else 0
        
        # For large datasets, use fixed width or stretch to avoid expensive resizing
        if row_count > LARGE_DATASET_THRESHOLD:
            logger.info(f"Large dataset ({row_count} rows), using conservative resize policy")
            for i in range(12):
                if i < 3:
                    # Keep first 3 columns stretchy
                    self.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
                else:
                    # Use fixed mode for others to avoid expensive calculations
                    self.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
                    # Set reasonable default widths
                    if i in [3, 4, 5, 6, 7, 8, 10]:  # Numeric columns
                        self.setColumnWidth(i, 80)
                    elif i == 9:  # Time
                        self.setColumnWidth(i, 100)
                    elif i == 11:  # Status
                        self.setColumnWidth(i, 120)
        else:
            # For small datasets, use ResizeToContents for better appearance
            logger.info(f"Small dataset ({row_count} rows), using ResizeToContents policy")
            for i in range(12):
                resize_mode = QHeaderView.ResizeMode.Stretch if i < 3 else QHeaderView.ResizeMode.ResizeToContents
                self.horizontalHeader().setSectionResizeMode(i, resize_mode)


    def onSelectionChanged(self, selected, deselected):
        selected_songs = []
        source_model = self.model().sourceModel()
        # Use selectedRows() to get all selected rows
        for index in self.selectionModel().selectedRows():
            source_index = self.model().mapToSource(index)
            if source_index.isValid() and source_index.row() < len(source_model.songs):
                song: Song = source_model.songs[source_index.row()]
                selected_songs.append(song)
            else:
                logger.warning(f"Invalid source index obtained: {source_index.row()}")

        if selected_songs:
            first_song = selected_songs[0]
            logger.debug(f"Selected {len(selected_songs)} songs. First: {first_song.title} by {first_song.artist}")
        else:
            logger.debug("Selection cleared.")

        # Emit the list of selected songs
        self.selected_songs_changed.emit(selected_songs)

        # Keep single song selection action for compatibility if needed elsewhere,
        # but primary handling should use the list via selected_songs_changed.
        # If actions.select_song is only used for single selection logic (e.g., detail view),
        # it might need adjustment or removal depending on overall architecture.
        # For now, let's assume the main handling is via set_selected_songs in Actions.
        # if selected_songs:
        #     self.actions.select_song(selected_songs[0].path) # Or adapt select_song if needed
    
    def _capture_header_modes(self):
        """Capture current header resize modes for restoration after resize."""
        header = self.horizontalHeader()
        column_count = header.count()
        self._original_header_modes = {}
        for i in range(column_count):
            self._original_header_modes[i] = header.sectionResizeMode(i)
        logger.debug(f"Captured {len(self._original_header_modes)} header modes")
    
    def resizeEvent(self, event):
        """Handle resize events with hard freeze to prevent performance issues."""
        super().resizeEvent(event)
        
        # On first resize, disable expensive operations and freeze painting
        if not self._is_resizing:
            self._is_resizing = True
            self._disable_expensive_operations()
        
        # Restart the debounce timer
        self._resize_timer.start()
    
    def _disable_expensive_operations(self):
        """Temporarily disable expensive operations during resize with hard freeze."""
        # HARD FREEZE: Stop all repaints during active resize
        self.setUpdatesEnabled(False)
        
        # Disable sorting during resize
        self.setSortingEnabled(False)
        
        # Disable dynamic filtering on proxy model if available
        model = self.model()
        if hasattr(model, 'setDynamicSortFilter'):
            model.setDynamicSortFilter(False)
        
        # Freeze all columns to Fixed mode to prevent per-pixel width recalculation
        header = self.horizontalHeader()
        column_count = header.count()
        for i in range(column_count):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
        
        logger.debug("Hard freeze: disabled updates, sorting, filtering, and header resize")
    
    def _on_resize_finished(self):
        """Re-enable expensive operations after resize has settled with batched refresh."""
        self._is_resizing = False
        
        # Restore in optimal order to avoid thrash
        # 1. Restore original header modes first
        header = self.horizontalHeader()
        for col_idx, mode in self._original_header_modes.items():
            header.setSectionResizeMode(col_idx, mode)
        
        # 2. Check dataset size before applying auto-fit
        model = self.model()
        source_model = None
        if hasattr(model, 'sourceModel'):
            source_model = model.sourceModel()
        else:
            source_model = model
        
        row_count = source_model.rowCount() if source_model else 0
        
        # 4. Conditionally apply auto-fit only for small datasets
        if self._auto_fit_enabled and row_count <= LARGE_DATASET_THRESHOLD and row_count > 0:
            logger.debug(f"Applying single auto-fit pass for small dataset ({row_count} rows)")
            # Only resize text columns selectively
            for i in [0, 1, 2]:  # Path, Artist, Title
                if i in self._original_header_modes:
                    mode = self._original_header_modes[i]
                    if mode == QHeaderView.ResizeMode.ResizeToContents:
                        self.resizeColumnToContents(i)
        
        # 5. Re-enable dynamic filtering (must be before sorting)
        if hasattr(model, 'setDynamicSortFilter'):
            model.setDynamicSortFilter(True)
        
        # 6. Re-enable sorting
        self.setSortingEnabled(True)
        
        # 7. FINAL: Re-enable updates to batch all changes into single repaint
        self.setUpdatesEnabled(True)
        
        logger.debug("Resize finished: restored all operations with single batched refresh")


