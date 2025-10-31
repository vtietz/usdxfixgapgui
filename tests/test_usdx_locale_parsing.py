"""
Test USDX file parsing with locale-specific decimal formats.

Tests the fix for locale decimal separator handling (comma vs period)
to ensure German/European format songs parse correctly.
"""

from services.usdx_file_service import USDXFileService


class TestLocaleDecimalParsing:
    """Test BPM and START parsing with different decimal formats"""

    def test_bpm_with_period_decimal_separator(self, tmp_path):
        """Test A: US/UK format with period (198.6)"""
        # Setup: Create USDX file content with period decimal separator
        content = "#TITLE:Test Song\n" "#ARTIST:Test Artist\n" "#BPM:198.6\n" "#GAP:1000\n"

        # Action: Parse the content
        tags, notes = USDXFileService.parse(content)

        # Assert: BPM is correctly parsed
        assert tags.BPM == 198.6

    def test_bpm_with_comma_decimal_separator(self, tmp_path):
        """Test B: German/European format with comma (198,6) - THE BUG FIX"""
        # Setup: Create USDX file content with comma decimal separator
        content = "#TITLE:Test Lied\n" "#ARTIST:Test Künstler\n" "#BPM:198,6\n" "#GAP:1000\n"

        # Action: Parse the content
        tags, notes = USDXFileService.parse(content)

        # Assert: BPM is correctly parsed (comma replaced with period)
        assert tags.BPM == 198.6

    def test_start_with_comma_decimal_separator(self, tmp_path):
        """Test C: START tag with comma decimal separator"""
        # Setup: Create USDX file content with comma in START
        content = "#TITLE:Test\n" "#ARTIST:Test\n" "#BPM:120\n" "#START:5,5\n" "#GAP:1000\n"

        # Action: Parse the content
        tags, notes = USDXFileService.parse(content)

        # Assert: START is correctly parsed
        assert tags.START == 5.5

    def test_integer_bpm_still_works(self, tmp_path):
        """Test D: Integer BPM values still parse correctly"""
        # Setup: Create USDX file content with integer BPM
        content = "#TITLE:Test\n" "#ARTIST:Test\n" "#BPM:120\n" "#GAP:1000\n"

        # Action: Parse the content
        tags, notes = USDXFileService.parse(content)

        # Assert: Integer BPM is correctly parsed
        assert tags.BPM == 120.0
