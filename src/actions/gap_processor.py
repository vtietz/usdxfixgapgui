import logging
from managers.base_manager import BaseManager
from model.song import Song, SongStatus
from model.gap_info import GapInfoStatus
from workers.detect_gap import DetectGapWorker
from utils.run_async import run_async
import utils.usdx as usdx

logger = logging.getLogger(__name__)

class GapProcessor(BaseManager):
    """Handles gap detection and related operations"""
    
    def detect_gap_for_songs(self, overwrite=False):
        selected_songs = self.data.selected_songs
        if not selected_songs:
            logger.error("No songs selected for gap detection.")
            return
        
        logger.info(f"Queueing gap detection for {len(selected_songs)} songs.")
        
        # Save overwrite parameter for the callback
        self._overwrite_gap = overwrite
        
        # Use async queuing to prevent UI freeze
        self._queue_tasks_non_blocking(selected_songs, self._detect_gap_if_valid)
    
    def _detect_gap_if_valid(self, song, is_first):
        if song.audio_file and self.config.spleeter:
            self._detect_gap(song, self._overwrite_gap, is_first)
        else:
            logger.warning(f"Skipping gap detection for {song}: No audio file or Spleeter not configured.")
    
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
        worker.signals.finished.connect(lambda song=song: self._on_detect_gap_finished(song))
        song.status = SongStatus.QUEUED
        self.data.songs.updated.emit(song)
        self.worker_queue.add_task(worker, start_now)

    def _on_detect_gap_finished(self, song: Song):
        # Notify app that detection is complete
        if hasattr(self.data, 'gap_detection_finished'):
            self.data.gap_detection_finished.emit(song)
        
        # Update song status
        song.update_status_from_gap_info()
        self.data.songs.updated.emit(song)

    def get_notes_overlap(self, song: Song, silence_periods, detection_time):
        song_to_process = song or self.data.first_selected_song
        if not song_to_process: return
        
        notes_overlap = usdx.get_notes_overlap(song_to_process.notes, silence_periods, detection_time)
        song_to_process.gap_info.notes_overlap = notes_overlap
        run_async(song_to_process.gap_info.save())
        self.data.songs.updated.emit(song_to_process)

    def update_gap_value(self, song: Song, gap: int):
        song_to_process = song or self.data.first_selected_song
        if not song_to_process:
            logger.error("No song selected for updating gap value.")
            return
            
        song_to_process.status = SongStatus.UPDATED
        song_to_process.gap = gap
        song_to_process.gap_info.status = GapInfoStatus.UPDATED
        song_to_process.gap_info.updated_gap = gap
        run_async(song_to_process.usdx_file.write_gap_tag(gap))
        run_async(song_to_process.gap_info.save())
        song_to_process.usdx_file.calculate_note_times()
        
        # Notify that gap was updated
        if hasattr(self.data, 'gap_updated'):
            self.data.gap_updated.emit(song_to_process)
        
        self.data.songs.updated.emit(song_to_process)

    def revert_gap_value(self, song: Song):
        song_to_process = song or self.data.first_selected_song
        if not song_to_process:
            logger.error("No song selected for reverting gap value.")
            return
            
        song_to_process.gap = song_to_process.gap_info.original_gap
        run_async(song_to_process.usdx_file.write_gap_tag(song_to_process.gap))
        run_async(song_to_process.gap_info.save())
        song_to_process.usdx_file.calculate_note_times()
        
        # Notify that gap was reverted
        if hasattr(self.data, 'gap_reverted'):
            self.data.gap_reverted.emit(song_to_process)
            
        self.data.songs.updated.emit(song_to_process)

    def keep_gap_value(self, song: Song):
        song_to_process = song or self.data.first_selected_song
        if not song_to_process:
            logger.error("No song selected for keeping gap value.")
            return
            
        song_to_process.status = SongStatus.SOLVED
        song_to_process.gap_info.status = GapInfoStatus.SOLVED
        run_async(song_to_process.gap_info.save())
        self.data.songs.updated.emit(song_to_process)
    
    def _on_song_worker_started(self, song: Song):
        song.status = SongStatus.PROCESSING
        self.data.songs.updated.emit(song)

    def _on_song_worker_error(self, song: Song):
        song.status = SongStatus.ERROR
        self.data.songs.updated.emit(song)
