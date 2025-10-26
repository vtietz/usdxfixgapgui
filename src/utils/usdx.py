
import logging
from typing import List, cast
from model.usdx_file import Note

logger = logging.getLogger(__name__)

def fix_gap(gap: int, start_beat: int, bpm: float):
    """
    Corrects gap if first note does not start with beat 0 and song has a start time.

    Ultrastar uses quarter-note interpretation:
    - BPM value represents quarter notes per minute
    - beats_per_ms = (bpm / 60 / 1000) * 4
    - ms_per_beat = 1000 / beats_per_ms = (60 * 1000) / (bpm * 4) = 15000 / bpm

    Args:
        gap: Original gap value in milliseconds
        start_beat: Starting beat of the first note (0 if starts on beat 0)
        bpm: Song BPM (quarter notes per minute)

    Returns:
        Corrected gap in milliseconds
    """
    if start_beat != 0 and bpm > 0:
        # Convert beats to milliseconds using Ultrastar's quarter-note interpretation
        # beats_per_ms = (bpm / 60 / 1000) * 4, so ms_per_beat = 15000 / bpm
        ms_per_beat = 15000.0 / float(bpm)
        position_ms = int(start_beat * ms_per_beat)
        gap = gap - position_ms
        logger.debug(f"fix_gap: start_beat={start_beat}, bpm={bpm}, ms_per_beat={ms_per_beat:.3f}, "
                    f"position_ms={position_ms}, adjusted_gap={gap}")
    return gap

def get_syllaby_at_position(notes: List[Note], position: int):
    for note in notes:
        if note.StartBeat == position:
            return note.Text
    return None

def get_syllable(notes: List[Note], position_ms: int, bpm: float, gap: int, is_relative=False):
    """
    Finds the current syllable being sung at a given position in the song, considering Ultrastar's quarter note interpretation.

    :param notes: The list of notes parsed from the file.
    :param position_ms: Current position in ms.
    :param bpm: Song BPM (quarter notes per minute).
    :param gap: Initial gap before the song starts, in ms.
    :param is_relative: If True, timing is relative to the gap.
    :return: The syllable (note text) at the current position, or None if no syllable is active.
    """
    if not notes or not bpm or bpm <= 0:
        return None

    # Convert BPM to beats per millisecond, accounting for Ultrastar's quarter note interpretation.
    beats_per_ms = (bpm / 60 / 1000) * 4

    # Convert the current position in milliseconds to beats
    position_beats = (position_ms - gap) * beats_per_ms if not is_relative else (position_ms * beats_per_ms)

    for note in notes:
        # Guard against malformed notes
        if note.StartBeat is None or note.Length is None:
            continue
        start_beat = int(note.StartBeat)
        end_beat = start_beat + int(note.Length)

        if start_beat <= position_beats < end_beat:
            return note.Text  # Return the text of the current syllable

    # If no note matches the current position
    return None

def calculate_overlap_duration(note: Note, silence_period):
    """Calculate overlap duration between a note and a silence period."""
    if note.start_ms is None or note.end_ms is None:
        return 0.0
    sp_start = float(silence_period[0])
    sp_end = float(silence_period[1])
    start_ms = float(cast(float, note.start_ms))
    end_ms = float(cast(float, note.end_ms))
    overlap_start = max(start_ms, sp_start)
    overlap_end = min(end_ms, sp_end)
    return max(0.0, overlap_end - overlap_start)


def get_notes_overlap(notes: List[Note], silence_periods, max_length_ms=None):
    """Return percentage of note duration NOT in silence periods."""
    if not notes:
        return 100.0  # If there are no notes, treat as fully not-in-silence

    # Work only with notes that have computed timings
    valid_notes: List[Note] = [
        n for n in notes
        if getattr(n, "start_ms", None) is not None and getattr(n, "end_ms", None) is not None
    ]
    if not valid_notes:
        return 100.0

    # Apply optional max_length_ms filter
    if max_length_ms is not None:
        valid_notes = [
            n for n in valid_notes
            if float(cast(float, n.start_ms)) < float(max_length_ms)
        ]

    # Compute total note duration within the considered window
    if max_length_ms is None:
        total_note_duration = sum(
            float(cast(float, n.end_ms)) - float(cast(float, n.start_ms))
            for n in valid_notes
        )
    else:
        max_len_f = float(max_length_ms)
        total_note_duration = sum(
            max(
                0.0,
                float(min(float(cast(float, n.end_ms)), max_len_f)) - float(cast(float, n.start_ms))
            )
            for n in valid_notes
        )

    total_overlap_duration = 0.0
    for n in valid_notes:
        n_start = float(cast(float, n.start_ms))
        n_end = float(cast(float, n.end_ms))
        for sp in (silence_periods or []):
            sp_start = float(sp[0])
            sp_end = float(sp[1]) if len(sp) > 1 else sp_start
            # Overlap check
            if n_end > sp_start and n_start < sp_end:
                upper_bound = sp_end if max_length_ms is None else float(min(sp_end, float(max_length_ms)))
                total_overlap_duration += calculate_overlap_duration(n, (sp_start, upper_bound))

    if total_note_duration <= 0.0:
        return 100.0

    notes_not_in_silence_percentage = ((total_note_duration - total_overlap_duration) / total_note_duration) * 100.0
    return round(notes_not_in_silence_percentage, 2)