import os
import pickle
import datetime
from PySide6.QtCore import Signal as pyqtSignal
from model.gap_info import GapInfo, GapInfoStatus
from model.song import Song, SongStatus
from model.song_cached import SongCached
from utils.usdx_file import USDXFile
from workers.worker_queue_manager import IWorker, IWorkerSignals
import utils.audio as audio
from utils.run_async import run_sync
from common.database import get_all_cache_entries, cleanup_stale_entries
import logging

logger = logging.getLogger(__name__)

class WorkerSignals(IWorkerSignals):
    songLoaded = pyqtSignal(Song)
    cacheCleanup = pyqtSignal(int)  # Signal to report stale cache entries cleaned up

class LoadUsdxFilesWorker(IWorker):
    def __init__(self, directory, tmp_root):
        super().__init__()
        self.signals = WorkerSignals()
        self.directory = directory
        self.tmp_root = tmp_root
        self.description = f"Loading songs from cache and searching in {directory}."
        self.path_usdb_id_map = {}
        self.loaded_paths = set()  # Track files we've loaded to detect stale cache entries

    async def load(self, txt_file_path, force_reload=False) -> Song:
        """Load a song from file, optionally forcing reload."""
        self.description = f"Loading file {txt_file_path}"
        song = SongCached(txt_file_path, self.directory, self.tmp_root)
        try:
            await song.load(force_reload=force_reload)
            song.usdb_id = self.path_usdb_id_map.get(song.path, None)
            if not song.duration_ms:
                song.duration_ms = audio.get_audio_duration(song.audio_file, self.is_cancelled())
        except Exception as e:
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
                if self.is_cancelled(): 
                    return
                
                if file.endswith(".usdb"):
                    usdb_id = os.path.splitext(file)[0]
                    self.path_usdb_id_map[root] = usdb_id
                
                if file.endswith(".txt"):
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
        
        # First load from cache for immediate UI feedback
        await self.load_from_cache()
        
        # Then scan directory for changes and new files
        await self.scan_directory()
        
        # Finally clean up stale cache entries
        await self.cleanup_cache()

        if not self.is_cancelled():
            self.signals.finished.emit()
            logger.debug("Finished loading songs.")
