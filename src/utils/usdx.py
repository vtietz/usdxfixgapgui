
import os


def extract_tags(file_path):
    """Extract #GAP, #MP3, #BPM, and #RELATIVE values from the given file."""
    print(f"Extracting tags from {file_path}...")
    tags = {'TITLE': None, 'ARTIST' : None, 'GAP': None, 'MP3': None, 'BPM': None, 'RELATIVE': None}
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            for line in file:
                if line.startswith('#GAP:'):
                    value = line.split(':')[1].strip()
                    tags['GAP'] = int(value) if value else None
                elif line.startswith('#TITLE:'):
                    tags['TITLE'] = line.split(':')[1].strip()                
                elif line.startswith('#ARTIST:'):
                    tags['ARTIST'] = line.split(':')[1].strip()
                elif line.startswith('#MP3:'):
                    tags['AUDIO'] = line.split(':')[1].strip()
                elif line.startswith('#AUDIO:'):
                    tags['AUDIO'] = line.split(':')[1].strip()
                elif line.startswith('#BPM:'):
                    value = line.split(':')[1].strip()
                    tags['BPM'] = float(value) if value else None
                elif line.startswith('#RELATIVE:'):
                    value = line.split(':')[1].strip()
                    tags['RELATIVE'] = value.lower() == "yes" if value else None
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
    return tags

def update_gap(file_path, gap):
    """Update the GAP value in the given file."""
    with open(file_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()
    with open(file_path, 'w', encoding='utf-8') as file:
        for line in lines:
            if line.startswith('#GAP:'):
                file.write(f"#GAP:{gap}\n")
            else:
                file.write(line)
                

def parse_notes(file_path):
    """
    Parses notes from a given text file, starting after the first line that begins with '#'.

    :param file_path: Path to the text file containing the notes.
    :return: A list of dictionaries, each representing a note.
    """
    print(f"Parsing notes from {file_path}...")
    notes = []
    start_parsing = False  # Flag to indicate when to start parsing notes
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            for line in file:
                if line.startswith('#'):
                    start_parsing = True  # Start parsing notes after this line
                    continue
                if start_parsing and line.strip() and not line.startswith('#'):
                    parts = line.strip().split()
                    if len(parts) >= 5 and parts[0] in {':', '*', 'R', '-', 'F', 'G'}:
                        note = {
                            'NoteType': parts[0],
                            'StartBeat': int(parts[1]),
                            'Length': int(parts[2]),
                            'Pitch': int(parts[3]),
                            'Text': ' '.join(parts[4:])
                        }
                        notes.append(note)
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
    return notes

def get_gap_offset_according_firts_note(bpm, notes):
    start_beat = notes[0]['StartBeat']
    if start_beat == 0:
        return 0
    position_ms = start_beat / bpm
    return (int)(position_ms)

def get_syllaby_at_position(notes, position):
    for note in notes:
        if note['StartBeat'] == position:
            return note['Text']
    return None

def get_syllable(notes, position_ms, bpm, gap, is_relative=False):
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
        start_beat = note['StartBeat']
        end_beat = start_beat + note['Length']
        
        if start_beat <= position_beats < end_beat:
            #print(f"start_beat: {start_beat} - position_beats: {position_beats} - end_beat: {end_beat} - note: {note['Text']}")
            return note['Text']  # Return the text of the current syllable

    # If no note matches the current position
    return None