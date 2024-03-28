import re
from typing import List
import logging

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

    def __str__(self):
        return f"Notes(NoteType={self.NoteType}, StartBeat={self.StartBeat}, Length={self.Length}, Pitch={self.Pitch}, Text={self.Text})"

class USDXFile:
    
    def __init__(self, filepath):
        self.filepath = filepath
        self.encoding = None
        self.content = None
        self.tags = None

    def validate(self):

        content = self.content
        # Check for TITLE and ARTIST as mandatory attributes
        for attr, pattern in {"TITLE": r"#TITLE:.+", "ARTIST": r"#ARTIST:.+"}.items():
            if not re.search(pattern, content, re.MULTILINE):
                raise ValidationError(f"Mandatory attribute missing or incorrect: {attr}")

        # Check for AUDIO or MP3
        if not re.search(r"#AUDIO:.+", content, re.MULTILINE) and not re.search(r"#MP3:.+", content, re.MULTILINE):
            raise ValidationError("Either #AUDIO or #MP3 attribute must be present.")

        # BPM is also mandatory
        if not re.search(r"#BPM:\d+", content, re.MULTILINE):
            raise ValidationError("Mandatory attribute missing or incorrect: BPM")
        
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
                logger.debug(f"Failed to decode with {encoding}: {e}")
        raise Exception("Failed to determine encoding")

    async def load(self):
        if self.encoding is None:
            await self.determine_encoding()
        async with aiofiles.open(self.filepath, 'r', encoding=self.encoding) as file:
            self.content = await file.read()
        self.validate()
        
        self.tags = USDXFile.parse_tags(self.content)
        self.notes = USDXFile.parse_notes(self.content)
        
    def save(self):
        try:
            with open(self.filepath, 'w', encoding=self.encoding) as file:
                file.write(self.content)
        except Exception as e:
            self.errors.append(f"Failed to write file: {e}")
            return False
        
    def _write_tag(self, tag, value):
        self.content = re.sub(rf"#{tag}:.*", f"#{tag}:{value}", self.content)
        self.save()

    def write_gap_tag(self, value):
        self.tags.GAP = value
        self._write_tag("GAP", value)

    def parse_tags(content) -> Tags:
        tags = Tags()
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
        return tags
    
    def parse_notes(content) -> List[Note]:
        notes: List[Note] = []
        for line in content.splitlines():
            if not line.startswith('#'):
                parts = line.strip().split()
                if len(parts) >= 5 and parts[0] in {':', '*', 'R', '-', 'F', 'G'}:
                    note = Note()
                    note.NoteType = parts[0]
                    note.StartBeat = int(parts[1])
                    note.Length = int(parts[2])
                    note.Pitch = int(parts[3])
                    note.Text = ' '.join(parts[4:])
                    notes.append(note)
        return notes    