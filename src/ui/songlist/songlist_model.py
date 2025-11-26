import time
from typing import List
from PySide6.QtCore import QAbstractTableModel, Qt, QModelIndex, QTimer, Signal
from PySide6.QtGui import QColor
import logging

from app.app_data import AppData
from model.song import Song, SongStatus
from model.songs import Songs
from ui.songlist.columns import create_registry
from utils import files

logger = logging.getLogger(__name__)


class SongTableModel(QAbstractTableModel):
    # Custom signals for bulk loading optimization
    bulk_load_started = Signal()
    bulk_load_ended = Signal()
    def __init__(self, songs_model: Songs, data: AppData, parent=None):
        super().__init__(parent)
        self.app_data = data
        self.songs_model = songs_model
        self.songs: List[Song] = list(self.songs_model.songs)
        self.pending_songs = []
        self._bulk_loading = False  # Track whether we are inserting streaming batches
        self._bulk_started_at = 0.0

        # Column strategy registry
        base_dir = self.app_data.directory or self.app_data.config.default_directory or ""
        self._column_registry = create_registry(base_dir)

        # Performance optimizations
        self._row_cache = {}  # Cache for expensive computations
        self._is_streaming = False  # Flag for async loading
        self._dirty_rows = set()  # For throttled dataChanged emissions
        self._update_timer = QTimer()
        self._update_timer.setSingleShot(True)  # Single-shot timer for coalescing
        self._update_timer.setInterval(33)  # 33ms coalescing
        self._update_timer.timeout.connect(self._emit_coalesced_updates)

        # Connect signals
        self.songs_model.added.connect(self.song_added)
        self.songs_model.updated.connect(self.song_updated)
        self.songs_model.deleted.connect(self.song_deleted)
        self.songs_model.cleared.connect(self.songs_cleared)
        self.songs_model.listChanged.connect(self.list_changed)  # Handle batch updates

        # Timer for adding pending songs - reduced for better responsiveness
        self.timer = QTimer()
        self.timer.setInterval(100)  # 100ms instead of 1000ms for better UX
        self.timer.timeout.connect(self.add_pending_songs)

        # Build initial cache
        self._rebuild_cache()

    def song_added(self, song: Song):
        self.pending_songs.append(song)
        logger.debug(f"Added: {song}")
        if not self.timer.isActive():
            self.timer.start()

    def list_changed(self):
        """Handle list structure changes (batch operations and clears only)."""
        # Guard: Skip if pending_songs timer active (avoid race with song_added)
        if self.pending_songs or self.timer.isActive():
            logger.debug("list_changed skipped - pending_songs active, avoiding double-insert")
            return

        current_count = len(self.songs)
        model_count = len(self.songs_model.songs)
        delta = model_count - current_count

        if delta >= 1:  # Batch addition (1+ songs) - include single-row time-budgeted flushes
            # Signal bulk load start on first batch
            if not self._bulk_loading:
                self._bulk_loading = True
                self._bulk_started_at = time.perf_counter()
                self.bulk_load_started.emit()
                logger.info("SongTableModel bulk load started at %.1f ms", 0.0)

            new_songs = self.songs_model.songs[current_count:model_count]
            self.beginInsertRows(QModelIndex(), current_count, model_count - 1)
            self.songs.extend(new_songs)
            for song in new_songs:
                self._add_to_cache(song)
            self.endInsertRows()
            elapsed = 0.0
            if self._bulk_started_at:
                elapsed = (time.perf_counter() - self._bulk_started_at) * 1000
            logger.debug(
                "SongTableModel inserted %s songs via listChanged at %.1f ms (delta=%s)",
                len(new_songs),
                elapsed,
                delta,
            )
        elif model_count < current_count:  # Removal or clear
            self.songs_cleared()
            logger.debug("list_changed triggered songs_cleared (removal detected)")

        self._remap_selection_to_current_instances()

    def add_pending_songs(self):
        if self.pending_songs:
            self.beginInsertRows(QModelIndex(), len(self.songs), len(self.songs) + len(self.pending_songs) - 1)
            self.songs.extend(self.pending_songs)
            # Populate cache for newly added songs
            for song in self.pending_songs:
                self._add_to_cache(song)
            self.pending_songs.clear()
            self.endInsertRows()
        if not self.pending_songs:
            self.timer.stop()

    def end_bulk_loading(self):
        """Explicitly end bulk loading mode (called when loading finishes)."""
        if self._bulk_loading:
            self._bulk_loading = False
            self.bulk_load_ended.emit()
            elapsed = 0.0
            if self._bulk_started_at:
                elapsed = (time.perf_counter() - self._bulk_started_at) * 1000
            logger.info("SongTableModel bulk load ended at %.1f ms", elapsed)
            self._bulk_started_at = 0.0
            logger.debug("Bulk loading ended - dynamic filtering re-enabled")

    def _rebuild_cache(self):
        """Rebuild the entire cache from current songs list."""
        self._row_cache.clear()
        for song in self.songs:
            self._add_to_cache(song)

    def _add_to_cache(self, song: Song):
        """Add a single song to the cache."""
        relative_path = files.get_relative_path(self.app_data.directory, song.path)
        self._row_cache[song.path] = {
            "relative_path": relative_path,
            "relative_path_lower": relative_path.lower(),
            "artist_lower": song.artist.lower(),
            "title_lower": song.title.lower(),
            "title_sort_key": song.title_sort_key,
        }

    def _update_cache(self, song: Song):
        """Update cache entry for a song."""
        if song.path in self._row_cache:
            relative_path = files.get_relative_path(self.app_data.directory, song.path)
            self._row_cache[song.path]["relative_path"] = relative_path
            self._row_cache[song.path]["relative_path_lower"] = relative_path.lower()
            self._row_cache[song.path]["artist_lower"] = song.artist.lower()
            self._row_cache[song.path]["title_lower"] = song.title.lower()
            self._row_cache[song.path]["title_sort_key"] = song.title_sort_key

    def _remove_from_cache(self, song: Song):
        """Remove a song from the cache."""
        self._row_cache.pop(song.path, None)

    def _emit_coalesced_updates(self):
        """Emit dataChanged for accumulated dirty rows."""
        if not self._dirty_rows:
            return

        # Sort dirty rows and emit ranges
        sorted_rows = sorted(self._dirty_rows)
        if not sorted_rows:
            return

        ellipsis = "..." if len(sorted_rows) > 10 else ""
        logger.debug(f"Emitting dataChanged for {len(sorted_rows)} rows: " f"{sorted_rows[:10]}{ellipsis}")

        # Emit contiguous ranges
        start_row = sorted_rows[0]
        end_row = sorted_rows[0]

        for row in sorted_rows[1:]:
            if row == end_row + 1:
                end_row = row
            else:
                # Emit current range
                self.dataChanged.emit(
                    self.index(start_row, 0),
                    self.index(end_row, self.columnCount() - 1),
                    [
                        Qt.ItemDataRole.DisplayRole,
                        Qt.ItemDataRole.BackgroundRole,
                        Qt.ItemDataRole.TextAlignmentRole,
                    ],
                )
                start_row = row
                end_row = row

        # Emit final range
        self.dataChanged.emit(
            self.index(start_row, 0),
            self.index(end_row, self.columnCount() - 1),
            [
                Qt.ItemDataRole.DisplayRole,
                Qt.ItemDataRole.BackgroundRole,
                Qt.ItemDataRole.TextAlignmentRole,
            ],
        )

        self._dirty_rows.clear()

    def song_updated(self, song: Song):
        for idx, s in enumerate(self.songs):
            if s.path == song.path:
                # Update cache
                self._update_cache(song)
                # Add to dirty rows for coalesced update
                self._dirty_rows.add(idx)
                if not self._update_timer.isActive():
                    self._update_timer.start()
                logger.debug(f"Marked row {idx} as dirty for song: {song.title} ({song.artist})")
                return
        logger.warning(f"Song update received but not found in model: {song.path}")

    def song_deleted(self, song: Song):
        try:
            row_index = self.songs.index(song)
            self.beginRemoveRows(QModelIndex(), row_index, row_index)
            self.songs.pop(row_index)
            self._remove_from_cache(song)
            self.endRemoveRows()
            logger.info(f"Deleted song: {song}")
        except ValueError:
            logger.error(f"Attempted to delete a song not in the list: {song}")

    def songs_cleared(self):
        # End bulk loading if active
        if self._bulk_loading:
            self._bulk_loading = False
            self.bulk_load_ended.emit()

        self.beginResetModel()
        self.songs.clear()
        self._row_cache.clear()
        self.endResetModel()
        self._remap_selection_to_current_instances()

    def rowCount(self, parent=QModelIndex()):
        return len(self.songs)

    def columnCount(self, parent=QModelIndex()):
        return 12

    def _format_column_display(self, song: Song, column: int, cache_entry) -> str:
        """Format display text for a specific column via strategy pattern."""
        return self._column_registry.format_display(song, column, cache_entry)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self.songs)):
            return None

        song: Song = self.songs[index.row()]
        column = index.column()

        if role == Qt.ItemDataRole.UserRole:
            return song
        elif role == Qt.ItemDataRole.DisplayRole:
            cache_entry = self._row_cache.get(song.path)
            return self._format_column_display(song, column, cache_entry)
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            if 3 <= column <= 8 or column == 10:
                return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        elif role == Qt.ItemDataRole.BackgroundRole:
            if song.status == SongStatus.ERROR or song.status == SongStatus.MISSING_AUDIO:
                return QColor(180, 50, 50)  # Dark red for errors and missing audio
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            headers = [
                "Path",
                "Artist",
                "Title",
                "Length",
                "BPM",
                "Gap",
                "Detected",
                "Diff",
                "Notes",
                "Time",
                "Normalized",
                "Status",
            ]
            return headers[section]
        return None

    def _get_sort_key(self, song: Song, column: int):
        """Get sort key for a song based on column via strategy pattern."""
        cache_entry = self._row_cache.get(song.path)
        return self._column_registry.get_sort_key(song, column, cache_entry)

    def sort(self, column, order=Qt.SortOrder.AscendingOrder):
        """Optimized sort using direct attribute access instead of data() calls."""
        self.layoutAboutToBeChanged.emit()

        self.songs.sort(key=lambda song: self._get_sort_key(song, column))
        if order == Qt.SortOrder.DescendingOrder:
            self.songs.reverse()
        self.layoutChanged.emit()

    # Streaming API for chunked async loading
    def load_data_async_start(self, total_count=0):
        """Start async data loading - clears existing data and prepares for streaming."""
        self._is_streaming = True
        self.beginResetModel()
        self.songs.clear()
        self._row_cache.clear()
        self.endResetModel()
        logger.info(f"Started async loading, expecting {total_count} songs")

    def load_data_async_append(self, chunk_songs: List[Song]):
        """Append a chunk of songs during async loading."""
        if not chunk_songs:
            return

        start_row = len(self.songs)
        end_row = start_row + len(chunk_songs) - 1

        self.beginInsertRows(QModelIndex(), start_row, end_row)
        self.songs.extend(chunk_songs)
        # Populate cache for the chunk
        for song in chunk_songs:
            self._add_to_cache(song)
        self.endInsertRows()

        logger.debug(f"Appended {len(chunk_songs)} songs, total now: {len(self.songs)}")

    def load_data_async_complete(self):
        """Complete async data loading."""
        self._is_streaming = False
        logger.info(f"Completed async loading, total songs: {len(self.songs)}")
        self._remap_selection_to_current_instances()

    def _remap_selection_to_current_instances(self):
        """Ensure AppData.selected_songs references current Song instances after batch operations."""
        selected = list(getattr(self.app_data, "selected_songs", []) or [])
        if not selected:
            return

        path_map = {}
        for song in self.songs:
            path = getattr(song, "path", None)
            if path:
                path_map[path] = song

        remapped = []
        changed = False
        for song in selected:
            path = getattr(song, "path", None)
            replacement = path_map.get(path)
            if replacement is None:
                return  # Missing selection in current list; keep existing selection untouched
            remapped.append(replacement)
            if replacement is not song:
                changed = True

        if changed:
            logger.debug("Selection remapped to new instances: %s entries", len(remapped))
            self.app_data.selected_songs = remapped
