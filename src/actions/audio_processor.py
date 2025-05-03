import os
import logging
from actions.base_manager import BaseManager
from model.song import Song, SongStatus
from workers.detect_audio_length import DetectAudioLengthWorker
from workers.normalize_audio import NormalizeAudioWorker
from workers.create_waveform import CreateWaveform

logger = logging.getLogger(__name__)

class AudioProcessor(BaseManager):
    """Handles audio processing operations like normalization and waveform creation"""
    
    def get_audio_length(self, song: Song):
        worker = DetectAudioLengthWorker(song)
        worker.signals.lengthDetected.connect(lambda song: self.data.songs.updated.emit(song))
        self.worker_queue.add_task(worker, True)

    def normalize_songs(self):
        selected_songs = self.data.selected_songs
        if not selected_songs:
            logger.error("No songs selected for normalization.")
            return
        
        logger.info(f"Queueing normalization for {len(selected_songs)} songs.")
        
        # Use async queuing to prevent UI freeze
        self._queue_tasks_non_blocking(selected_songs, self._normalize_song_if_valid)
    
    def _normalize_song_if_valid(self, song, is_first):
        if song.audio_file:
            self._normalize_song(song, is_first)
        else:
            logger.warning(f"Skipping normalization for '{song.title}': No audio file.")

    def _normalize_song(self, song: Song, start_now=False):
        worker = NormalizeAudioWorker(song)
        worker.signals.started.connect(lambda: self._on_song_worker_started(song))
        worker.signals.error.connect(lambda: self._on_song_worker_error(song))
        worker.signals.finished.connect(lambda: self._on_song_worker_finished(song))
        worker.signals.finished.connect(lambda song=song: self._create_waveforms(song, True))
        song.status = SongStatus.QUEUED
        self.data.songs.updated.emit(song)
        self.worker_queue.add_task(worker, start_now)

    def create_waveforms(self, song: Song, overwrite: bool = False):
        """Public interface to create waveforms for a song"""
        self._create_waveforms(song, overwrite)

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
    
    def _on_song_worker_started(self, song: Song):
        song.status = SongStatus.PROCESSING
        self.data.songs.updated.emit(song)

    def _on_song_worker_error(self, song: Song):
        song.status = SongStatus.ERROR
        self.data.songs.updated.emit(song)

    def _on_song_worker_finished(self, song: Song):
        song.update_status_from_gap_info()
        self.data.songs.updated.emit(song)
