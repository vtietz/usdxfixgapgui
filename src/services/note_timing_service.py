import logging
from model.song import Song

logger = logging.getLogger(__name__)


class NoteTimingService:
    """Utility service for keeping Song.note timing fields in sync with gap/BPM."""

    @staticmethod
    def recalculate(song: Song) -> None:
        """Recalculate note start/end/duration in milliseconds based on current gap and BPM."""
        if not song.notes or not song.bpm:
            logger.warning("Cannot recalculate note times for %s: missing notes or BPM", song.txt_file)
            return

        logger.debug("Recalculating note times for %s with gap=%s, bpm=%s", song.txt_file, song.gap, song.bpm)

        beats_per_ms = (float(song.bpm) / 60 / 1000) * 4
        if beats_per_ms == 0:
            logger.warning("Cannot recalculate note times for %s: zero beats_per_ms", song.txt_file)
            return

        for note in song.notes:
            if note.StartBeat is None or note.Length is None:
                continue

            start_beat = float(note.StartBeat)
            length_beats = float(note.Length)
            start_rel_ms = start_beat / beats_per_ms
            end_rel_ms = (start_beat + length_beats) / beats_per_ms

            if song.is_relative:
                note.start_ms = start_rel_ms
                note.end_ms = end_rel_ms
            else:
                note.start_ms = song.gap + start_rel_ms
                note.end_ms = song.gap + end_rel_ms

            note.duration_ms = float(note.end_ms) - float(note.start_ms)

        logger.debug("Note times recalculated for %s", song.txt_file)
