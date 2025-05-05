import logging
import os
from common.actions.base_actions import BaseActions
from common.actions.song_actions import SongActions
from model.song import Song, SongStatus
from utils import files
from services.waveform_path_service import WaveformPathService
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
            logger.warning(f"Skipping normalization for {song}: No audio file.")

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
        
        # Check if audio file exists
        if not hasattr(song, 'audio_file') or not song.audio_file:
            logger.warning(f"Cannot create waveforms for song '{song.title if hasattr(song, 'title') else 'Unknown'}': Missing audio file")
            # Trigger song reload to properly load the audio file
            song_actions = SongActions(self.data)
            song_actions.reload_song(song) 
            return
        
        # Check if notes are loaded before creating waveforms
        if not hasattr(song, 'notes') or not song.notes:
            logger.warning(f"Loading notes fpr {song}...")
            song_actions = SongActions(self.data)
            song_actions.load_notes_for_song(song)
        
        # Use the WaveformPathService to get all paths
        paths = WaveformPathService.get_paths(song, self.data.tmp_path)
        if not paths:
            logger.error(f"Could not get waveform paths for song: {song.title if hasattr(song, 'title') else 'Unknown'}")
            return
        
        self._create_waveform(song, paths["audio_file"], paths["audio_waveform_file"], overwrite)
        self._create_waveform(song, paths["vocals_file"], paths["vocals_waveform_file"], overwrite)

    def _create_waveform(self, song: Song, audio_file: str, waveform_file: str, overwrite: bool = False):

        if not os.path.exists(audio_file):
            logger.error(f"Audio file does not exist: {audio_file}")
            return
        
        if os.path.exists(waveform_file) and not overwrite:
            logger.info(f"Waveform file already exists and overwrite is False: {waveform_file}")
            return
        
        logger.debug(f"Creating waveform creation task for {song}")
        worker = CreateWaveform(
            song,
            self.config,
            audio_file,
            waveform_file,
        )
        worker.signals.finished.connect(lambda song=song: self.data.songs.updated.emit(song))
        self.worker_queue.add_task(worker, True)
