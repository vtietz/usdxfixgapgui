import asyncio
from types import SimpleNamespace

import pytest

from model.usdx_file import Note
from workers.detect_gap import DetectGapWorker, DetectGapWorkerOptions


class DummyConfig:
    default_detection_time = 20
    gap_tolerance = 400


def test_detect_gap_worker_corrects_zero_start_note(monkeypatch):
    """Gap correction should run even when the first note starts at beat 0."""

    corrected_value = 777
    fix_gap_calls = []

    def fake_fix_gap(detected_gap, start_beat, bpm):
        fix_gap_calls.append((detected_gap, start_beat, bpm))
        return corrected_value

    detection_output = SimpleNamespace(
        detected_gap=123,
        silence_periods=[(0.0, 10.0)],
        confidence=0.5,
        detection_method="mdx",
        preview_wav_path=None,
        waveform_json_path=None,
        detected_gap_ms=123.4,
    )

    note = Note()
    note.StartBeat = 0
    note.Length = 2
    note.Pitch = 3

    options = DetectGapWorkerOptions(
        audio_file="song.mp3",
        txt_file="song.txt",
        notes=[note],
        bpm=359.08,
        original_gap=430,
        duration_ms=1000,
        config=DummyConfig(),
        tmp_path="/tmp",
        overwrite=False,
    )

    worker = DetectGapWorker(options)

    results = []
    worker.signals.finished.connect(lambda res: results.append(res))

    monkeypatch.setattr("workers.detect_gap.detect_gap.perform", lambda *_args, **_kwargs: detection_output)
    monkeypatch.setattr("workers.detect_gap.usdx.fix_gap", fake_fix_gap)

    asyncio.run(worker.run())

    assert results, "Worker did not emit finished signal"
    assert results[0].detected_gap == corrected_value

    assert len(fix_gap_calls) == 1
    detected_gap, start_beat, bpm = fix_gap_calls[0]
    assert detected_gap == 123
    assert start_beat == 0
    assert bpm == pytest.approx(359.08)
