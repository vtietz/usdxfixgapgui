import logging
from typing import List
from model.usdx_file import Note

logger = logging.getLogger(__name__)


def fix_gap(gap: int, start_beat: int, bpm: float):
    """
    Corrects a metadata gap value by aligning it to the first note position.

    Note: beat 0 is a valid first-note position. When `start_beat` is 0, this function
    returns the input `gap` unchanged.

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
        logger.debug(
            "fix_gap: start_beat=%s, bpm=%s, ms_per_beat=%.3f, position_ms=%s, adjusted_gap=%s",
            start_beat,
            bpm,
            ms_per_beat,
            position_ms,
            gap,
        )
    return gap


def get_syllaby_at_position(notes: List[Note], position: int):
    for note in notes:
        if note.StartBeat == position:
            return note.Text
    return None


def get_syllable(notes: List[Note], position_ms: int, bpm: float, gap: int, is_relative=False):
    """
    Finds the current syllable being sung at a given position in the song,
    considering Ultrastar's quarter note interpretation.

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
