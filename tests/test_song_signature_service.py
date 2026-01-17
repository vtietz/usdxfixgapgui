import os
import time

from model.gap_info import GapInfo
from model.song import Song
from services.song_signature_service import SongSignatureService


def _make_song(tmp_path):
    txt_path = tmp_path / "sample.txt"
    txt_path.write_text("ORIGINAL", encoding="utf-8")

    audio_path = tmp_path / "sample.mp3"
    audio_path.write_bytes(b"abc")

    song = Song(str(txt_path))
    song.audio_file = str(audio_path)
    song.gap_info = GapInfo(str(tmp_path / "usdxfixgap.info"), txt_path.name)
    return song, txt_path, audio_path


def test_capture_processed_signatures_records_current_files(tmp_path):
    song, txt_path, audio_path = _make_song(tmp_path)

    SongSignatureService.capture_processed_signatures(song)

    assert song.gap_info.processed_txt_signature is not None
    assert song.gap_info.processed_audio_signature is not None
    assert song.gap_info.processed_txt_signature["size"] == os.path.getsize(txt_path)
    assert song.gap_info.processed_audio_signature["size"] == os.path.getsize(audio_path)


def test_has_meaningful_change_detects_txt_updates(tmp_path):
    song, txt_path, _ = _make_song(tmp_path)
    SongSignatureService.capture_processed_signatures(song)

    assert not SongSignatureService.has_meaningful_change(song, str(txt_path))

    txt_path.write_text("UPDATED", encoding="utf-8")
    time.sleep(0.01)

    assert SongSignatureService.has_meaningful_change(song, str(txt_path))


def test_has_meaningful_change_detects_audio_updates(tmp_path):
    song, _, audio_path = _make_song(tmp_path)
    SongSignatureService.capture_processed_signatures(song)

    assert not SongSignatureService.has_meaningful_change(song, str(audio_path))

    audio_path.write_bytes(b"abcd")
    time.sleep(0.01)

    assert SongSignatureService.has_meaningful_change(song, str(audio_path))


def test_has_signature_drift_detects_txt_changes(tmp_path):
    song, txt_path, _ = _make_song(tmp_path)
    SongSignatureService.capture_processed_signatures(song)

    assert not SongSignatureService.has_signature_drift(song)

    txt_path.write_text("UPDATED", encoding="utf-8")
    time.sleep(0.01)

    assert SongSignatureService.has_signature_drift(song)


def test_has_signature_drift_detects_audio_changes(tmp_path):
    song, _, audio_path = _make_song(tmp_path)
    SongSignatureService.capture_processed_signatures(song)

    assert not SongSignatureService.has_signature_drift(song)

    # Write different-sized content to guarantee signature change detection
    # (mtime alone may not change on some filesystems within test timing)
    audio_path.write_bytes(b"xyza")
    time.sleep(0.01)

    # Debug: verify song state before assertion
    assert song.audio_file, f"audio_file should be set, got: {song.audio_file!r}"
    assert os.path.exists(song.audio_file), f"audio_file should exist: {song.audio_file}"
    assert song.gap_info is not None, "gap_info should be set"
    assert song.gap_info.processed_audio_signature is not None, "processed_audio_signature should be set"

    assert SongSignatureService.has_signature_drift(song)


def test_has_signature_drift_requires_baseline(tmp_path):
    song, txt_path, _ = _make_song(tmp_path)

    # Skip capturing signatures to simulate missing baseline
    assert not SongSignatureService.has_signature_drift(song)

    txt_path.write_text("UPDATED", encoding="utf-8")
    time.sleep(0.01)

    assert not SongSignatureService.has_signature_drift(song)
