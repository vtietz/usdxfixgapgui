import os
import traceback
from PyQt6.QtCore import pyqtSignal
from utils.run_async import run_async
from utils.worker_queue_manager import IWorker, IWorkerSignals
from model.song import Song
import logging

logger = logging.getLogger(__name__)

class WorkerSignals(IWorkerSignals):
    songLoaded = pyqtSignal(Song)  

class LoadSongsWorker(IWorker):
    def __init__(self, directory, tmp_path):
        super().__init__()
        self.directory = directory
        self.tmp_path = tmp_path
        self.description = f"Loading songs from {directory}."
        self.signals = WorkerSignals()
        self.path_usdb_id_map = {}

    def load_song(self, txt_file_path):
        if self.is_canceled():
            return
        try:
            song = Song(txt_file_path, self.tmp_path)
            # Note: No need to pass 'song' as an argument to the callback; use it directly in the lambda
            run_async(song.load(), lambda _: self.on_song_loaded(song))
        except Exception as e:
            stack_trace = traceback.format_exc()
            logger.error(f"Error loading song: {e}\nStack trace:\n{stack_trace}")           
            self.signals.error.emit((e,))

    def on_song_loaded(self, song: Song):
        song.relative_path = os.path.relpath(song.path, self.directory)
        song.usdb_id = self.path_usdb_id_map.get(song.path, None)
        self.signals.songLoaded.emit(song)

    def run(self):
        logger.debug(f"Starting to load songs from {self.directory}")

        for root, dirs, files in os.walk(self.directory):
            if self.is_canceled():
                logger.debug("Loading cancelled.")
                self.signals.canceled.emit()
                break

            for file in files:
                if self.is_canceled():
                    logger.debug("Loading cancelled.")
                    self.signals.canceled.emit()
                    break  # Early exit if operation was cancelled

                if file.endswith(".usdb"):
                    usdb_id = os.path.splitext(file)[0]
                    self.path_usdb_id_map[root] = int(usdb_id)
                elif file.endswith(".txt"):
                    song_path = os.path.join(root, file)
                    self.description = f"Reading {file}"
                    self.signals.progress.emit()

                    self.load_song(song_path)  # Load each song sequentially

        if not self.is_canceled():
            self.signals.finished.emit()
            logger.debug("Finished loading songs.")
