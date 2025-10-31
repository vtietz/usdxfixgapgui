"""
Concrete Tag Handler Implementations

Each class handles parsing of one specific USDX tag or note type.
"""

from model.usdx_file import Tags, Note


class GapTagHandler:
    """Handler for #GAP: tag (integer milliseconds)."""

    @property
    def tag_prefix(self) -> str:
        return "#GAP:"

    def parse(self, line: str, tags: Tags, notes: list) -> None:
        value = line.split(":")[1].strip()
        # Remove all numbers after "," or "."
        value = value.split(",")[0].split(".")[0]
        tags.GAP = int(value) if value else None


class TitleTagHandler:
    """Handler for #TITLE: tag."""

    @property
    def tag_prefix(self) -> str:
        return "#TITLE:"

    def parse(self, line: str, tags: Tags, notes: list) -> None:
        tags.TITLE = line.split(":")[1].strip()


class ArtistTagHandler:
    """Handler for #ARTIST: tag."""

    @property
    def tag_prefix(self) -> str:
        return "#ARTIST:"

    def parse(self, line: str, tags: Tags, notes: list) -> None:
        tags.ARTIST = line.split(":")[1].strip()


class Mp3TagHandler:
    """Handler for #MP3: tag (legacy audio file reference)."""

    @property
    def tag_prefix(self) -> str:
        return "#MP3:"

    def parse(self, line: str, tags: Tags, notes: list) -> None:
        tags.AUDIO = line.split(":")[1].strip()


class AudioTagHandler:
    """Handler for #AUDIO: tag."""

    @property
    def tag_prefix(self) -> str:
        return "#AUDIO:"

    def parse(self, line: str, tags: Tags, notes: list) -> None:
        tags.AUDIO = line.split(":")[1].strip()


class BpmTagHandler:
    """Handler for #BPM: tag (float with locale-aware decimal parsing)."""

    @property
    def tag_prefix(self) -> str:
        return "#BPM:"

    def parse(self, line: str, tags: Tags, notes: list) -> None:
        value = line.split(":")[1].strip()
        # Handle both period and comma as decimal separator (locale-aware)
        value_normalized = value.replace(",", ".") if value else None
        tags.BPM = float(value_normalized) if value_normalized else None


class StartTagHandler:
    """Handler for #START: tag (float milliseconds)."""

    @property
    def tag_prefix(self) -> str:
        return "#START:"

    def parse(self, line: str, tags: Tags, notes: list) -> None:
        value = line.split(":")[1].strip()
        # Handle both period and comma as decimal separator
        value_normalized = value.replace(",", ".") if value else None
        tags.START = float(value_normalized) if value_normalized else None


class RelativeTagHandler:
    """Handler for #RELATIVE: tag (boolean yes/no)."""

    @property
    def tag_prefix(self) -> str:
        return "#RELATIVE:"

    def parse(self, line: str, tags: Tags, notes: list) -> None:
        value = line.split(":")[1].strip()
        tags.RELATIVE = value.lower() == "yes" if value else None


class NoteLineHandler:
    """Handler for note lines (non-tag lines with note data)."""

    @property
    def tag_prefix(self) -> str:
        return ""  # Empty prefix indicates this handles non-tag lines

    def parse(self, line: str, tags: Tags, notes: list) -> None:
        parts = line.strip().split()
        if len(parts) >= 5 and parts[0] in {":", "*", "R", "-", "F", "G"}:
            note = Note()
            note.NoteType = parts[0]
            note.StartBeat = int(parts[1])
            note.Length = int(parts[2])
            note.Pitch = int(parts[3])
            note.Text = " ".join(parts[4:])
            notes.append(note)
