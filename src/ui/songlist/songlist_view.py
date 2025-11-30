from PySide6.QtWidgets import QHeaderView, QTableView
from PySide6.QtCore import Signal, Qt, QTimer, QSortFilterProxyModel
import logging

from actions import Actions
from model.song import Song, SongStatus
from ui.common.column_layout import ColumnDefaults, ColumnLayoutController
from ui.songlist.songlist_model import SongTableModel

logger = logging.getLogger(__name__)

# CRITICAL: ResizeToContents is a major performance killer!
RESIZE_DEBOUNCE_MS = 200  # Delay before re-enabling expensive operations after resize

COLUMN_DEFAULT_WIDTHS = {
    3: 60,
    4: 60,
    5: 60,
    6: 60,
    7: 60,
    8: 60,
    9: 100,
    10: 60,
    11: 120,
}

PRIMARY_COLUMN_RATIOS = (0.4, 0.35, 0.25)  # Path, Artist, Title share of remaining width
PRIMARY_COLUMN_MIN_WIDTH = 120

# Viewport-based lazy loading configuration
VIEWPORT_LOAD_DELAY_MS = 100  # Delay before loading visible songs
VIEWPORT_BUFFER_ROWS = 10  # Load this many extra rows above/below viewport


class SongListView(QTableView):
    selected_songs_changed = Signal(list)  # Emits list of selected Song objects

    def __init__(self, model, actions: Actions, parent=None):
        super().__init__(parent)
        self.setModel(model)
        # Track both proxy and source model for robust mapping
        self.proxyModel = model if isinstance(model, QSortFilterProxyModel) else None
        self.tableModel = self.proxyModel.sourceModel() if self.proxyModel else model
        # Avoid name clash with QWidget.actions() method
        self.ui_actions = actions

        # Connect selection changed signal
        self.selectionModel().selectionChanged.connect(self.onSelectionChanged)
        # Connect the view's signal to the action handler
        self.selected_songs_changed.connect(actions.set_selected_songs)

        # Selection debounce timer to prevent rapid-fire selections
        self._selection_timer = QTimer()
        self._selection_timer.setSingleShot(True)
        self._selection_timer.setInterval(150)  # 150ms debounce
        self._selection_timer.timeout.connect(self._process_selection)
        self._pending_selection = None

        # Re-trigger viewport lazy-loading whenever data changes in proxy or source
        model.dataChanged.connect(lambda *args: self.reset_viewport_loading())
        if self.tableModel is not model:
            self.tableModel.dataChanged.connect(lambda *args: self.reset_viewport_loading())

        # Resize optimization state
        self._resize_timer = QTimer()
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(RESIZE_DEBOUNCE_MS)
        self._resize_timer.timeout.connect(self._on_resize_finished)
        self._is_resizing = False
        self._original_header_modes = {}  # Store original header resize modes

        # Viewport-based lazy loading state
        self._viewport_timer = QTimer()
        self._viewport_timer.setSingleShot(True)
        self._viewport_timer.setInterval(VIEWPORT_LOAD_DELAY_MS)
        self._viewport_timer.timeout.connect(self._load_visible_songs)
        self._loaded_rows = set()  # Track which rows have been loaded

        column_defaults = ColumnDefaults(
            numeric_widths=COLUMN_DEFAULT_WIDTHS,
            primary_ratios=PRIMARY_COLUMN_RATIOS,
            primary_min_width=PRIMARY_COLUMN_MIN_WIDTH,
            primary_columns=(0, 1, 2),
        )
        self._column_layout = ColumnLayoutController(self, column_defaults)

        self.setupUi()

    def setupUi(self):
        self.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        # Allow selecting multiple rows
        self.setSelectionMode(QTableView.SelectionMode.ExtendedSelection)
        self.setSortingEnabled(True)
        self.horizontalHeader().setSortIndicatorShown(True)
        self.horizontalHeader().setSectionsClickable(True)
        self.horizontalHeader().setSectionsMovable(True)

        # CRITICAL PERFORMANCE OPTIMIZATIONS
        # Scroll per pixel for smoother experience
        self.setVerticalScrollMode(QTableView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollMode(QTableView.ScrollMode.ScrollPerPixel)

        # Fixed vertical header to prevent row height recalculation
        # This effectively gives us uniform row heights (24px for all rows)
        self.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.verticalHeader().setDefaultSectionSize(24)  # Standard row height

        # Apply initial resize policy (fixed layout for performance)
        self.apply_resize_policy()

        # Sorting by the first column initially
        self.sortByColumn(0, Qt.SortOrder.AscendingOrder)

        # Capture original header modes after setup for restore during resize
        self._capture_header_modes()

    def apply_resize_policy(self):
        """Delegate to shared column layout controller."""
        self._column_layout.apply_policy()

    def onSelectionChanged(self, selected, deselected):
        """Debounce selection changes to prevent rapid-fire updates"""
        # Restart the debounce timer
        self._selection_timer.stop()
        self._selection_timer.start()

    def _process_selection(self):
        """Actually process the selection after debounce period"""
        import time

        start_time = time.perf_counter()

        selected_songs = []
        # Resolve source model robustly
        proxy_model = self.model()
        source_model = proxy_model.sourceModel() if isinstance(proxy_model, QSortFilterProxyModel) else proxy_model

        # If the underlying model isn't SongTableModel, we cannot extract Song instances
        if not isinstance(source_model, SongTableModel):
            logger.debug("Selection changed but source model is not SongTableModel")
            self.selected_songs_changed.emit(selected_songs)
            return

        # Use selectedRows() to get all selected rows
        for index in self.selectionModel().selectedRows():
            source_index = proxy_model.mapToSource(index) if isinstance(proxy_model, QSortFilterProxyModel) else index
            if source_index.isValid() and source_index.row() < len(source_model.songs):
                song: Song = source_model.songs[source_index.row()]
                selected_songs.append(song)
            else:
                logger.warning(f"Invalid source index obtained: {source_index.row()}")

        duration_ms = (time.perf_counter() - start_time) * 1000
        if duration_ms > 50:
            logger.warning(f"SLOW selection processing: {duration_ms:.1f}ms for {len(selected_songs)} songs")

        if selected_songs:
            first_song = selected_songs[0]
            logger.debug(f"Song selected: {first_song.title} by {first_song.artist} ({len(selected_songs)} total)")
        else:
            logger.debug("Selection cleared")

        # Emit the list of selected songs
        self.selected_songs_changed.emit(selected_songs)

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
        if isinstance(model, QSortFilterProxyModel):
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

        model = self.model()

        # Re-enable dynamic filtering (must be before sorting)
        if isinstance(model, QSortFilterProxyModel):
            model.setDynamicSortFilter(True)

        # Re-enable sorting
        self.setSortingEnabled(True)

        # Ensure columns still span the viewport before repaint
        self._column_layout.rebalance_viewport()

        # FINAL: Re-enable updates to batch all changes into single repaint
        self.setUpdatesEnabled(True)

        logger.debug("Resize finished: restored all operations with single batched refresh")

    def scrollContentsBy(self, dx, dy):
        """Override scroll handler to trigger lazy loading of visible songs."""
        super().scrollContentsBy(dx, dy)

        # Trigger viewport load after scrolling stops
        if self._viewport_timer.isActive():
            self._viewport_timer.stop()
        self._viewport_timer.start()

    def _load_visible_songs(self):
        """Load song data for songs currently visible in the viewport."""
        # Get the viewport rect and find visible rows
        viewport_rect = self.viewport().rect()
        top_index = self.indexAt(viewport_rect.topLeft())
        bottom_index = self.indexAt(viewport_rect.bottomLeft())

        if not top_index.isValid() or not bottom_index.isValid():
            return

        # Get source model
        proxy_model = self.model()
        source_model = proxy_model.sourceModel() if isinstance(proxy_model, QSortFilterProxyModel) else proxy_model

        if not isinstance(source_model, SongTableModel):
            return

        # Calculate row range with buffer
        first_row = max(0, top_index.row() - VIEWPORT_BUFFER_ROWS)
        last_row = min(proxy_model.rowCount() - 1, bottom_index.row() + VIEWPORT_BUFFER_ROWS)

        # Collect songs that need loading
        songs_to_load = []
        for proxy_row in range(first_row, last_row + 1):
            proxy_index = proxy_model.index(proxy_row, 0)
            source_index = (
                proxy_model.mapToSource(proxy_index) if isinstance(proxy_model, QSortFilterProxyModel) else proxy_index
            )

            if not source_index.isValid() or source_index.row() in self._loaded_rows:
                continue

            if source_index.row() < len(source_model.songs):
                song = source_model.songs[source_index.row()]

                # Check if song needs loading (missing critical data)
                if self._song_needs_loading(song):
                    songs_to_load.append(song)
                    self._loaded_rows.add(source_index.row())

        # Load songs if any need loading
        if songs_to_load:
            logger.debug(f"Viewport lazy-loading {len(songs_to_load)} songs (rows {first_row}-{last_row})")
            self._reload_songs_in_background(songs_to_load)

    def _song_needs_loading(self, song: Song) -> bool:
        """Check if a song needs to be loaded (has empty/missing data)."""
        # Song needs loading if it's NOT_PROCESSED and missing critical data
        if song.status != SongStatus.NOT_PROCESSED:
            return False

        # Check if essential fields are missing
        needs_load = (
            not song.title or not song.artist or song.bpm == 0 or not hasattr(song, "notes") or song.notes is None
        )

        return needs_load

    def _reload_songs_in_background(self, songs):
        """Trigger light reload of songs for viewport lazy-loading.
        Uses metadata-only reload that does NOT change status or queue workers."""
        logger.debug(f"Triggering light reload for {len(songs)} songs in viewport")
        for song in songs:
            logger.debug(f"  - Light-reloading: {song.title or song.path}")
            # Use light reload instead of full reload to avoid waveform generation
            self.ui_actions.reload_song_light(specific_song=song)

    def reset_viewport_loading(self):
        """Reset viewport loading state (call when data changes)."""
        self._loaded_rows.clear()
        # Trigger initial load
        QTimer.singleShot(100, self._load_visible_songs)
