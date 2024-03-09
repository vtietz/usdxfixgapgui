import os
from PyQt6.QtCore import QObject, QThreadPool
from data import AppData
from utils import files
from workers.extract_vocals import ExtractVocalsWorker
from workers.loading_songs import LoadSongsWorker

class Actions(QObject):

    data: AppData = None
    
    def __init__(self, data: AppData):
        super().__init__()
        self.data = data
        self.workerQueue = data.workerQueue
    
    def loadSongs(self):
        if self.data.isLoadingSongs: 
            print("Already loading songs")
            return
        self.data.isLoadingSongs = True
        self.clearSongs()
        worker = LoadSongsWorker(self.data.directory)
        worker.signals.songLoaded.connect(self.data.songs.add)
        worker.signals.finished.connect(lambda: self.finishLoadingSongs())
        worker.signals.finished.connect(lambda: self.finishLoadingSongs())
        self.workerQueue.addTask(worker)
    
    def cancelLoadingSongs(self):
        print("Cancelling loading songs")
        if self.currentWorker:
            self.currentWorker.cancel()
            self.finishLoadingSongs()

    def finishLoadingSongs(self):
        self.data.isLoadingSongs = False

    def clearSongs(self):
        self.data.songs.clear()

    def setSelectedSong(self, path: str):
        print(f"Selected song to {path}")
        song = next((s for s in self.data.songs if s.path == path), None)
        self.data.selectedSong = song

    def loadingSongsFinished(self):
        self.data.isLoadingSongs = False
        print("Loading songs finished.")

    def extractVocals(self):
        selectedSong = self.data.selectedSong
        if not selectedSong:
            print("No song selected")
            return
        audio_file = selectedSong.audio_file
        destination_path = files.get_temp_path(selectedSong.txt_file)
        print(f"Extracting vocals from {audio_file} to {destination_path}")
        worker = ExtractVocalsWorker(audio_file, destination_path, 30)
        #worker.signals.finished.connect(self.vocalsExtracted)
        self.workerQueue.addTask(worker)