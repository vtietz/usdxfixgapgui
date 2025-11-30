from model.song import Song, SongStatus
from model.songs import Songs
from model.gap_info import GapInfo, GapInfoStatus


def _make_song(txt_path: str, status: GapInfoStatus) -> Song:
    song = Song(txt_path)
    gap_info = GapInfo()
    song.gap_info = gap_info
    gap_info.status = status
    return song


def test_add_rebinds_gap_info_owner_and_status():
    songs = Songs()
    existing = _make_song("C:/songs/example.txt", GapInfoStatus.MATCH)
    songs.add(existing)

    duplicate = _make_song("C:/songs/example.txt", GapInfoStatus.MISMATCH)
    songs.add(duplicate)

    assert songs.get_by_txt_file(existing.txt_file) is existing
    assert existing.gap_info.owner is existing
    assert existing.status == SongStatus.MISMATCH

    existing.gap_info.status = GapInfoStatus.UPDATED
    assert existing.status == SongStatus.UPDATED


def test_add_batch_rebinds_gap_info_owner_and_status():
    songs = Songs()
    existing = _make_song("C:/songs/batch.txt", GapInfoStatus.MATCH)
    songs.add(existing)

    duplicate = _make_song("C:/songs/batch.txt", GapInfoStatus.SOLVED)
    songs.add_batch([duplicate])

    assert songs.get_by_txt_file(existing.txt_file) is existing
    assert existing.gap_info.owner is existing
    assert existing.status == SongStatus.SOLVED

    existing.gap_info.status = GapInfoStatus.MISMATCH
    assert existing.status == SongStatus.MISMATCH


def test_gap_info_assignment_preserves_newer_timestamp():
    song = Song("C:/songs/timestamp.txt")
    current = GapInfo()
    current.processed_time = "2025-02-01 10:00:00"
    song.gap_info = current
    song.set_status_timestamp_from_string(current.processed_time)

    replacement = GapInfo()
    replacement.processed_time = "2024-12-31 23:59:59"
    song.gap_info = replacement

    assert song.gap_info.processed_time == "2025-02-01 10:00:00"
    assert song.status_time_display == "2025-02-01 10:00:00"
