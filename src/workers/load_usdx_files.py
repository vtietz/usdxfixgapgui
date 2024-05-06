import os
from PyQt6.QtCore import pyqtSignal
from model.gap_info import GapInfo, GapInfoStatus
from model.song import Song, SongStatus
from utils.usdx_file import USDXFile
from workers.worker_queue_manager import IWorker, IWorkerSignals
import utils.audio as audio
from utils.run_async import run_sync
import logging

logger = logging.getLogger(__name__)

class WorkerSignals(IWorkerSignals):
    songLoaded = pyqtSignal(Song)  

class LoadUsdxFilesWorker(IWorker):
    def __init__(self, directory, tmp_root):
        super().__init__()
        self.signals = WorkerSignals()
        self.directory = directory
        self.tmp_root = tmp_root
        self.description = f"Searching song files in {directory}."
        self.path_usdb_id_map = {}


    async def load(self, txt_file_path) -> Song:
        self.description = f"Loading file {txt_file_path}"
        song = Song(txt_file_path, self.directory, self.tmp_root)
        try:
            await song.load()
            song.usdb_id = self.path_usdb_id_map.get(song.path, None)
            if(not song.duration_ms):
                song.duration_ms = audio.get_audio_duration(song.audio_file, self.is_cancelled())
        except Exception as e:
            song.status = SongStatus.ERROR
            logger.error(f"Error loading song '{txt_file_path}")
        return song
        #self.signals.error.emit(e)

    async def run(self):
        logger.debug(self.description)
        for root, dirs, files in os.walk(self.directory):
            self.description = f"Searching song files in {root}"
            if self.is_cancelled(): 
                return

            for file in files:
                if self.is_cancelled(): 
                    return
                if file.endswith(".usdb"):
                    usdb_id = os.path.splitext(file)[0]
                    self.path_usdb_id_map[root] = int(usdb_id)
                if file.endswith(".txt"):
                    song_path = os.path.join(root, file)
                    song = await self.load(song_path)
                    if song:
                        self.signals.songLoaded.emit(song)
                self.signals.progress.emit()
            self.signals.progress.emit()

        if not self.is_cancelled():
            self.signals.finished.emit()
            logger.debug("Finished loading songs.")
