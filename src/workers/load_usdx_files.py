import os
from PyQt6.QtCore import pyqtSignal
from model.gap_info import GapInfo, GapInfoStatus
from model.song import Song
from utils.usdx_file import USDXFile
from utils.worker_queue_manager import IWorker, IWorkerSignals
from utils.run_async import run_async
import utils.files as files
import utils.audio as audio
import traceback
import logging

logger = logging.getLogger(__name__)

class WorkerSignals(IWorkerSignals):
    songLoaded = pyqtSignal(Song)  

class FindUsdxFilesWorker(IWorker):
    def __init__(self, directory, tmp_root):
        super().__init__()
        self.directory = directory
        self.tmp_root = tmp_root
        self.description = f"Searching song files in {directory}."
        self.signals = WorkerSignals()
        self.path_usdb_id_map = {}


    async def load(self, txt_file_path) -> Song:
        if self.is_canceled():
            return
        try:
            usdx_file = USDXFile(txt_file_path)
            await usdx_file.load()

            gap_file = GapInfo(usdx_file.path)
            await gap_file.load()

            song = Song(usdx_file, gap_file, self.tmp_root)
            return song
            
        except Exception as e:
            stack_trace = traceback.format_exc()
            logger.error(f"Error loading song '{txt_file_path}': {e}\nStack trace:\n{stack_trace}")           
            self.signals.error.emit((e,))

    def on_song_loaded(self, song: Song):
        song.relative_path = os.path.relpath(song.path, self.directory)
        song.usdb_id = self.path_usdb_id_map.get(song.path, None)
        song.duration_ms = audio.get_audio_duration(song.audio_file)
        self.signals.songLoaded.emit(song)
    
    def run(self):
        logger.debug(self.description)

        for root, dirs, files in os.walk(self.directory):
            if self.is_canceled():
                logger.debug("Loading cancelled.")
                self.signals.canceled.emit()
                break

            for file in files:
                if self.is_canceled():
                    logger.debug("Loading cancelled.")
                    self.signals.canceled.emit()
                    break

                if file.endswith(".usdb"):
                    usdb_id = os.path.splitext(file)[0]
                    self.path_usdb_id_map[root] = int(usdb_id)
                if file.endswith(".txt"):
                    song_path = os.path.join(root, file)
                    self.description = f"Found file {file}"
                    run_async(self.load(song_path), lambda song: self.on_song_loaded(song) if song is not None else None)
                    #run_async(self.load(song_path), lambda song: self.on_song_loaded(song))
                    self.signals.progress.emit()
                    #self.signals.fileFound.emit(usdx_file)

        if not self.is_canceled():
            self.signals.finished.emit()
            logger.debug("Finished loading songs.")
