import logging
import os
from PyQt6.QtCore import QObject, QUrl
from PyQt6.QtGui import QDesktopServices
from data import AppData, Config
from model.song import Song
from utils import files
from utils.worker_queue_manager import WorkerQueueManager
from workers.detect_gap import DetectGapWorker
from workers.normalize_audio import NormalizeAudioWorker
from workers.loading_songs import LoadSongsWorker
from workers.create_waveform import CreateWaveform
from model.song import Song, SongStatus
from model.gap_info import GapInfoStatus
import utils.files as files
import utils.usdx as usdx

logger = logging.getLogger(__name__)

class Actions(QObject):

    data: AppData = None
    
    def __init__(self, data: AppData, config: Config):
        super().__init__()
        self.data = data
        self.config = config
        self.worker_queue = WorkerQueueManager()
    
    def load_songs(self, directory: str):
        logger.debug(f"Loading songs from {directory}")
        self.config.directory = directory
        self.data.tmp_folder = os.path.join(
            self.config.tmp_root, 
            files.generate_directory_hash(directory)
        )
        if self.data.is_loading_songs: 
            logger.debug("Already loading songs")
            return
        self.data.is_loading_songs = True
        self.clear_songs()
        worker = LoadSongsWorker(self.config.directory, self.data.tmp_folder)
        worker.signals.songLoaded.connect(self.data.songs.add)
        worker.signals.songLoaded.connect(self.on_song_loaded)
        worker.signals.finished.connect(lambda: self.finish_loading_songs())
        self.worker_queue.add_task(worker)
    
    def finish_loading_songs(self):
        self.data.is_loading_songs = False

    def clear_songs(self):
        self.data.songs.clear()

    def select_song(self, path: str):
        logger.debug(f"Selected {path}")
        song: Song = next((s for s in self.data.songs if s.path == path), None)
        if(song):
            self.data.selected_song = song
            self._create_waveforms(song)

    def loadingSongsFinished(self):
        self.data.is_loading_songs = False
        logger.debug("Loading songs finished.")

    def detect_gap(self, song: Song = None, overwrite=False, start_now=False):
        if not song:
            song: Song = self.data.selected_song
        if not song:
            raise Exception("No song given")

        audio_file = song.audio_file
        bpm = song.bpm
        gap = song.gap
        if(song.start):
            gap = gap + (song.start * 1000)
        default_detection_time = self.config.default_detection_time

        worker = DetectGapWorker(
            audio_file, 
            self.data.tmp_folder,
            bpm, 
            gap, 
            default_detection_time, 
            overwrite)
        
        worker.signals.started.connect(lambda: self.on_song_worker_started(song))
        worker.signals.error.connect(lambda: self.on_song_worker_error(song))
        worker.signals.finished.connect(
            lambda detected_gap: self.on_detect_gap_finished(song, detected_gap)
        )
        song.status = SongStatus.QUEUED
        self.data.songs.updated.emit(song)
        self.worker_queue.add_task(worker, start_now)

    def on_song_loaded(self, song: Song):
        if(song.gap_info.status == SongStatus.NOT_PROCESSED and self.config.spleeter):
            self.detect_gap(song)
    
    def on_detect_gap_finished(self, song: Song, detected_gap: int):
        gap = song.gap
        firstNoteOffset = usdx.get_gap_offset_according_first_note(song.bpm, song.notes)
        detected_gap = detected_gap - firstNoteOffset
        if(song.start):
            detected_gap = detected_gap - song.start
        gap_diff = abs(gap - detected_gap)
        if gap_diff > self.config.gap_tolerance:
            song.status = SongStatus.MISMATCH
        else:
            song.status = SongStatus.MATCH
        song.gap_info.status = GapInfoStatus.MATCH if song.status == SongStatus.MATCH else GapInfoStatus.MISMATCH
        song.gap_info.detected_gap = detected_gap
        song.gap_info.diff = gap_diff
        song.gap_info.save()
        self._create_waveforms(song, True)

    def on_song_worker_started(self, song: Song):
        song.status = SongStatus.PROCESSING
        self.data.songs.updated.emit(song)

    def on_song_worker_error(self, song: Song):
        song.status = SongStatus.ERROR
        self.data.songs.updated.emit(song)

    def on_song_worker_finished(self, song: Song):
        song.update_status_from_gap_info()
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
        worker = CreateWaveform(
            song,
            audio_file,
            waveform_file,
            self.config.detected_gap_color,
            self.config.waveform_color
        )
        worker.signals.finished.connect(lambda song=song: self.data.songs.updated.emit(song))
        self.worker_queue.add_task(worker, True)    

    def update_gap_value(self, song: Song, gap: int):
        if not song: return
        song.gap = gap
        song.file.write_gap_tag(gap)
        song.status = SongStatus.UPDATED
        song.gap_info.status = GapInfoStatus.UPDATED
        song.gap_info.updated_gap = gap
        song.gap_info.save()
        self._create_waveforms(song, True)
        self.data.songs.updated.emit(song)

    def revert_gap_value(self, song: Song):
        if not song: return
        song.gap = song.gap_info.original_gap
        song.file.write_gap_tag(song.gap)
        song.gap_info.save()
        self._create_waveforms(song, True)
        self.data.songs.updated.emit(song)

    def keep_gap_value(self, song: Song):
        if not song: return
        song.status = SongStatus.SOLVED
        song.gap_info.status = GapInfoStatus.SOLVED
        song.gap_info.save()
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
            logger.error("Failed to open the folder.")
            return False
        return True
    
    def reload_song(self):
        song: Song = self.data.selected_song
        if not song:
            logger.error("No song selected")
            return
        logger.info(f"Reloading song {song.path}")
        song.load()
        self._create_waveforms(song, True)

    def delete_selected_song(self):
        song: Song = self.data.selected_song
        if not song:
            logger.error("No song selected")
            return
        logger.info(f"Deleting song {song.path}")
        self.data.songs.remove(song)
        self.data.songs.deleted.emit(song)
        song.delete()

    def normalize_song(self):
        song: Song = self.data.selected_song
        if not song:
            logger.error("No song selected")
            return
        logger.info(f"Normalizing song {song.path}")
        worker = NormalizeAudioWorker(song)
        worker.signals.started.connect(lambda: self.on_song_worker_started(song))
        worker.signals.error.connect(lambda: self.on_song_worker_error(song))
        #worker.signals.finished.connect(lambda: self.data.songs.updated.emit(song))
        worker.signals.finished.connect(lambda: self.on_song_worker_finished(song))
        worker.signals.finished.connect(lambda: self._create_waveforms(song, True))
        self.worker_queue.add_task(worker, True)
