"""Factory for creating Note objects in tests."""

from model.usdx_file import Note


def create_note(start_beat: int, length: int, pitch: int, text: str = "test") -> Note:
    """
    Create a Note object with specified parameters.

    Args:
        start_beat: The starting beat of the note
        length: The length of the note in beats
        pitch: The pitch of the note
        text: The text/lyric for the note (default: "test")

    Returns:
        A Note object with the specified attributes
    """
    note = Note()
    note.NoteType = ":"  # Regular note
    note.StartBeat = start_beat
    note.Length = length
    note.Pitch = pitch
    note.Text = text
    # Optional: calculate timing if needed (start_ms, duration_ms, end_ms)
    # Can be added later if tests require it
    return note


def create_basic_notes() -> list:
    """
    Create a basic set of two notes for testing.

    Returns:
        List of two Note objects suitable for basic tests
    """
    return [
        create_note(start_beat=0, length=4, pitch=60, text="Hello"),
        create_note(start_beat=4, length=4, pitch=62, text="World")
    ]
