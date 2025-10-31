"""Test that German umlauts and special characters are handled correctly"""

import asyncio
import os
import tempfile
from services.usdx_file_service import USDXFileService
from model.usdx_file import USDXFile


def test_load_notes_with_german_umlauts():
    """Test that we can load notes from files with German umlauts (ä, ö, ü)"""
    # Create a temporary USDX file with German umlauts in Windows-1252 encoding
    content = """#TITLE:Ich wäre gern wie Du
#ARTIST:König Louie
#MP3:song.mp3
#BPM:120
#GAP:1000
: 0 4 5 Ich
: 4 4 6 wä~
: 8 4 7 re
: 12 4 8 gern
"""

    with tempfile.NamedTemporaryFile(mode="w", encoding="cp1252", suffix=".txt", delete=False) as f:
        f.write(content)
        temp_file = f.name

    try:
        # Load notes from the file
        usdx_file = USDXFile(temp_file)
        notes = asyncio.run(USDXFileService.load_notes_only(usdx_file))

        # Verify notes were loaded correctly
        assert len(notes) == 4
        assert notes[0].Text == "Ich"
        assert notes[1].Text == "wä~"
        assert notes[2].Text == "re"
        assert notes[3].Text == "gern"

        # Verify encoding was detected
        assert usdx_file.encoding in ["cp1252", "windows-1252", "latin-1"]

    finally:
        if os.path.exists(temp_file):
            os.unlink(temp_file)


def test_load_notes_with_utf8_encoding():
    """Test that UTF-8 files also work correctly"""
    content = """#TITLE:Über den Wolken
#ARTIST:Reinhard Mey
#MP3:song.mp3
#BPM:120
#GAP:1000
: 0 4 5 Ü~
: 4 4 6 ber
: 8 4 7 den
: 12 4 8 Wol~
: 16 4 9 ken
"""

    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".txt", delete=False) as f:
        f.write(content)
        temp_file = f.name

    try:
        # Load notes from the file
        usdx_file = USDXFile(temp_file)
        notes = asyncio.run(USDXFileService.load_notes_only(usdx_file))

        # Verify notes were loaded correctly
        assert len(notes) == 5
        assert notes[0].Text == "Ü~"
        assert notes[1].Text == "ber"
        assert notes[4].Text == "ken"

        # Verify encoding was detected
        assert usdx_file.encoding == "utf-8"

    finally:
        if os.path.exists(temp_file):
            os.unlink(temp_file)
