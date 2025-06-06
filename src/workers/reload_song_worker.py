import os
import logging
from PySide6.QtCore import Signal
from model.song import Song, SongStatus
from services import song_service
from utils import files
from managers.worker_queue_manager import IWorker, IWorkerSignals
import utils.audio as audio
from services.gap_info_service import GapInfoService

logger = logging.getLogger(__name__)

class WorkerSignals(IWorkerSignals):
    songReloaded = Signal(Song)

class ReloadSongWorker(IWorker):
    """Worker specifically designed for reloading a single song"""
    
    def __init__(self, song_path, directory):
        super().__init__()
        self.signals = WorkerSignals()
        self.song_path = song_path
        self.directory = directory
        self.description = f"Loading song {os.path.basename(song_path)}"
        self.song_service = song_service.SongService() 

    async def load(self) -> Song:
        """Load a song from file, forcing reload."""
        try:
            txt_file = files.find_txt_file(self.song_path)
            song = await self.song_service.load_song(txt_file, True, self.is_cancelled)
            return song
            
        except RuntimeError as e:
            # Specific handling for RuntimeError (failed to load USDX file)
            logger.error(f"RuntimeError reloading song '{self.song_path}': {str(e)}")
            logger.exception(e)
            
            # Create a basic song with error status
            song = Song()
            song.path = self.song_path
            song.txt_file = self.song_path if self.song_path.endswith('.txt') else ""
            song.status = SongStatus.ERROR
            song.error_message = str(e)

            return song

    async def run(self):
        """Execute the worker's task."""
        logger.info(f"Loading song: {self.song_path}")
        
        song = await self.load()
         
        if not self.is_cancelled():
            self.signals.songReloaded.emit(song)
            self.signals.finished.emit()
            logger.debug(f"Finished reloading song: {self.song_path}")
