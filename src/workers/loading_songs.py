import os
from time import sleep
from PyQt6.QtCore import QObject, pyqtSignal, QRunnable
from utils.worker_queue_manager import IWorkerSignals

from model.song import Song
from utils import files as filesutil

class WorkerSignals(IWorkerSignals):
    songLoaded = pyqtSignal(Song)  

class LoadSongsWorker(QRunnable):

    def __init__(self, directory):
        super().__init__()
        self.directory = directory
        self.description = f"Loading songs from {directory}."
        self.signals = WorkerSignals()
        self._isCancelled = False

    def loadSong(self, txt_file_path):
        song = Song(txt_file_path)
        song.load()
        self.signals.songLoaded.emit(song)

    def run(self):
        print(f"Loading songs from {self.directory}")
        for root, dirs, files in os.walk(self.directory):
            if self._isCancelled:  # Check cancellation flag
                print("Loading cancelled.")
                return  # Exit the loop and end the worker prematurely
            for file in files:
                if file.endswith(".txt"):  # Adjust the condition based on your needs
                    self.loadSong(os.path.join(root, file))
        self.signals.finished.emit()  # Emit finished signal after all songs are processed
        print(f"Finshed.")

    def cancel(self):
        self._isCancelled = True
