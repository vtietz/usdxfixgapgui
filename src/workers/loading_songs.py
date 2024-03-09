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
        self.task_description = f"Loading songs from {directory}."
        self.signals = WorkerSignals()
        self._isCancelled = False

    def loadSong(self, txt_file_path):
        song_path = filesutil.get_song_path(txt_file_path)
        tmp_path = filesutil.get_temp_path(txt_file_path)
        tags = filesutil.extract_tags(txt_file_path)
        if not tags:
            return
        song = Song(song_path)
        song.fromTags(tags)
        info_file=filesutil.get_info_file_path(song_path)
        if info_file:
            info=filesutil.read_info_data(info_file)
            song.fromInfo(info)
        song.audio_file=os.path.join(song_path, song.audio)
        song.vocal_file=filesutil.get_vocals_path(tmp_path)
        song.waveform_file=filesutil.get_waveform_path(tmp_path)
        song.txt_file=txt_file_path
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
