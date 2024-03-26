import os
from concurrent.futures import ThreadPoolExecutor, as_completed
import traceback
from PyQt6.QtCore import pyqtSignal
from utils.worker_queue_manager import IWorker, IWorkerSignals
from model.song import Song
import logging

logger = logging.getLogger(__name__)

class WorkerSignals(IWorkerSignals):
    songLoaded = pyqtSignal(Song)  

class LoadSongsWorker(IWorker):
    def __init__(self, directory, tmp_path, max_workers=4):
        super().__init__()
        self.directory = directory
        self.tmp_path = tmp_path
        self.max_workers = max_workers
        self.description = f"Loading songs from {directory}."
        self.signals = WorkerSignals()
        self.path_usdb_id_map = {}

    def load_song(self, txt_file_path):
        if self.is_canceled():
            return
        try:
            song = Song(txt_file_path, self.tmp_path)
            song.load()
            song.relative_path = os.path.relpath(song.path, self.directory)
            song.usdb_id = self.path_usdb_id_map.get(song.path, None)
            self.signals.songLoaded.emit(song)
        except Exception as e:
            stack_trace = traceback.format_exc()
            logger.error(f"Error creating waveform: {e}\nStack trace:\n{stack_trace}")           
            self.signals.error.emit((e,))

    def run(self):
        print(f"Starting to load songs from {self.directory}")
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = []

            for root, dirs, files in os.walk(self.directory):
                if self.is_canceled():
                    print("Loading cancelled.")
                    self.signals.canceled.emit()
                    break

                for file in files:
                    if file.endswith(".usdb"):
                        usdb_id = os.path.splitext(file)[0]
                        self.path_usdb_id_map[root] = int(usdb_id)
                    elif file.endswith(".txt"):  # Use elif to ensure the file is not processed twice
                        song_path = os.path.join(root, file)
                        self.description = f"Reading {file}"
                        self.signals.progress.emit()

                        # Submit the task for this song immediately
                        future = executor.submit(self.load_song, song_path)
                        futures.append(future)

            # As each future completes, check for cancellation
            # Note: This loop can also be moved outside the os.walk loop if you want
            # to ensure all paths are submitted before waiting for any to complete.
            for future in as_completed(futures):
                if self.is_canceled():
                    print("Loading cancelled.")
                    self.signals.canceled.emit()
                    # Optionally: Cancel all running or waiting futures
                    for future in futures:
                        future.cancel()
                    break

        if not self.is_canceled():
            self.signals.finished.emit()
            print("Finished loading songs.")


