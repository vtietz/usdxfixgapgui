import os
import logging
from PySide6.QtCore import Signal
from model.song import Song, SongStatus
from services.song_service import SongService
from managers.worker_queue_manager import IWorker, IWorkerSignals
import utils.audio as audio
from common.database import get_all_cache_entries, cleanup_stale_entries

logger = logging.getLogger(__name__)

class WorkerSignals(IWorkerSignals):
    songLoaded = Signal(Song) 
    cacheCleanup = Signal(int)  # Signal to report stale cache entries cleaned up

class LoadUsdxFilesWorker(IWorker):
    def __init__(self, directory, tmp_root):
        super().__init__()
        self.signals = WorkerSignals()
        self.directory = directory
        self.tmp_root = tmp_root
        self.description = f"Loading songs from cache and searching in {directory}."
        self.path_usdb_id_map = {}
        self.loaded_paths = set()  # Track files we've loaded to detect stale cache entries
        self.reload_single_file = None  # Path to single file to reload (when used for reload)
        self.song_service = SongService()  # Create song service

    async def load(self, txt_file_path, force_reload=False) -> Song:
        """Load a song from file, optionally forcing reload."""
        self.description = f"Loading file {txt_file_path}"
        
        # Check for cancellation before loading
        if self.is_cancelled():
            return None
            
        try:
            # Use the service to load the song
            song = await self.song_service.load_song(txt_file_path, self.directory, force_reload)
            song.usdb_id = self.path_usdb_id_map.get(song.path, None)
            return song
            
        except Exception as e:
            # Create minimal song data for error reporting
            song = Song(txt_file_path)
            song.status = SongStatus.ERROR
            song.error_message = str(e)
            logger.error(f"Error loading song '{txt_file_path}")
            logger.exception(e)
            return song

    async def load_from_cache(self):
        """Load all songs from the cache database first."""
        self.description = f"Loading songs from cache."
        logger.info("Loading songs from cache")
        
        deserialized_songs = get_all_cache_entries(deserialize=True)
        logger.info(f"Found {len(deserialized_songs)} cached songs")
        
        for file_path, song in deserialized_songs.items():
            if self.is_cancelled():
                return
            
            # Ensure path exists and song is valid
            if not hasattr(song, 'path') or not os.path.exists(file_path):
                continue
                
            # Update USDB ID if needed
            song.usdb_id = self.path_usdb_id_map.get(song.path, song.usdb_id)
            
            # Emit the loaded song
            self.signals.songLoaded.emit(song)
            self.loaded_paths.add(file_path)
            self.signals.progress.emit()

    async def scan_directory(self):
        """Scan directory for new or changed songs."""
        self.description = f"Scanning for new or changed songs in {self.directory}"
        logger.info(f"Scanning directory {self.directory} for new or changed songs")
        
        for root, dirs, files in os.walk(self.directory):
            self.description = f"Searching song files in {root}"
            if self.is_cancelled(): 
                return

            for file in files:
                # Check for cancellation on every file
                if self.is_cancelled(): 
                    return
                
                if file.endswith(".usdb"):
                    usdb_id = os.path.splitext(file)[0]
                    self.path_usdb_id_map[root] = usdb_id
                
                if file.endswith(".txt"):
                    # Check for cancellation again before heavy operation
                    if self.is_cancelled():
                        return
                        
                    song_path = os.path.join(root, file)
                    
                    # If already loaded from cache, skip
                    if song_path in self.loaded_paths:
                        continue
                    
                    song = await self.load(song_path)
                    if song:
                        self.signals.songLoaded.emit(song)
                        self.loaded_paths.add(song_path)
                        
                self.signals.progress.emit()
            
            self.signals.progress.emit()

    async def cleanup_cache(self):
        """Clean up stale cache entries."""
        self.description = "Cleaning up stale cache entries"
        logger.info("Cleaning up stale cache entries")
        
        stale_entries_removed = cleanup_stale_entries(self.loaded_paths)
        self.signals.cacheCleanup.emit(stale_entries_removed)

    async def run(self):
        logger.debug(self.description)
        
        # If this is a single file reload operation
        if self.reload_single_file:
            self.description = f"Reloading song {self.reload_single_file}"
            logger.info(f"Reloading song: {self.reload_single_file}")
            
            song = await self.load(self.reload_single_file, force_reload=True)
            if song:
                self.signals.songLoaded.emit(song)
                self.loaded_paths.add(song.txt_file)  # Changed from song.path to song.txt_file
            
            self.signals.finished.emit()
            return
            
        # Regular operation - loading all songs
        # First load from cache for immediate UI feedback
        await self.load_from_cache()
        
        # Then scan directory for changes and new files
        await self.scan_directory()
        
        # Finally clean up stale cache entries
        await self.cleanup_cache()

        if not self.is_cancelled():
            self.signals.finished.emit()
            logger.debug("Finished loading songs.")
