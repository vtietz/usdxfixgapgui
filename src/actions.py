import logging
import os
from PyQt6.QtCore import QObject
from data import AppData, Config
from model.song import Song
from utils import files
from workers.detect_gap import DetectGapWorker
from workers.extract_vocals import ExtractVocalsWorker
from workers.loading_songs import LoadSongsWorker
from workers.create_waveform import CreateWaveform
from model.song import Song, SongStatus
import utils.files as files
import utils.audio as audio

logger = logging.getLogger(__name__)

class Actions(QObject):

    data: AppData = None
    
    def __init__(self, data: AppData, config: Config):
        super().__init__()
        self.data = data
        self.config = config
        self.workerQueue = data.workerQueue
    
    def loadSongs(self):
        if self.data.isLoadingSongs: 
            print("Already loading songs")
            return
        self.data.isLoadingSongs = True
        self.clearSongs()
        worker = LoadSongsWorker(self.config.directory)
        worker.signals.songLoaded.connect(self.data.songs.add)
        worker.signals.finished.connect(lambda: self.finishLoadingSongs())
        self.workerQueue.addTask(worker)
    
    def finishLoadingSongs(self):
        self.data.isLoadingSongs = False

    def clearSongs(self):
        self.data.songs.clear()

    def setSelectedSong(self, path: str):
        print(f"Selected {path}")
        song = next((s for s in self.data.songs if s.path == path), None)
        self.data.selectedSong = song
        self._create_waveforms(song)

    def loadingSongsFinished(self):
        self.data.isLoadingSongs = False
        print("Loading songs finished.")

    def extractVocals(self):
        selectedSong: Song = self.data.selectedSong
        if not selectedSong:
            print("No song selected")
            return
        audio_file = selectedSong.audio_file
        destination_path = files.get_temp_path(selectedSong.audio_file)
        print(f"Extracting vocals from {audio_file} to {destination_path}")
        selectedSong.status = SongStatus.QUEUED
        worker = ExtractVocalsWorker(audio_file, destination_path, self.config.default_detection_time)
        #worker.signals.finished.connect(self.vocalsExtracted)
        self.workerQueue.addTask(worker)

    def detect_gap(self):
        selectedSong: Song = self.data.selectedSong
        if not selectedSong:
            print("No song selected")
            return
        worker = DetectGapWorker(selectedSong, self.config)
        worker.signals.started.connect(lambda: self.on_song_worker_started(selectedSong))
        worker.signals.error.connect(lambda: self.on_song_worker_error(selectedSong))
        worker.signals.finished.connect(lambda: selectedSong.info.save())
        worker.signals.finished.connect(lambda: self.on_detect_gap_finished(selectedSong))
        selectedSong.info.status = SongStatus.QUEUED
        self.data.songs.updated.emit(selectedSong)
        self.workerQueue.addTask(worker)

    def on_song_worker_started(self, song: Song):
        song.info.status = SongStatus.PROCESSING
        self.data.songs.updated.emit(song)

    def on_song_worker_error(self, song: Song):
        song.info.status = SongStatus.ERROR
        self.data.songs.updated.emit(song)

    def on_detect_gap_finished(self, song: Song):
        song.info.save()
        self._create_waveforms(song, True)
        self.data.songs.updated.emit(song)

    def _create_waveforms(self, song: Song, overwrite: bool = False):
        if not song:
            raise Exception("No song given")
        
        if overwrite or (os.path.exists(song.audio_file) and not os.path.exists(song.audio_waveform_file)):
            self._create_waveform(song, song.audio_file, song.audio_waveform_file)

        if overwrite or (os.path.exists(song.vocals_file) and not os.path.exists(song.vocals_waveform_file)):
            self._create_waveform(song, song.vocals_file, song.vocals_waveform_file)
        

    def _create_waveform(self, song: Song, audio_file: str, waveform_file: str):
        
        audio_file = song.audio_file
        bpm = song.bpm
        notes = song.notes
        gap = song.gap
        detected_gap = song.info.detected_gap
        song_title = song.title
        duration_ms = audio.get_audio_duration(audio_file)
        is_relative = song.is_relative
        
        logger.debug(f"Scheduling waveform creation for '{audio_file}'")
        
        worker = CreateWaveform(audio_file, duration_ms, waveform_file, song_title, notes, bpm, gap, detected_gap, is_relative)
        worker.signals.finished.connect(lambda: self.data.songs.updated(song))
        #worker.signals.error.connect(lambda: self.on_song_worker_error(song))
        self.workerQueue.addTask(worker)    