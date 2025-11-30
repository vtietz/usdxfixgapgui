import logging
import os
import threading
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Set

from PySide6.QtCore import QObject, Signal, QTimer

from model.song import Song, SongStatus
from services.song_service import SongService
from services.waveform_path_service import WaveformPathService
from workers.create_waveform import CreateWaveform
from utils.run_async import run_async
from utils.waveform import create_waveform_image, draw_notes, draw_silence_periods, draw_title

logger = logging.getLogger(__name__)

FinishedCallback = Callable[[Song], None]


@dataclass
class _WaveformJobState:
    song_path: str
    overwrite: bool
    use_queue: bool
    emit_on_finish: bool
    pending_targets: Set[str] = field(default_factory=set)
    callbacks: List[FinishedCallback] = field(default_factory=list)
    latest_song: Optional[Song] = None
    waiting_for_audio: bool = False
    requesters: Set[str] = field(default_factory=set)
    waiting_for_notes: bool = False
    lane_hold: bool = False
    target_fingerprints: Dict[str, "_WaveformFingerprint"] = field(default_factory=dict)


@dataclass(frozen=True)
class _WaveformFingerprint:
    audio_mtime: float
    audio_size: int


class WaveformManager(QObject):
    """Coordinates waveform generation for songs and deduplicates queued work."""

    waveformQueued = Signal(str)
    waveformReady = Signal(object)
    waveformFailed = Signal(object, str)

    METADATA_TIMEOUT_MS = 4000

    def __init__(self, data, *, direct_run_inline: bool = False):
        super().__init__()
        self._data = data
        self._pending_jobs: Dict[str, _WaveformJobState] = {}
        self._direct_run_inline = direct_run_inline
        self._metadata_waiting: Set[str] = set()
        self._metadata_timeouts: Dict[str, QTimer] = {}
        self._song_service = SongService()
        self._fingerprints: Dict[str, Dict[str, _WaveformFingerprint]] = {}

        songs = getattr(self._data, "songs", None)
        if songs is not None:
            songs.updated.connect(self._on_song_updated)

    def ensure_waveforms(
        self,
        song: Optional[Song],
        *,
        overwrite: bool = False,
        use_queue: bool = True,
        emit_on_finish: bool = True,
        finished_callback: Optional[FinishedCallback] = None,
        requester: Optional[str] = None,
    ):
        if song is None:
            logger.debug("Waveform request skipped: song is None")
            return

        key = self._resolve_song_key(song)
        if not key:
            logger.debug("Waveform request skipped: missing song key")
            return

        job = self._pending_jobs.get(key)
        if not job:
            job = _WaveformJobState(
                song_path=key,
                overwrite=overwrite,
                use_queue=use_queue,
                emit_on_finish=emit_on_finish,
            )
            self._pending_jobs[key] = job
        else:
            job.overwrite = job.overwrite or overwrite
            job.emit_on_finish = job.emit_on_finish or emit_on_finish
            if use_queue:
                job.use_queue = True

        job.latest_song = song
        self._acquire_standard_lane_hold(job)

        audio_ready = bool(getattr(song, "audio_file", None))
        notes_ready = getattr(song, "notes", None) is not None
        job.waiting_for_audio = not audio_ready
        job.waiting_for_notes = not notes_ready
        if requester:
            job.requesters.add(requester)
        if finished_callback:
            job.callbacks.append(finished_callback)

        if job.waiting_for_audio or job.waiting_for_notes:
            self._ensure_metadata_fetch(job, song)
            return

        if not overwrite and notes_ready and WaveformPathService.waveforms_exists(song, self._data.tmp_path):
            self._complete_job(job, song, already_ready=True)
            return

        if job.pending_targets:
            logger.debug("Waveform already running for %s (requesters=%s)", key, sorted(job.requesters))
            return

        self._start_job(job, song)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_cached_fingerprint(self, job_key: str, target_key: str) -> Optional[_WaveformFingerprint]:
        return self._fingerprints.get(job_key, {}).get(target_key)

    def _remember_fingerprint(
        self,
        job_key: str,
        target_key: str,
        fingerprint: Optional[_WaveformFingerprint],
    ) -> None:
        if not fingerprint:
            return
        self._fingerprints.setdefault(job_key, {})[target_key] = fingerprint

    def _compute_audio_fingerprint(self, audio_file: str) -> Optional[_WaveformFingerprint]:
        try:
            stat_result = os.stat(audio_file)
        except OSError:
            return None
        return _WaveformFingerprint(audio_mtime=stat_result.st_mtime, audio_size=stat_result.st_size)

    def _waveform_is_stale(
        self,
        job_key: str,
        target_key: str,
        fingerprint: Optional[_WaveformFingerprint],
        waveform_file: Optional[str],
    ) -> bool:
        if not fingerprint:
            return True

        cached = self._get_cached_fingerprint(job_key, target_key)
        if cached and cached == fingerprint:
            return False

        if not waveform_file or not os.path.exists(waveform_file):
            return True

        try:
            waveform_mtime = os.path.getmtime(waveform_file)
        except OSError:
            return True

        # Regenerate when audio is newer than the current waveform snapshot
        return waveform_mtime < fingerprint.audio_mtime

    def _resolve_song_key(self, song: Song) -> Optional[str]:
        path = getattr(song, "path", None)
        candidate = path or getattr(song, "audio_file", None)
        if not candidate:
            return None
        try:
            return os.path.normcase(os.path.abspath(candidate))
        except Exception:
            return candidate

    def _ensure_metadata_fetch(self, job: _WaveformJobState, song: Song):
        key = job.song_path
        self._slow_standard_lane_for_metadata()
        if key not in self._metadata_waiting:
            logger.debug("Requesting metadata for %s", key)
            self._metadata_waiting.add(key)
            self._start_metadata_timer(key)
            self._load_metadata_async(
                song,
                lambda result, k=key, target=song: self._handle_metadata_loaded(k, target, result),
            )
        else:
            logger.debug("Metadata already requested for %s", key)

    def _slow_standard_lane_for_metadata(self):
        worker_queue = getattr(self._data, "worker_queue", None)
        if not worker_queue:
            return
        try:
            worker_queue.pause_standard_lane(600)
        except Exception:  # pragma: no cover - defensive
            logger.debug("Failed to pause standard lane for metadata", exc_info=True)

    def _load_metadata_async(self, song: Song, callback: Callable[[Optional[Song]], None]):
        def _on_complete(result):
            QTimer.singleShot(0, lambda: callback(result))

        run_async(self._song_service.load_song_metadata_only(song.txt_file), callback=_on_complete)

    def _handle_metadata_loaded(self, key: str, target_song: Song, reloaded_song: Optional[Song]):
        self._metadata_waiting.discard(key)
        self._clear_metadata_timer(key)

        if not reloaded_song:
            logger.warning("Metadata reload returned no result for %s", key)
            return

        if getattr(reloaded_song, "status", None) == SongStatus.ERROR:
            logger.warning("Metadata reload failed for %s", key)
            return

        self._apply_metadata(target_song, reloaded_song)

        job = self._pending_jobs.get(key)
        if job:
            job.waiting_for_audio = not bool(getattr(target_song, "audio_file", None))
            job.waiting_for_notes = getattr(target_song, "notes", None) is None
            if not job.waiting_for_audio and not job.waiting_for_notes and not job.pending_targets:
                job.latest_song = target_song
                self._start_job(job, target_song)
        elif getattr(target_song, "notes", None):
            self.ensure_waveforms(target_song, overwrite=True, requester="metadata-complete")

        try:
            self._data.songs.updated.emit(target_song)
        except Exception:  # pragma: no cover - defensive
            logger.debug("songs.updated emit failed after metadata load", exc_info=True)

    def _start_metadata_timer(self, key: str):
        if key in self._metadata_timeouts:
            return
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: self._handle_metadata_timeout(key))
        timer.start(self.METADATA_TIMEOUT_MS)
        self._metadata_timeouts[key] = timer

    def _handle_metadata_timeout(self, key: str):
        self._clear_metadata_timer(key)
        self._metadata_waiting.discard(key)
        job = self._pending_jobs.get(key)
        if not job:
            return
        if job.waiting_for_notes:
            logger.warning("Metadata load timed out for %s; generating waveform without notes", key)
            job.waiting_for_notes = False
        if not job.waiting_for_audio and job.latest_song:
            self._start_job(job, job.latest_song)

    def _clear_metadata_timer(self, key: str):
        timer = self._metadata_timeouts.pop(key, None)
        if timer:
            try:
                timer.stop()
            except Exception:  # pragma: no cover - defensive
                pass
            timer.deleteLater()

    def _apply_metadata(self, target: Song, source: Song):
        fields = [
            "title",
            "artist",
            "audio",
            "gap",
            "bpm",
            "start",
            "is_relative",
            "audio_file",
            "duration_ms",
            "notes",
        ]
        for attr in fields:
            try:
                setattr(target, attr, getattr(source, attr))
            except Exception:
                logger.debug("Failed to copy %s for %s", attr, target.title)

    def _on_song_updated(self, updated_song: Song):
        key = self._resolve_song_key(updated_song)
        if not key:
            return
        job = self._pending_jobs.get(key)
        if not job:
            return

        audio_ready = bool(getattr(updated_song, "audio_file", None))
        notes_ready = getattr(updated_song, "notes", None) is not None
        resumed = False

        if job.waiting_for_audio and audio_ready:
            job.waiting_for_audio = False
            resumed = True

        if job.waiting_for_notes and notes_ready:
            job.waiting_for_notes = False
            resumed = True

        if resumed and not job.waiting_for_audio and not job.waiting_for_notes:
            if job.pending_targets:
                return
            job.latest_song = updated_song
            self._start_job(job, updated_song)

    def _start_job(self, job: _WaveformJobState, song: Song):
        paths = WaveformPathService.get_paths(song, self._data.tmp_path)
        if not paths:
            self._fail_job(job, "Missing waveform paths")
            return

        scheduled = 0
        scheduled += self._schedule_waveform_for_target(
            job,
            song,
            "audio",
            paths["audio_file"],
            paths["audio_waveform_file"],
        )
        scheduled += self._schedule_waveform_for_target(
            job,
            song,
            "vocals",
            paths["vocals_file"],
            paths["vocals_waveform_file"],
        )

        if scheduled == 0:
            logger.debug("Waveform already up-to-date for %s", job.song_path)
            self._complete_job(job, song, already_ready=True)
            return

        self.waveformQueued.emit(job.song_path)

    def _schedule_waveform_for_target(
        self,
        job: _WaveformJobState,
        song: Song,
        target_key: str,
        audio_file: Optional[str],
        waveform_file: Optional[str],
    ) -> int:
        if not audio_file or not waveform_file:
            return 0
        if not os.path.exists(audio_file):
            logger.debug("Skipping %s waveform, audio missing: %s", target_key, audio_file)
            return 0

        fingerprint = self._compute_audio_fingerprint(audio_file)
        waveform_exists = os.path.exists(waveform_file)

        if not job.overwrite and waveform_exists and fingerprint:
            if not self._waveform_is_stale(job.song_path, target_key, fingerprint, waveform_file):
                logger.debug("Skipping %s waveform, fingerprint unchanged", target_key)
                self._remember_fingerprint(job.song_path, target_key, fingerprint)
                return 0

        if not job.overwrite and waveform_exists and not fingerprint:
            logger.debug(
                "Regenerating %s waveform due to missing fingerprint metadata for %s",
                target_key,
                audio_file,
            )

        if not waveform_exists:
            logger.debug("Scheduling %s waveform, file missing: %s", target_key, waveform_file)

        job.pending_targets.add(target_key)
        if fingerprint:
            job.target_fingerprints[target_key] = fingerprint

        if job.use_queue:
            worker = CreateWaveform(
                song,
                self._data.config,
                audio_file,
                waveform_file,
                is_instant=True,
                target_label=target_key,
            )
            worker.signals.finished.connect(
                lambda *args, key=job.song_path, tk=target_key, s=song: self._handle_worker_finished(key, tk, s)
            )
            worker.signals.error.connect(
                lambda error, key=job.song_path, tk=target_key: self._handle_worker_error(key, tk, error)
            )
            self._data.worker_queue.add_task(worker, True)
        else:
            self._run_direct_waveform(job, song, audio_file, waveform_file, target_key)

        return 1

    def _run_direct_waveform(
        self,
        job: _WaveformJobState,
        song: Song,
        audio_file: str,
        waveform_file: str,
        target_key: str,
    ):
        def _build():
            try:
                color = getattr(self._data.config, "waveform_color", "gray")
                create_waveform_image(audio_file, waveform_file, color)

                gap_info = getattr(song, "gap_info", None)
                duration_ms = int(getattr(gap_info, "duration", 0) or getattr(song, "duration_ms", 0) or 0)
                silence_periods = getattr(gap_info, "silence_periods", []) if gap_info else []
                if silence_periods and duration_ms > 0:
                    draw_silence_periods(waveform_file, silence_periods, duration_ms)

                if song.notes and duration_ms > 0:
                    draw_notes(waveform_file, song.notes, duration_ms, color)

                title = f"{getattr(song, 'artist', '')} - {getattr(song, 'title', '')}".strip(" -")
                if title:
                    draw_title(waveform_file, title, color)

            except Exception as exc:
                self._handle_worker_error(job.song_path, target_key, exc)
                return

            self._handle_worker_finished(job.song_path, target_key, song)

        if self._direct_run_inline:
            _build()
        else:
            threading.Thread(target=_build, daemon=True).start()

    def _handle_worker_finished(self, job_key: str, target_key: str, song: Song):
        job = self._pending_jobs.get(job_key)
        if not job:
            return
        job.pending_targets.discard(target_key)
        if job.pending_targets:
            return
        self._complete_job(job, song)

    def _handle_worker_error(self, job_key: str, target_key: str, error: Exception):
        job = self._pending_jobs.get(job_key)
        if not job:
            return
        job.pending_targets.discard(target_key)
        message = str(error)
        logger.error("Waveform generation failed for %s (%s): %s", job_key, target_key, message)
        if not job.pending_targets:
            failing_song = job.latest_song
            self._pending_jobs.pop(job_key, None)
            self._release_standard_lane_hold(job)
            self.waveformFailed.emit(failing_song, message)

    def _complete_job(self, job: _WaveformJobState, song: Optional[Song], already_ready: bool = False):
        self._pending_jobs.pop(job.song_path, None)
        self._metadata_waiting.discard(job.song_path)
        self._clear_metadata_timer(job.song_path)
        self._release_standard_lane_hold(job)
        if not song:
            return

        if job.emit_on_finish:
            try:
                self._data.songs.updated.emit(song)
            except Exception:  # pragma: no cover - defensive
                logger.debug("songs.updated emit failed", exc_info=True)

        for callback in job.callbacks:
            try:
                callback(song)
            except Exception:  # pragma: no cover - defensive
                logger.debug("Waveform callback failed", exc_info=True)

        if not already_ready:
            logger.debug("Waveform ready for %s", job.song_path)

        for target_key, fingerprint in job.target_fingerprints.items():
            self._remember_fingerprint(job.song_path, target_key, fingerprint)

        self.waveformReady.emit(song)

    def _fail_job(self, job: _WaveformJobState, message: str):
        logger.error("Waveform job aborted for %s: %s", job.song_path, message)
        failing_song = job.latest_song
        self._pending_jobs.pop(job.song_path, None)
        self._metadata_waiting.discard(job.song_path)
        self._clear_metadata_timer(job.song_path)
        self._release_standard_lane_hold(job)
        self.waveformFailed.emit(failing_song, message)

    def _acquire_standard_lane_hold(self, job: _WaveformJobState):
        if job.lane_hold:
            return
        worker_queue = getattr(self._data, "worker_queue", None)
        if not worker_queue:
            return
        try:
            worker_queue.hold_standard_lane(job.song_path)
            job.lane_hold = True
        except Exception:  # pragma: no cover - defensive
            logger.debug("Failed to hold standard lane", exc_info=True)

    def _release_standard_lane_hold(self, job: _WaveformJobState):
        if not job.lane_hold:
            return
        worker_queue = getattr(self._data, "worker_queue", None)
        if not worker_queue:
            job.lane_hold = False
            return
        try:
            worker_queue.release_standard_lane(job.song_path)
        except Exception:  # pragma: no cover - defensive
            logger.debug("Failed to release standard lane hold", exc_info=True)
        finally:
            job.lane_hold = False
