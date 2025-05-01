import logging
from PySide6.QtCore import QObject
from common.data import AppData
from common.song_manager import SongManager
from common.gap_processor import GapProcessor
from common.audio_processor import AudioProcessor
from common.external_interactions import ExternalInteractions
from workers.worker_queue_manager import WorkerQueueManager

logger = logging.getLogger(__name__)

class Actions(QObject):
    """Coordinates between different managers to provide a unified API for UI interactions"""
    
    def __init__(self, data: AppData):
        super().__init__()
        self.data = data
        self.config = data.config
        
        # Create worker queue manager
        self.worker_queue = WorkerQueueManager()
        
        # Create managers
        self.song_manager = SongManager(data, self.worker_queue)
        self.gap_processor = GapProcessor(data, self.worker_queue)
        self.audio_processor = AudioProcessor(data, self.worker_queue)
        self.external_interactions = ExternalInteractions(data)
        
        # Setup event connections between managers
        self._setup_connections()
    
    def _setup_connections(self):
        """Setup connections between different managers"""
        # Connect gap detection finished to waveform creation
        if hasattr(self.data, 'gap_detection_finished'):
            self.data.gap_detection_finished.connect(
                lambda song: self.audio_processor.create_waveforms(song, True)
            )
            
            # If auto-normalize is enabled, connect to normalization
            if self.config.auto_normalize:
                self.data.gap_detection_finished.connect(
                    lambda song: self.audio_processor._normalize_song(song) if song.audio_file else None
                )
        
        # Connect gap updated/reverted to waveform creation
        if hasattr(self.data, 'gap_updated'):
            self.data.gap_updated.connect(
                lambda song: self.audio_processor.create_waveforms(song, True)
            )
        
        if hasattr(self.data, 'gap_reverted'):
            self.data.gap_reverted.connect(
                lambda song: self.audio_processor.create_waveforms(song, True)
            )

    # Delegate methods to appropriate managers
    # Song management
    def auto_load_last_directory(self):
        return self.song_manager.auto_load_last_directory()

    def set_directory(self, directory):
        self.song_manager.set_directory(directory)

    def set_selected_songs(self, songs):
        self.song_manager.set_selected_songs(songs)

    def reload_song(self):
        self.song_manager.reload_song()

    def delete_selected_song(self):
        self.song_manager.delete_selected_song()

    # Gap processing
    def detect_gap(self, overwrite=False):
        self.gap_processor.detect_gap_for_songs(overwrite)

    def get_notes_overlap(self, song, silence_periods, detection_time):
        self.gap_processor.get_notes_overlap(song, silence_periods, detection_time)

    def update_gap_value(self, song, gap):
        self.gap_processor.update_gap_value(song, gap)

    def revert_gap_value(self, song):
        self.gap_processor.revert_gap_value(song)

    def keep_gap_value(self, song):
        self.gap_processor.keep_gap_value(song)

    # Audio processing
    def normalize_song(self):
        self.audio_processor.normalize_songs()

    # External interactions
    def open_usdx(self):
        self.external_interactions.open_usdx()

    def open_folder(self):
        self.external_interactions.open_folder()

    # Legacy method to maintain compatibility with old code
    def select_song(self, path: str):
        logger.warning("select_song(path) called, consider using set_selected_songs(list[Song])")
        song = next((s for s in self.data.songs if s.path == path), None)
        if song:
            self.set_selected_songs([song])  # Wrap in list
        else:
            self.set_selected_songs([])
