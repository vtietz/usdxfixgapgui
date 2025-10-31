import re
import os
import logging
import aiofiles
from typing import List, Tuple
from model.usdx_file import USDXFile, Tags, Note, ValidationError
import utils.files as files

logger = logging.getLogger(__name__)


class USDXFileService:
    """Service class for operations on USDX files"""

    @staticmethod
    async def load(usdx_file: USDXFile) -> USDXFile:
        """Load and parse a USDX file"""
        logger.debug(f"Loading USDX file: {usdx_file.filepath}")

        if not usdx_file.filepath:
            raise ValueError("No filepath provided")

        if not os.path.exists(usdx_file.filepath):
            raise FileNotFoundError(f"File not found: {usdx_file.filepath}")

        # Set path
        usdx_file.path = files.get_song_path(usdx_file.filepath)

        # Determine encoding if needed
        if usdx_file.encoding is None:
            await USDXFileService.determine_encoding(usdx_file)

        # Read file content
        async with aiofiles.open(usdx_file.filepath, "r", encoding=usdx_file.encoding) as file:
            usdx_file.content = await file.read()

        # Parse content
        tags, notes = USDXFileService.parse(usdx_file.content)
        usdx_file.tags = tags
        usdx_file.notes = notes

        # Validate required tags
        USDXFileService.validate(usdx_file)

        # Calculate note timings
        USDXFileService.calculate_note_times(usdx_file)

        # Mark as loaded
        usdx_file._loaded = True
        logger.debug(f"Successfully loaded USDX file: {usdx_file.filepath}")

        return usdx_file

    @staticmethod
    async def determine_encoding(usdx_file: USDXFile) -> None:
        """Determine the encoding of the USDX file"""
        async with aiofiles.open(usdx_file.filepath, "rb") as file:
            raw = await file.read()

        encodings = [
            "utf-8",
            "utf-16",
            "utf-32",
            "cp1252",
            "cp1250",
            "latin-1",
            "ascii",
            "windows-1252",
            "iso-8859-1",
            "iso-8859-15",
        ]

        for encoding in encodings:
            try:
                logger.debug(f"Trying encoding {encoding} for {usdx_file.filepath}")
                content = raw.decode(encoding)
                if re.search(r"#TITLE:.+", content, re.MULTILINE):
                    usdx_file.encoding = encoding
                    logger.debug(f"Encoding determined as {encoding} for {usdx_file.filepath}")
                    return
            except Exception as e:
                logger.debug(f"Failed to decode '{usdx_file.filepath}' with {encoding}: {e}")

        raise Exception(f"Failed to determine encoding for {usdx_file.filepath}")

    @staticmethod
    def parse(content: str) -> Tuple[Tags, List[Note]]:
        """Parse USDX file content into tags and notes using strategy pattern"""
        from services.usdx.parsers import create_registry

        tags = Tags()
        notes: List[Note] = []
        registry = create_registry()

        for line in content.splitlines():
            registry.parse_line(line, tags, notes)

        return tags, notes

    @staticmethod
    def validate(usdx_file: USDXFile) -> None:
        """Validate that USDX file has all required tags"""
        if usdx_file.tags.TITLE is None:
            raise ValidationError("TITLE tag is missing")
        if usdx_file.tags.ARTIST is None:
            raise ValidationError("ARTIST tag is missing")
        if usdx_file.tags.GAP is None:
            raise ValidationError("GAP tag is missing")
        if usdx_file.tags.AUDIO is None:
            raise ValidationError("AUDIO tag is missing")
        if usdx_file.tags.BPM is None:
            raise ValidationError("BPM tag is missing")
        if not usdx_file.notes:
            raise ValidationError("Notes are missing")

    @staticmethod
    def calculate_note_times(usdx_file: USDXFile) -> None:
        """Calculate note start and end times in milliseconds with safety guards."""
        bpm = usdx_file.tags.BPM
        if bpm is None or bpm <= 0:
            logger.warning(f"Cannot calculate note times for '{usdx_file.filepath}': BPM missing or invalid ({bpm})")
            return

        beats_per_ms = (bpm / 60 / 1000) * 4
        gap = usdx_file.tags.GAP or 0
        is_relative = bool(usdx_file.tags.RELATIVE)

        for note in usdx_file.notes or []:
            # Guard against malformed notes
            if note.StartBeat is None or note.Length is None:
                continue

            start_beat = float(note.StartBeat)
            length_beats = float(note.Length)

            if is_relative:
                note.start_ms = start_beat / beats_per_ms
                note.end_ms = (start_beat + length_beats) / beats_per_ms
            else:
                note.start_ms = gap + (start_beat / beats_per_ms)
                note.end_ms = gap + ((start_beat + length_beats) / beats_per_ms)

            note.duration_ms = float(note.end_ms) - float(note.start_ms)

    @staticmethod
    async def save(usdx_file: USDXFile) -> None:
        """Save the USDX file content back to disk"""
        logger.debug(f"Saving USDX file: {usdx_file.filepath}")

        if not usdx_file.content:
            raise ValueError("No content to save")

        async with aiofiles.open(usdx_file.filepath, "w", encoding=usdx_file.encoding) as file:
            await file.write(usdx_file.content)

        logger.debug(f"USDX file saved: {usdx_file.filepath}")

    @staticmethod
    async def write_tag(usdx_file: USDXFile, tag: str, value: str) -> None:
        """Write or update a tag in the USDX file"""
        logger.debug(f"Writing {usdx_file.filepath}: {tag}={value}")

        pattern = rf"(?mi)^#\s*{tag}:\s*.*$"
        replacement = f"#{tag}:{value}"

        # Ensure content is a string
        if not isinstance(usdx_file.content, str):
            usdx_file.content = ""

        if re.search(pattern, usdx_file.content):
            usdx_file.content = re.sub(pattern, replacement, usdx_file.content)
        else:
            usdx_file.content = (usdx_file.content or "") + f"\n{replacement}\n"

        await USDXFileService.save(usdx_file)

    @staticmethod
    async def write_gap_tag(usdx_file: USDXFile, value: int) -> None:
        """Update the GAP tag in the USDX file"""
        usdx_file.tags.GAP = value
        await USDXFileService.write_tag(usdx_file, "GAP", str(value))

    @staticmethod
    async def load_notes_only(usdx_file: USDXFile) -> List[Note]:
        """Load only the notes from the file without parsing all metadata"""
        try:
            if not os.path.exists(usdx_file.filepath):
                raise FileNotFoundError(f"File not found: {usdx_file.filepath}")

            # Determine encoding if not already set
            if usdx_file.encoding is None:
                await USDXFileService.determine_encoding(usdx_file)

            # Open the file and read content asynchronously
            async with aiofiles.open(usdx_file.filepath, "r", encoding=usdx_file.encoding) as f:
                lines = await f.readlines()

            # Find and parse notes
            notes = []
            for line in lines:
                parts = line.strip().split()
                if len(parts) >= 5 and parts[0] in {":", "*", "R", "-", "F", "G"}:
                    note = Note()
                    note.NoteType = parts[0]
                    note.StartBeat = int(parts[1])
                    note.Length = int(parts[2])
                    note.Pitch = int(parts[3])
                    note.Text = " ".join(parts[4:])
                    notes.append(note)

            return notes
        except Exception as e:
            logger.error(f"Error loading notes from file: {e}")
            raise

    @staticmethod
    async def create_and_load(filepath: str) -> USDXFile:
        """Create a new USDXFile instance and load it from disk"""
        usdx_file = USDXFile(filepath)
        await USDXFileService.load(usdx_file)
        return usdx_file
