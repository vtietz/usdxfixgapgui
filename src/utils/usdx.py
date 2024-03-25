
import logging
from typing import List
from utils.usdx_file import Note

logger = logging.getLogger(__name__)
                
def get_gap_offset_according_first_note(bpm: int, notes: List[Note]):
    print(notes)
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
            #print(f"start_beat: {start_beat} - position_beats: {position_beats} - end_beat: {end_beat} - note: {note['Text']}")
            return note.Text  # Return the text of the current syllable

    # If no note matches the current position
    return None


