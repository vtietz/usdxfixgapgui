import logging
import os
from common.actions.base_actions import BaseActions
from model.song import Song, SongStatus
from workers.detect_audio_length import DetectAudioLengthWorker
from workers.normalize_audio import NormalizeAudioWorker
from workers.create_waveform import CreateWaveform

logger = logging.getLogger(__name__)

class AudioActions(BaseActions):
    """Audio processing actions like normalization and waveform generation"""

    def _get_audio_length(self, song: Song):
        worker = DetectAudioLengthWorker(song)
        worker.signals.lengthDetected.connect(lambda song: self.data.songs.updated.emit(song))
        self.worker_queue.add_task(worker, True)

    def normalize_song(self):
        selected_songs = self.data.selected_songs
        if not selected_songs:
            logger.error("No songs selected for normalization.")
            return
        
        logger.info(f"Queueing normalization for {len(selected_songs)} songs.")
        
        # Use async queuing to prevent UI freeze
        # self._queue_tasks_non_blocking(selected_songs, self._normalize_song_if_valid)

        if len(selected_songs) == 1:
            # If only one song is selected, normalize it immediately
            self._normalize_song_if_valid(selected_songs[0], True)
        else:
            for song in selected_songs:
                self._normalize_song_if_valid(song, False)
    
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
        
        # Only create waveforms if this is the first selected song
        if song == self.data.first_selected_song:
            worker.signals.finished.connect(lambda: self._create_waveforms(song, True))
        
        song.status = SongStatus.QUEUED
        self.data.songs.updated.emit(song)
        self.worker_queue.add_task(worker, start_now)

    def _create_waveforms(self, song: Song, overwrite: bool = False):
        if not song:
            raise Exception("No song given")
        
        self._create_waveform(song, song.audio_file, song.audio_waveform_file, overwrite)
        self._create_waveform(song, song.vocals_file, song.vocals_waveform_file, overwrite)

    def _create_waveform(self, song: Song, audio_file: str, waveform_file: str, overwrite: bool = False):

        if not os.path.exists(audio_file):
            logger.error(f"Audio file does not exist: {audio_file}")
            return
        
        if os.path.exists(waveform_file) and not overwrite:
            logger.info(f"Waveform file already exists and overwrite is False: {waveform_file}")
            return
        
        logger.debug(f"Creating waveform creation task for '{audio_file}'")
        worker = CreateWaveform(
            song,
            self.config,
            audio_file,
            waveform_file,
        )
        worker.signals.finished.connect(lambda song=song: self.data.songs.updated.emit(song))
        self.worker_queue.add_task(worker, True)
