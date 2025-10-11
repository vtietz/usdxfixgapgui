from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import QSortFilterProxyModel, QTimer
from actions import Actions
from app.app_data import AppData
from model.song import Song
from model.songs import Songs
from ui.songlist.songlist_view import SongListView
from ui.songlist.songlist_model import SongTableModel
from typing import List
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
        song: Song = self.sourceModel().songs[source_row]

        # Implement filtering logic
        statusMatch = song.status.name in self.selectedStatuses if self.selectedStatuses else True
        
        # Use cached lowercase strings from model if available
        source_model = self.sourceModel()
        if hasattr(source_model, '_row_cache') and song.path in source_model._row_cache:
            cache_entry = source_model._row_cache[song.path]
            textMatch = (self.textFilter in cache_entry['artist_lower'] or 
                        self.textFilter in cache_entry['title_lower'])
        else:
            # Fallback to direct lowercase conversion
            textMatch = self.textFilter in song.artist.lower() or self.textFilter in song.title.lower()

        return statusMatch and textMatch

class SongListWidget(QWidget):
    def __init__(self, songs_model: Songs, actions: Actions, data: AppData,parent=None):
        super().__init__(parent)
        self.actions = actions

        # Create the table model and proxy model
        self.songs_model = songs_model
        self.tableModel = SongTableModel(songs_model, data)
        self.proxyModel = CustomSortFilterProxyModel()
        self.proxyModel.setSourceModel(self.tableModel)

        self.tableView = SongListView(self.proxyModel, actions)
        
        # Create song count label
        self.countLabel = QLabel()

        layout = QVBoxLayout()
        layout.addWidget(self.tableView)
        layout.addWidget(self.countLabel)
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
        
        # Streaming state
        self._streaming_songs: List[Song] = []
        self._streaming_index = 0
        self._streaming_timer = QTimer()
        self._streaming_timer.timeout.connect(self._append_next_chunk)
        
        # Initial update of the count label
        self.updateCountLabel()

    def updateFilter(self):
        self.proxyModel.selectedStatuses = self.songs_model.filter
        self.proxyModel.textFilter = self.songs_model.filter_text.lower()
        self.proxyModel.invalidateFilter()
        self.updateCountLabel()
        
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
        
        # Clear streaming state
        self._streaming_songs = []
        self._streaming_index = 0

