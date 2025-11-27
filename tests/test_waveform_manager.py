from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

import pytest
from PySide6.QtWidgets import QApplication

from app.app_data import AppData
from model.song import Song
from model.songs import Songs
from services.waveform_manager import WaveformManager
from services.waveform_path_service import WaveformPathService


class _DummyQueue:
    def __init__(self):
        self.pauses: list[int] = []
        self.holds: list[str] = []
        self.releases: list[str] = []

    def add_task(self, worker, start_now=False, priority=False):
        return None

    def pause_standard_lane(self, milliseconds: int = 250):
        self.pauses.append(milliseconds)

    def hold_standard_lane(self, reason=None):
        self.holds.append(reason)

    def release_standard_lane(self, reason=None):
        self.releases.append(reason)


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def app_data(tmp_path):
    data = AppData()
    data._tmp_path = str(tmp_path)
    data.songs = Songs()
    data.worker_queue = _DummyQueue()
    return data


def _make_song(tmp_path: Path) -> Song:
    song_dir = tmp_path / "Artist - Title"
    song_dir.mkdir(parents=True, exist_ok=True)
    song = Song(str(song_dir / "song.txt"))
    song.artist = "Artist"
    song.title = "Title"
    song.notes = []  # Simulate metadata-ready song by default
    return song


def test_waveform_manager_dedupes_requests(qapp, app_data, tmp_path, monkeypatch):
    manager = WaveformManager(app_data)
    app_data.waveform_manager = manager
    song = _make_song(tmp_path)
    audio_file = song.path + os.sep + "song.mp3"
    Path(audio_file).write_bytes(b"audio")
    song.audio_file = audio_file

    start_calls: list[str] = []

    def fake_start(self, job, current_song):
        start_calls.append(job.song_path)
        job.pending_targets.add("audio")

    monkeypatch.setattr(WaveformManager, "_start_job", fake_start, raising=False)

    manager.ensure_waveforms(song, requester="test")
    key = next(iter(manager._pending_jobs))
    job = manager._pending_jobs[key]
    job.pending_targets.add("audio")  # Simulate in-flight job
    manager.ensure_waveforms(song, requester="test")

    assert start_calls == [key]


def test_waveform_manager_waits_for_audio_metadata(qapp, app_data, tmp_path, monkeypatch):
    manager = WaveformManager(app_data)
    app_data.waveform_manager = manager

    song = _make_song(tmp_path)
    song.audio_file = ""  # force metadata fetch

    start_calls: list[str] = []

    def fake_start(self, job, current_song):
        start_calls.append(current_song.txt_file)
        job.pending_targets.add("audio")

    monkeypatch.setattr(WaveformManager, "_start_job", fake_start, raising=False)

    metadata_callbacks: list[Callable[[Song], None]] = []

    def fake_metadata_loader(target_song, callback):
        metadata_callbacks.append(callback)

    monkeypatch.setattr(manager, "_start_metadata_timer", lambda key: None)
    monkeypatch.setattr(manager, "_clear_metadata_timer", lambda key: None)
    monkeypatch.setattr(manager, "_load_metadata_async", fake_metadata_loader)

    manager.ensure_waveforms(song, requester="test")
    assert metadata_callbacks  # metadata fetch kicked off
    assert start_calls == []

    audio_file = song.path + os.sep + "song.mp3"
    Path(audio_file).write_bytes(b"audio")
    metadata_song = Song(song.txt_file)
    metadata_song.audio_file = audio_file
    metadata_song.notes = []

    metadata_callbacks[0](metadata_song)

    assert start_calls == [song.txt_file]


def test_waveform_manager_waits_for_notes_metadata(qapp, app_data, tmp_path, monkeypatch):
    manager = WaveformManager(app_data)
    app_data.waveform_manager = manager

    song = _make_song(tmp_path)
    song.notes = None  # force metadata fetch for notes

    audio_file = song.path + os.sep + "song.mp3"
    Path(audio_file).write_bytes(b"audio")
    song.audio_file = audio_file

    start_calls: list[str] = []

    def fake_start(self, job, current_song):
        start_calls.append(current_song.txt_file)
        job.pending_targets.add("audio")

    monkeypatch.setattr(WaveformManager, "_start_job", fake_start, raising=False)
    metadata_callbacks: list[Callable[[Song], None]] = []

    def fake_metadata_loader(target_song, callback):
        metadata_callbacks.append(callback)

    monkeypatch.setattr(manager, "_start_metadata_timer", lambda key: None)
    monkeypatch.setattr(manager, "_clear_metadata_timer", lambda key: None)
    monkeypatch.setattr(manager, "_load_metadata_async", fake_metadata_loader)

    manager.ensure_waveforms(song, requester="test")
    assert metadata_callbacks
    assert start_calls == []

    metadata_song = Song(song.txt_file)
    metadata_song.audio_file = song.audio_file
    metadata_song.notes = []
    metadata_callbacks[0](metadata_song)

    assert start_calls == [song.txt_file]


def test_waveform_manager_pauses_standard_lane_for_metadata(qapp, app_data, tmp_path, monkeypatch):
    manager = WaveformManager(app_data)
    app_data.waveform_manager = manager

    song = _make_song(tmp_path)
    song.notes = None
    song.audio_file = ""  # force metadata fetch for both resources

    monkeypatch.setattr(manager, "_start_metadata_timer", lambda key: None)
    monkeypatch.setattr(manager, "_clear_metadata_timer", lambda key: None)
    monkeypatch.setattr(manager, "_load_metadata_async", lambda song, cb: None)

    manager.ensure_waveforms(song, requester="test")

    assert app_data.worker_queue.pauses
    assert app_data.worker_queue.pauses[-1] >= 600


def test_waveform_manager_holds_standard_lane_during_waveform(qapp, app_data, tmp_path, monkeypatch):
    manager = WaveformManager(app_data)
    app_data.waveform_manager = manager

    song = _make_song(tmp_path)
    audio_file = song.path + os.sep + "song.mp3"
    Path(audio_file).write_bytes(b"audio")
    song.audio_file = audio_file

    paths = {
        "audio_file": audio_file,
        "vocals_file": audio_file,
        "audio_waveform_file": str(tmp_path / "audio.png"),
        "vocals_waveform_file": str(tmp_path / "vocals.png"),
    }

    monkeypatch.setattr(
        WaveformPathService,
        "get_paths",
        lambda s, tmp_root: paths,
    )
    monkeypatch.setattr(WaveformPathService, "waveforms_exists", lambda *args, **kwargs: False)

    def fake_run_direct(self, job, current_song, audio_path, waveform_path, target_key):
        job.pending_targets.add(target_key)
        self._handle_worker_finished(job.song_path, target_key, current_song)

    monkeypatch.setattr(WaveformManager, "_run_direct_waveform", fake_run_direct, raising=False)

    manager.ensure_waveforms(song, use_queue=False)

    assert app_data.worker_queue.holds
    assert app_data.worker_queue.releases
    assert len(app_data.worker_queue.holds) == len(app_data.worker_queue.releases)
