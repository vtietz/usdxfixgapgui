import logging
from actions.base_actions import BaseActions
from actions.audio_actions import AudioActions
from model.song import Song, SongStatus
from model.gap_info import GapInfoStatus
from services.gap_info_service import GapInfoService
from workers.detect_gap import DetectGapWorker, GapDetectionResult, DetectGapWorkerOptions
from utils.run_async import run_async
import utils.usdx as usdx

logger = logging.getLogger(__name__)

class GapActions(BaseActions):
    """Gap detection and management actions"""

    def _detect_gap(self, song: Song, overwrite=False, start_now=False):
        if not song:
            raise Exception("No song given")

        options = DetectGapWorkerOptions(
            audio_file=song.audio_file,
            txt_file=song.txt_file,
            notes=song.notes,
            bpm=song.bpm,
            original_gap=song.gap,
            duration_ms=song.duration_ms,
            config=self.config,
            tmp_path=self.data.tmp_path,
            overwrite=overwrite
        )
        
        worker = DetectGapWorker(options)
        
        worker.signals.started.connect(lambda: self._on_song_worker_started(song))
        worker.signals.error.connect(lambda: self._on_song_worker_error(song))
        worker.signals.finished.connect(lambda result: self._on_detect_gap_finished(song, result))
        song.status = SongStatus.QUEUED
        self.data.songs.updated.emit(song)
        self.worker_queue.add_task(worker, start_now)


    def detect_gap(self, overwrite=False):
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
            logger.warning(f"Skipping gap detection for '{song.title}': No audio file or Spleeter not configured.")

    def _on_detect_gap_finished(self, song: Song, result: GapDetectionResult):
        # Validate that the result matches the song
        if song.txt_file != result.song_file_path:
            logger.error(f"Gap detection result mismatch: {song.txt_file} vs {result.song_file_path}")
            return
            
        # Update song with detection results
        song.gap_info.detected_gap = result.detected_gap
        song.gap_info.diff = result.gap_diff
        song.gap_info.status = result.status
        song.gap_info.notes_overlap = result.notes_overlap
        song.gap_info.silence_periods = result.silence_periods
        song.gap_info.duration = result.duration_ms
        
        # Set song status based on the result status
        song.status = SongStatus.MATCH if result.status == GapInfoStatus.MATCH else SongStatus.MISMATCH
        
        # Save gap info
        run_async(GapInfoService.save(song.gap_info))
        
        # Create waveforms first
        audio_actions = AudioActions(self.data)
        audio_actions._create_waveforms(song, True)
        
        # Check if auto-normalization is enabled
        if self.config.auto_normalize and song.audio_file:
            logger.info(f"Auto-normalizing audio for {song} after gap detection")
            audio_actions._normalize_song(song)
            
        # Notify that the song has been updated
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
        
        audio_actions = AudioActions(self.data)
        audio_actions._create_waveforms(song_to_process, True)
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
        
        audio_actions = AudioActions(self.data)
        audio_actions._create_waveforms(song_to_process, True)
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
