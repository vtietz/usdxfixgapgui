import os
from PyQt6.QtCore import pyqtSignal
from model.gap_info import GapInfo
from model.song import Song
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
        self.directory = directory
        self.tmp_root = tmp_root
        self.description = f"Searching song files in {directory}."
        self.signals = WorkerSignals()
        self.path_usdb_id_map = {}


    async def load(self, txt_file_path) -> Song:
        try:
            usdx_file = USDXFile(txt_file_path)
            await usdx_file.load()

            gap_file = GapInfo(usdx_file.path)
            await gap_file.load()

            song = Song(usdx_file, gap_file, self.tmp_root)
            song.relative_path = os.path.relpath(song.path, self.directory)
            song.usdb_id = self.path_usdb_id_map.get(song.path, None)

            if(not song.duration_ms):
                song.duration_ms = audio.get_audio_duration(song.audio_file)
            return song
        
        except Exception as e:
            logger.error(f"Error loading song '{txt_file_path}")           
            self.signals.error.emit(e)


    async def run(self):
        logger.debug(self.description)

        for root, dirs, files in os.walk(self.directory):

            if self.is_cancelled():
                logger.debug("Loading cancelled.")
                self.signals.canceled.emit()
                break

            for file in files:

                if self.is_cancelled():
                    logger.debug("Loading cancelled.")
                    self.signals.canceled.emit()
                    break

                if file.endswith(".usdb"):
                    usdb_id = os.path.splitext(file)[0]
                    self.path_usdb_id_map[root] = int(usdb_id)
                if file.endswith(".txt"):
                    song_path = os.path.join(root, file)
                    self.description = f"Loading file {file}"
                    song = await self.load(song_path)
                    if song:
                        self.signals.songLoaded.emit(song)
                self.signals.progress.emit()

        if not self.is_cancelled():
            self.signals.finished.emit()
            logger.debug("Finished loading songs.")
