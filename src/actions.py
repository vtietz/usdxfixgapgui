import logging
import os
from PyQt6.QtCore import QObject, QUrl
from PyQt6.QtGui import QDesktopServices
from data import AppData, Config
from model.song import Song
from utils import files
from utils.worker_queue_manager import WorkerQueueManager
from workers.detect_gap import DetectGapWorker
from workers.extract_vocals import ExtractVocalsWorker
from workers.loading_songs import LoadSongsWorker
from workers.create_waveform import CreateWaveform
from model.song import Song
from model.info import SongStatus
import utils.files as files
import utils.audio as audio
import utils.usdx as usdx



logger = logging.getLogger(__name__)

class Actions(QObject):

    data: AppData = None
    
    def __init__(self, data: AppData, config: Config):
        super().__init__()
        self.data = data
        self.config = config
        self.worker_queue = WorkerQueueManager()
    
    def loadSongs(self, directory: str):
        self.config.directory = directory
        self.data.tmp_folder = os.path.join(
            self.config.tmp_root, 
            files.generate_directory_hash(directory)
        )
        if self.data.is_loading_songs: 
            print("Already loading songs")
            return
        self.data.is_loading_songs = True
        self.clearSongs()
        worker = LoadSongsWorker(self.config.directory, self.data.tmp_folder)
        worker.signals.songLoaded.connect(self.data.songs.add)
        worker.signals.songLoaded.connect(self.on_song_loaded)
        worker.signals.finished.connect(lambda: self.finishLoadingSongs())
        self.worker_queue.add_task(worker)
    
    def finishLoadingSongs(self):
        self.data.is_loading_songs = False

    def clearSongs(self):
        self.data.songs.clear()

    def setSelectedSong(self, path: str):
        logger.debug(f"Selected {path}")
        song: Song = next((s for s in self.data.songs if s.path == path), None)
        if(song):
            song.load_notes()
            self.data.selected_song = song
            self._create_waveforms(song)

    def loadingSongsFinished(self):
        self.data.is_loading_songs = False
        print("Loading songs finished.")

    def extractVocals(self):
        selectedSong: Song = self.data.selected_song
        if not selectedSong:
            print("No song selected")
            return
        audio_file = selectedSong.audio_file
        destination_path = files.get_temp_path(self.data.tmp_folder, selectedSong.audio_file)
        print(f"Extracting vocals from {audio_file} to {destination_path}")
        selectedSong.status = SongStatus.QUEUED
        worker = ExtractVocalsWorker(audio_file, destination_path, self.config.default_detection_time)
        self.worker_queue.add_task(worker)

    def detect_gap(self, song: Song = None, start_now=False):
        if not song:
            song: Song = self.data.selected_song
        if not song:
            raise Exception("No song given")

        audio_file = song.audio_file
        bpm = song.bpm
        gap = song.gap + (song.start * 1000)
        default_detection_time = self.config.default_detection_time

        worker = DetectGapWorker(
            audio_file, 
            self.data.tmp_folder,
            bpm, 
            gap, 
            default_detection_time, 
            False)
        
        worker.signals.started.connect(lambda: self.on_song_worker_started(song))
        worker.signals.error.connect(lambda: self.on_song_worker_error(song))
        worker.signals.finished.connect(
            lambda detected_gap: self.on_detect_gap_finished(song, detected_gap)
        )
        song.info.status = SongStatus.QUEUED
        self.data.songs.updated.emit(song)
        self.worker_queue.add_task(worker, start_now)

    def on_song_loaded(self, song: Song):
        if(song.info.status == SongStatus.NOT_PROCESSED):
            self.detect_gap(song)
    
    def on_detect_gap_finished(self, song: Song, detected_gap: int):
        gap = song.gap
        if(not song.notes):
            song.load_notes()
        firstNoteOffset = usdx.get_gap_offset_according_firts_note(song.bpm, song.notes)
        detected_gap = detected_gap - firstNoteOffset
        if(song.start):
            detected_gap = detected_gap - song.start
        gap_diff = abs(gap - detected_gap)
        if gap_diff > self.config.gap_tolerance:
            song.info.status = SongStatus.MISMATCH
        else:
            song.info.status = SongStatus.MATCH
        song.info.detected_gap = detected_gap
        song.info.diff = gap_diff
        song.info.save()
        self._create_waveforms(song, True)

    def on_song_worker_started(self, song: Song):
        song.info.status = SongStatus.PROCESSING
        self.data.songs.updated.emit(song)

    def on_song_worker_error(self, song: Song):
        song.info.status = SongStatus.ERROR
        self.data.songs.updated.emit(song)

    def _create_waveforms(self, song: Song, overwrite: bool = False):
        if not song:
            raise Exception("No song given")
        if overwrite or (os.path.exists(song.audio_file) and not os.path.exists(song.audio_waveform_file)):
            self._create_waveform(song, song.audio_file, song.audio_waveform_file)
        if overwrite or (os.path.exists(song.vocals_file) and not os.path.exists(song.vocals_waveform_file)):
            self._create_waveform(song, song.vocals_file, song.vocals_waveform_file)

    def _create_waveform(self, song: Song, audio_file: str, waveform_file: str):
        
        logger.debug(f"Creating waveform creation task for '{audio_file}'")

        bpm = song.bpm
        notes = song.notes
        gap = song.gap
        detected_gap = song.info.detected_gap
        song_title = f"{song.artist} - {song.title}"
        duration_ms = audio.get_audio_duration(audio_file)
        is_relative = song.is_relative
        
        worker = CreateWaveform(
            audio_file, 
            duration_ms, 
            waveform_file, 
            song_title, 
            notes, 
            bpm, 
            gap, 
            detected_gap, 
            is_relative,
            self.config.detected_gap_color,
            self.config.waveform_color
        )
        worker.signals.finished.connect(lambda song=song: self.data.songs.updated.emit(song))
        self.worker_queue.add_task(worker, True)    

    def update_gap_value(self, song: Song, gap: int):
        if not song: return
        song.gap = gap
        usdx.update_gap(song.txt_file, song.gap)  
        song.info.status = SongStatus.UPDATED
        song.info.updated_gap = gap
        song.info.save()
        self._create_waveforms(song, True)
        self.data.songs.updated.emit(song)

    def revert_gap_value(self, song: Song):
        if not song: return
        song.gap = song.info.original_gap
        usdx.update_gap(song.txt_file, song.gap)  
        song.info.save()
        self._create_waveforms(song, True)
        self.data.songs.updated.emit(song)

    def keep_gap_value(self, song: Song):
        if not song: return
        song.info.status = SongStatus.SOLVED
        song.info.save()
        self.data.songs.updated.emit(song)

    def open_usdx(self):
        song: Song = self.data.selected_song
        if not song:
            logger.error("No song selected")
            return
        if not song.usdb_id:
            logger.error("No USDB ID found")
            return
        logger.info(f"Opening USDB in web browser for {song.txt_file}")
        url = QUrl(f"https://usdb.animux.de/index.php?link=detail&id={song.usdb_id}")
        QDesktopServices.openUrl(url)

    def open_folder(self):
        song: Song = self.data.selected_song
        if not song:
            logger.error("No song selected")
            return
        logger.info(f"Opening folder for {song.path}")
        url = QUrl.fromLocalFile(song.path)
        if not QDesktopServices.openUrl(url):
            print("Failed to open the folder.")
            return False
        return True

