import re
from typing import List
import logging
import utils.files as files
import aiofiles

logger = logging.getLogger(__name__)

class ValidationError(Exception):
    pass

class Tags:
    def __init__(self):
        self.TITLE = None
        self.ARTIST = None
        self.GAP = None
        self.AUDIO = None
        self.BPM = None
        self.RELATIVE = None
        self.START = None

    def __str__(self):
        return f"Tags(TITLE={self.TITLE}, ARTIST={self.ARTIST}, GAP={self.GAP}, AUDIO={self.AUDIO}, BPM={self.BPM}, RELATIVE={self.RELATIVE}, START={self.START})"
    
class Note:
    def __init__(self):
        self.NoteType = None
        self.StartBeat = None
        self.Length = None
        self.Pitch = None
        self.Text = None
        self.start_ms = None
        self.duration_ms = None
        self.end_ms = None

    def __str__(self):
        return f"Notes(NoteType={self.NoteType}, StartBeat={self.StartBeat}, Length={self.Length}, Pitch={self.Pitch}, Text={self.Text})"

class USDXFile:
    
    def __init__(self, filepath):
        self.filepath = filepath
        self.encoding = None
        self.content = None
        self.tags = None

    async def determine_encoding(self):
        async with aiofiles.open(self.filepath, 'rb') as file:
            raw = await file.read()
        encodings = ['utf-8', 'utf-16', 'utf-32', 'cp1252', 'cp1250', 'latin-1', 'ascii', 'windows-1252', 'iso-8859-1', 'iso-8859-15']
        for encoding in encodings:
            try:
                logging.debug(f"Reading ({encoding}): {self.filepath}")
                content = raw.decode(encoding)
                if re.search(r"#TITLE:.+", content, re.MULTILINE):
                    self.encoding = encoding
                    return
            except Exception as e:
                logger.debug(f"Failed to decode '{self.filepath}' with {encoding}: {e}")
        raise Exception(f"Failed to determine encoding for '{self.filepath}'")

    async def load(self):

        logger.debug(f"Loading USDX file: {self.filepath}")

        self.path = files.get_song_path(self.filepath)
        
        if self.encoding is None:
            await self.determine_encoding()
        async with aiofiles.open(self.filepath, 'r', encoding=self.encoding) as file:
            self.content = await file.read()
        
        self.tags, self.notes = USDXFile.parse(self.content)
        
        if self.tags.TITLE is None:
            raise ValidationError("TITLE is missing")
        if self.tags.ARTIST is None:
            raise ValidationError("ARTIST is missing")
        if self.tags.GAP is None:
            raise ValidationError("GAP is missing")
        if self.tags.AUDIO is None:
            raise ValidationError("AUDIO is missing")
        if self.tags.BPM is None:
            raise ValidationError("BPM is missing")
        if self.notes is None:
            raise ValidationError("Notes are missing")
        
        self.calculate_note_times()
        
    async def save(self):
        try:
            with aiofiles.open(self.filepath, 'w', encoding=self.encoding) as file:
                await file.write(self.content)
        except Exception as e:
            self.errors.append(f"Failed to write file: {e}")
            return False
        
    async def _write_tag(self, tag, value):
        self.content = re.sub(rf"#{tag}:.*", f"#{tag}:{value}", self.content)
        self.save()

    async def write_gap_tag(self, value):
        self.tags.GAP = value
        self._write_tag("GAP", value)

    def parse(content) -> tuple[Tags, List[Note]]:
        tags = Tags()
        notes: List[Note] = []
        for line in content.splitlines():
            if line.startswith('#GAP:'):
                value = line.split(':')[1].strip()
                # remove all numbers after "," or "."
                value = value.split(",")[0].split(".")[0] 
                tags.GAP = int(value) if value else None
            elif line.startswith('#TITLE:'):
                tags.TITLE = line.split(':')[1].strip()                
            elif line.startswith('#ARTIST:'):
                tags.ARTIST = line.split(':')[1].strip()
            elif line.startswith('#MP3:'):
                tags.AUDIO = line.split(':')[1].strip()
            elif line.startswith('#AUDIO:'):
                tags.AUDIO = line.split(':')[1].strip()
            elif line.startswith('#BPM:'):
                value = line.split(':')[1].strip()
                tags.BPM = float(value) if value else None
            elif line.startswith('#START:'):
                value = line.split(':')[1].strip()
                tags.START = float(value) if value else None                    
            elif line.startswith('#RELATIVE:'):
                value = line.split(':')[1].strip()
                tags.RELATIVE = value.lower() == "yes" if value else None
            elif not line.startswith('#'):
                parts = line.strip().split()
                if len(parts) >= 5 and parts[0] in {':', '*', 'R', '-', 'F', 'G'}:
                    note = Note()
                    note.NoteType = parts[0]
                    note.StartBeat = int(parts[1])
                    note.Length = int(parts[2])
                    note.Pitch = int(parts[3])
                    note.Text = ' '.join(parts[4:])
                    notes.append(note)
        return tags, notes
    
    def is_loaded(self):
        return self.content is not None
    
    def calculate_note_times(self):
        beats_per_ms = (self.tags.BPM / 60 / 1000) * 4
        for note in self.notes:
            if self.tags.RELATIVE:
                note.start_ms = note.StartBeat / beats_per_ms
                note.end_ms = (note.StartBeat + note.Length) / beats_per_ms
            else:
                note.start_ms = self.tags.GAP + (note.StartBeat / beats_per_ms)
                note.end_ms = self.tags.GAP + ((note.StartBeat + note.Length) / beats_per_ms)
            note.duration_ms = note.end_ms - note.start_ms