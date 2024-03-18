import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from PyQt6.QtCore import pyqtSignal
from utils.worker_queue_manager import IWorker, IWorkerSignals
from model.song import Song

class WorkerSignals(IWorkerSignals):
    songLoaded = pyqtSignal(Song)  

class LoadSongsWorker(IWorker):
    def __init__(self, directory, max_workers=4):
        super().__init__()
        self.directory = directory
        self.max_workers = max_workers
        self.description = f"Loading songs from {directory}."
        self.signals = WorkerSignals()

    def load_song(self, txt_file_path):
        if self.is_canceled():
            return
        try:
            song = Song(txt_file_path)
            song.load()
            self.signals.songLoaded.emit(song)
        except Exception as e:
            self.signals.error.emit((str(e),))

    def run(self):
        print(f"Starting to load songs from {self.directory}")
        song_paths = []
        for root, dirs, files in os.walk(self.directory):
            if self.is_canceled():
                print("Loading cancelled.")
                self.signals.canceled.emit()
                break
            for file in files:
                if file.endswith(".txt"):
                    self.description = f"Reading {file}"
                    self.signals.progress.emit()
                    song_paths.append(os.path.join(root, file))
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [executor.submit(self.load_song, path) for path in song_paths]
            for future in as_completed(futures):
                if self.is_canceled():
                    print("Loading cancelled.")
                    self.signals.canceled.emit()
                    break
        if not self.is_canceled():
            self.signals.finished.emit()
            print("Finished loading songs.")

