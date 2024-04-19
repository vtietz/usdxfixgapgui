
import logging
from typing import List
from utils.usdx_file import Note

logger = logging.getLogger(__name__)
                
def get_gap_offset_according_first_note(bpm: int, notes: List[Note]):
    start_beat = notes[0].StartBeat
    if start_beat == 0:
        return 0
    position_ms = start_beat / bpm
    return (int)(position_ms)

def get_syllaby_at_position(notes: List[Note], position: int):
    for note in notes:
        if note.StartBeat == position:
            return note.Text
    return None

def get_syllable(notes: List[Note], position_ms: int, bpm: int, gap: int, is_relative=False):
    """
    Finds the current syllable being sung at a given position in the song, considering Ultrastar's quarter note interpretation.

    :param notes: The list of note dictionaries parsed from the file.
    :param position_ms: The current position in the song, in milliseconds.
    :param bpm: The song's BPM (Beats Per Minute), with Ultrastar's quarter note interpretation.
    :param gap: The initial gap before the song starts, in milliseconds.
    :param is_relative: Indicates if the timing is relative to the gap.
    :return: The syllable (note text) at the current position, or None if no syllable is active.
    """
    # Convert BPM to beats per millisecond, accounting for Ultrastar's quarter note interpretation.
    beats_per_ms = (bpm / 60 / 1000) * 4
    
    # Convert the current position in milliseconds to beats
    position_beats = (position_ms - gap) * beats_per_ms if not is_relative else (position_ms * beats_per_ms)

    for note in notes:
        start_beat = note.StartBeat
        end_beat = start_beat + note.Length
        
        if start_beat <= position_beats < end_beat:
            return note.Text  # Return the text of the current syllable

    # If no note matches the current position
    return None

def calculate_overlap_duration(note: Note, silence_period):
    """Calculate overlap duration between a note and a silence period."""
    overlap_start = max(note.start_ms, silence_period[0])
    overlap_end = min(note.end_ms, silence_period[1])
    return max(0, overlap_end - overlap_start)


def get_notes_overlap(notes: List[Note], silence_periods, max_length_ms=None):
    if not notes:
        return 100  # Assuming 100% are not in silent parts if there are no notes.

    # Filter notes to include only those within the specified max_length_ms, if provided
    if max_length_ms is not None:
        notes = [note for note in notes if note.start_ms < max_length_ms]

    total_note_duration = sum(min(note.end_ms, max_length_ms) - note.start_ms for note in notes if max_length_ms is None or note.start_ms < max_length_ms)
    total_overlap_duration = 0

    for note in notes:
        for silence_period in silence_periods:
            if note.end_ms > silence_period[0] and note.start_ms < silence_period[1]:
                # Adjust note's end_ms for the calculation if it goes beyond max_length_ms
                note_end_ms = min(note.end_ms, max_length_ms) if max_length_ms is not None else note.end_ms
                total_overlap_duration += calculate_overlap_duration(note, (silence_period[0], min(silence_period[1], max_length_ms)))

    # Calculate the percentage of note duration NOT in silence
    if total_note_duration == 0:  # Avoid division by zero
        return 100
    notes_not_in_silence_percentage = ((total_note_duration - total_overlap_duration) / total_note_duration) * 100

    return round(notes_not_in_silence_percentage, 2)  # Rounding to 2 decimal places for readability
