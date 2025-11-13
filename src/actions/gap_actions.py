import logging
from actions.base_actions import BaseActions
from actions.audio_actions import AudioActions
from model.song import Song, SongStatus
from model.gap_info import GapInfoStatus
from model.usdx_file import USDXFile
from services.gap_info_service import GapInfoService
from services.usdx_file_service import USDXFileService
from workers.detect_gap import DetectGapWorker, GapDetectionResult, DetectGapWorkerOptions
from utils.run_async import run_async
import utils.usdx as usdx
from typing import Optional, cast

logger = logging.getLogger(__name__)

# Stable aliases to satisfy static type checkers
GapInfoServiceRef = GapInfoService
USDXFileServiceRef = USDXFileService


class GapActions(BaseActions):
    """Gap detection and management actions"""

    def _detect_gap(self, song: Song, overwrite=False, start_now=False):
        if not song:
            raise Exception("No song given")

        # Ensure gap_info exists to receive detection results
        if not song.gap_info:
            song.gap_info = GapInfoService.create_for_song_path(song.path)

        options = DetectGapWorkerOptions(
            audio_file=song.audio_file,
            txt_file=song.txt_file,
            notes=song.notes or [],
            bpm=song.bpm,
            original_gap=song.gap,
            duration_ms=song.duration_ms,
            config=self.config,
            tmp_path=self.data.tmp_path,
            overwrite=overwrite,
        )

        worker = DetectGapWorker(options)

        worker.signals.started.connect(lambda: self._on_song_worker_started(song))
        worker.signals.error.connect(lambda e: self._on_song_worker_error(song, e))
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

    def _resolve_song(self, song: Optional[Song]) -> Optional[Song]:
        """Resolve a Song instance from an explicit arg or data.first_selected_song, calling if it's a method."""
        if song is not None:
            return song
        candidate = getattr(self.data, "first_selected_song", None)
        if callable(candidate):
            try:
                return cast(Optional[Song], candidate())
            except Exception:
                return None
        return cast(Optional[Song], candidate)

    def _detect_gap_if_valid(self, song, is_first):
        if song.audio_file:
            # Only start immediately if this is the first item AND no task is currently running.
            # Otherwise, add to the queue so the Task Queue shows WAITING and processes sequentially.
            start_now = is_first and not self.worker_queue.running_tasks
            self._detect_gap(song, self._overwrite_gap, start_now)
        else:
            logger.warning(f"Skipping gap detection for '{song.title}': No audio file found.")

    def _on_detect_gap_finished(self, song: Song, result: GapDetectionResult):
        # Validate that the result matches the song
        if song.txt_file != result.song_file_path:
            logger.error(f"Gap detection result mismatch: {song.txt_file} vs {result.song_file_path}")
            return

        # Ensure gap_info exists and then update with detection results
        if not song.gap_info:
            song.gap_info = GapInfoService.create_for_song_path(song.path)

        # Update gap_info with detection results - status mapping happens via owner hook
        # Assign with safe defaults to satisfy type checker and runtime robustness
        song.gap_info.detected_gap = int(result.detected_gap or song.gap_info.detected_gap)
        song.gap_info.diff = int(result.gap_diff or song.gap_info.diff)
        song.gap_info.notes_overlap = float(result.notes_overlap or song.gap_info.notes_overlap)
        song.gap_info.silence_periods = result.silence_periods or []
        song.gap_info.duration = int(result.duration_ms) if result.duration_ms else song.gap_info.duration

        # Update extended detection metadata
        song.gap_info.confidence = result.confidence
        song.gap_info.detection_method = result.detection_method
        song.gap_info.preview_wav_path = result.preview_wav_path
        song.gap_info.waveform_json_path = result.waveform_json_path
        song.gap_info.detected_gap_ms = result.detected_gap_ms
        song.gap_info.tolerance_band_ms = self.config.gap_tolerance

        # Setting gap_info.status triggers _gap_info_updated() which sets Song.status
        song.gap_info.status = result.status or song.gap_info.status

        # Save gap info and update cache
        async def save_gap_and_cache():
            if song.gap_info:
                await GapInfoServiceRef.save(song.gap_info)
            # Update song_cache.db so status persists across app restarts
            from services.song_service import SongService

            SongService().update_cache(song)
            logger.debug(f"Updated song cache after gap detection for {song.txt_file}")

        run_async(save_gap_and_cache())

        # Create waveforms first
        audio_actions = AudioActions(self.data)
        audio_actions._create_waveforms(song, True)

        # Queue auto-normalization as separate worker task (non-blocking)
        if self.config.auto_normalize and song.audio_file:
            # Check if already normalized to avoid unnecessary re-processing
            if song.gap_info and song.gap_info.is_normalized:
                logger.debug(f"Skipping auto-normalization for {song} - already normalized on {song.gap_info.normalized_date}")
            else:
                logger.info(f"Queueing auto-normalization for {song} after gap detection")
                # Use start_now=False to let queue manager schedule it after current tasks
                audio_actions._normalize_song(song, start_now=False)

        # Notify that the song has been updated
        self.data.songs.updated.emit(song)

    def get_notes_overlap(self, song: Optional[Song], silence_periods, detection_time):
        song_to_process = self._resolve_song(song)
        if not song_to_process:
            return

        notes = song_to_process.notes or []
        notes_overlap = usdx.get_notes_overlap(notes, silence_periods, detection_time)

        if not song_to_process.gap_info:
            song_to_process.gap_info = GapInfoServiceRef.create_for_song_path(song_to_process.path)

        song_to_process.gap_info.notes_overlap = notes_overlap

        # Save gap info and update cache
        async def save_gap_and_cache():
            if song_to_process.gap_info:
                await GapInfoServiceRef.save(song_to_process.gap_info)
            # Update song_cache.db so status persists
            from services.song_service import SongService

            SongService().update_cache(song_to_process)
            logger.debug(f"Updated song cache after notes overlap for {song_to_process.txt_file}")

        run_async(save_gap_and_cache())
        self.data.songs.updated.emit(song_to_process)

    def update_gap_value(self, song: Optional[Song], gap: int):
        song_to_process = self._resolve_song(song)
        if not song_to_process:
            logger.error("No song selected for updating gap value.")
            return

        logger.info(f"Updating gap value for '{song_to_process.txt_file}' to {gap}")

        # Update gap value and gap_info - status mapping happens via owner hook
        song_to_process.gap = gap
        if not song_to_process.gap_info:
            song_to_process.gap_info = GapInfoServiceRef.create_for_song_path(song_to_process.path)
        song_to_process.gap_info.updated_gap = gap
        # Setting gap_info.status triggers _gap_info_updated() which sets Song.status
        song_to_process.gap_info.status = GapInfoStatus.UPDATED

        # Update gap tag in file, save gap_info, and update cache
        async def update_gap_and_cache():
            # Update gap tag in .txt file
            usdx_file = USDXFile(song_to_process.txt_file)
            await USDXFileServiceRef.load(usdx_file)
            await USDXFileServiceRef.write_gap_tag(usdx_file, gap)
            logger.debug(f"Gap tag written to {song_to_process.txt_file}")

            # Save gap_info to .info file
            if song_to_process.gap_info:
                await GapInfoServiceRef.save(song_to_process.gap_info)

            # Update song_cache.db so status persists
            from services.song_service import SongService

            SongService().update_cache(song_to_process)
            logger.debug(f"Updated song cache after gap update for {song_to_process.txt_file}")

        run_async(update_gap_and_cache())

        # Recalculate note times with new gap value
        self._recalculate_note_times(song_to_process)

        audio_actions = AudioActions(self.data)
        audio_actions._create_waveforms(song_to_process, True)
        self.data.songs.updated.emit(song_to_process)

    def revert_gap_value(self, song: Optional[Song]):
        song_to_process = self._resolve_song(song)
        if not song_to_process:
            logger.error("No song selected for reverting gap value.")
            return

        orig_gap = song_to_process.gap_info.original_gap if song_to_process.gap_info else song_to_process.gap
        logger.info(f"Reverting gap value for '{song_to_process.txt_file}' to original: {orig_gap}")

        if not song_to_process.gap_info:
            song_to_process.gap_info = GapInfoServiceRef.create_for_song_path(song_to_process.path)

        song_to_process.gap = song_to_process.gap_info.original_gap

        # Revert gap tag in file, save gap_info, and update cache
        async def revert_gap_and_cache():
            # Revert gap tag in .txt file
            usdx_file = USDXFile(song_to_process.txt_file)
            await USDXFileServiceRef.load(usdx_file)
            await USDXFileServiceRef.write_gap_tag(usdx_file, song_to_process.gap)
            logger.debug(f"Gap tag reverted in {song_to_process.txt_file}")

            # Save gap_info to .info file
            if song_to_process.gap_info:
                await GapInfoServiceRef.save(song_to_process.gap_info)

            # Update song_cache.db so status persists
            from services.song_service import SongService

            SongService().update_cache(song_to_process)
            logger.debug(f"Updated song cache after gap revert for {song_to_process.txt_file}")

        run_async(revert_gap_and_cache())

        # Recalculate note times with original gap value
        self._recalculate_note_times(song_to_process)

        audio_actions = AudioActions(self.data)
        audio_actions._create_waveforms(song_to_process, True)
        self.data.songs.updated.emit(song_to_process)

    def keep_gap_value(self, song: Optional[Song]):
        song_to_process = self._resolve_song(song)
        if not song_to_process:
            logger.error("No song selected for keeping gap value.")
            return

        # Mark as solved - status mapping happens via owner hook
        # Setting gap_info.status triggers _gap_info_updated() which sets Song.status
        if not song_to_process.gap_info:
            song_to_process.gap_info = GapInfoServiceRef.create_for_song_path(song_to_process.path)
        song_to_process.gap_info.status = GapInfoStatus.SOLVED

        # Save gap info and update cache
        async def save_gap_and_cache():
            if song_to_process.gap_info:
                await GapInfoServiceRef.save(song_to_process.gap_info)
            # Update song_cache.db so status persists
            from services.song_service import SongService

            SongService().update_cache(song_to_process)
            logger.debug(f"Updated song cache after keeping gap for {song_to_process.txt_file}")

        run_async(save_gap_and_cache())
        self.data.songs.updated.emit(song_to_process)

    def _recalculate_note_times(self, song: Song):
        """Recalculate note times based on current gap, bpm, and is_relative settings"""
        if not song.notes or not song.bpm:
            logger.warning(f"Cannot recalculate note times for {song.txt_file}: missing notes or BPM")
            return

        logger.debug(f"Recalculating note times for {song.txt_file} with gap={song.gap}, bpm={song.bpm}")

        beats_per_ms = (float(song.bpm) / 60 / 1000) * 4

        for note in song.notes:
            # Guard against missing beats/length
            if note.StartBeat is None or note.Length is None:
                continue
            start_beat = int(note.StartBeat)
            length_beats = int(note.Length)
            start_rel_ms = start_beat / beats_per_ms
            end_rel_ms = (start_beat + length_beats) / beats_per_ms
            if song.is_relative:
                note.start_ms = start_rel_ms
                note.end_ms = end_rel_ms
            else:
                note.start_ms = song.gap + start_rel_ms
                note.end_ms = song.gap + end_rel_ms
            note.duration_ms = float(note.end_ms) - float(note.start_ms)

        logger.debug(f"Note times recalculated for {song.txt_file}")
