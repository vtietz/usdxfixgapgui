
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
                file.write(f"#GAP: {gap}\n")
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

def adjust_gap_according_to_first_note(detected_gap, bpm, notes):
    start_beat = notes[0]['StartBeat']
    if start_beat == 0:
        return detected_gap
    position_ms = start_beat / bpm
    return (int)(detected_gap - position_ms)