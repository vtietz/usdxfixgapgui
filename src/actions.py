import logging
import os
from PyQt6.QtCore import QObject, QUrl
from PyQt6.QtGui import QDesktopServices
from data import AppData
from model.song import Song
from utils.run_async import run_async, run_sync
from workers.worker_queue_manager import WorkerQueueManager
from workers.detect_audio_length import DetectAudioLengthWorker
from workers.detect_gap import DetectGapWorker
from workers.load_usdx_files import LoadUsdxFilesWorker
from workers.normalize_audio import NormalizeAudioWorker
from workers.create_waveform import CreateWaveform
from model.song import Song, SongStatus
from model.gap_info import GapInfoStatus
import utils.usdx as usdx

logger = logging.getLogger(__name__)

class Actions(QObject):

    data: AppData = None
    
    def __init__(self, data: AppData):
        super().__init__()
        self.data = data
        self.config = data.config
        self.worker_queue = WorkerQueueManager()

    def set_directory(self, directory: str):
        self.data.directory = directory
        self._claer_songs()
        self._load_songs()

    def _claer_songs(self):
        self.data.songs.clear()

    def _load_songs(self):
        worker = LoadUsdxFilesWorker(self.data.directory, self.data.tmp_path)
        worker.signals.songLoaded.connect(self._on_song_loaded)
        worker.signals.finished.connect(self._on_loading_songs_finished)
        self.worker_queue.add_task(worker, True)

    def select_song(self, path: str):
        logger.debug(f"Selected {path}")
        song: Song = next((s for s in self.data.songs if s.path == path), None)
        self.data.selected_song = song
        self._create_waveforms(song)

    def _on_song_loaded(self, song: Song):
        self.data.songs.add(song)
        if(song.status == SongStatus.NOT_PROCESSED):
            song.gap_info.original_gap = song.gap
            if(self.config.spleeter):
                self._detect_gap(song)
        
    def _on_loading_songs_finished(self):
        self.data.is_loading_songs = False

    def _get_audio_length(self, song: Song):
        worker = DetectAudioLengthWorker(song)
        worker.signals.lengthDetected.connect(lambda song: self.data.songs.updated.emit(song))
        self.worker_queue.add_task(worker, True)

    def _detect_gap(self, song: Song, overwrite=False, start_now=False):
        if not song:
            raise Exception("No song given")

        worker = DetectGapWorker(
            song, 
            self.config,
            self.data.tmp_path,
            self.config.default_detection_time,
            overwrite
        )
        
        worker.signals.started.connect(lambda: self._on_song_worker_started(song))
        worker.signals.error.connect(lambda: self._on_song_worker_error(song))
        worker.signals.finished.connect(self._on_detect_gap_finished)
        song.status = SongStatus.QUEUED
        self.data.songs.updated.emit(song)
        self.worker_queue.add_task(worker, start_now)

    def detect_gap(self, overwrite=False):
        song: Song = self.data.selected_song
        if(song):
            self._detect_gap(song, overwrite, True)
        else:
            logger.error("No song selected")

    def get_notes_overlap(self, song: Song, silence_periods, detection_time):
        notes_overlap = usdx.get_notes_overlap(song.notes, silence_periods, detection_time)
        song.gap_info.notes_overlap = notes_overlap
        run_async(song.gap_info.save())
        self.data.songs.updated.emit(song)

    def update_gap_value(self, song: Song, gap: int):
        if not song: 
            return
        song.status = SongStatus.UPDATED
        song.gap = gap
        song.gap_info.status = GapInfoStatus.UPDATED
        song.gap_info.updated_gap = gap
        run_async(song.usdx_file.write_gap_tag(gap))
        run_async(song.gap_info.save())
        song.usdx_file.calculate_note_times()
        self._create_waveforms(song, True)
        self.data.songs.updated.emit(song)

    def revert_gap_value(self, song: Song):
        if not song: return
        song.gap = song.gap_info.original_gap
        run_async(song.usdx_file.write_gap_tag(song.gap))
        run_async(song.gap_info.save())
        song.usdx_file.calculate_note_times()
        self._create_waveforms(song, True)
        self.data.songs.updated.emit(song)

    def keep_gap_value(self, song: Song):
        if not song: return
        song.status = SongStatus.SOLVED
        song.gap_info.status = GapInfoStatus.SOLVED
        run_async(song.gap_info.save())
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
        try:
            run_sync(song.load())
            self._create_waveforms(song, True)
        except Exception as e:
            song.error_message = str(e)
            logger.exception(e)

    def delete_selected_song(self):
        song: Song = self.data.selected_song
        if not song:
            logger.error("No song selected")
            return
        logger.info(f"Deleting song {song.path}")
        song.delete()
        self.data.songs.remove(song)
        self.data.songs.deleted.emit(song)

    def normalize_song(self):
        song: Song = self.data.selected_song
        if not song:
            logger.error("No song selected")
            return
        logger.info(f"Normalizing song {song.path}")
        self._normalize_song(song, True)  # Start immediately when user explicitly requests it

    def _normalize_song(self, song: Song, start_now=False):
        worker = NormalizeAudioWorker(song)
        worker.signals.started.connect(lambda: self._on_song_worker_started(song))
        worker.signals.error.connect(lambda: self._on_song_worker_error(song))
        worker.signals.finished.connect(lambda: self._on_song_worker_finished(song))
        worker.signals.finished.connect(lambda: self._create_waveforms(song, True))
        song.status = SongStatus.QUEUED
        self.data.songs.updated.emit(song)
        self.worker_queue.add_task(worker, start_now)

    def _on_detect_gap_finished(self, song: Song):
        self._create_waveforms(song, True)

    def _on_song_worker_started(self, song: Song):
        song.status = SongStatus.PROCESSING
        self.data.songs.updated.emit(song)

    def _on_song_worker_error(self, song: Song):
        song.status = SongStatus.ERROR
        self.data.songs.updated.emit(song)

    def _on_song_worker_finished(self, song: Song):
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
            self.config,
            audio_file,
            waveform_file,
        )
        worker.signals.finished.connect(lambda song=song: self.data.songs.updated.emit(song))
        self.worker_queue.add_task(worker, True)    
    