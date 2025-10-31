"""
Tests for multi-entry gap info support.

Tests backward compatibility with legacy single-entry format and
new multi-entry format for folders with multiple .txt files.
"""

import sys
import json
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from model.gap_info import GapInfo, GapInfoStatus
from services.gap_info_service import GapInfoService


class TestGapInfoMultiEntry:
    """Test multi-entry gap info functionality"""

    def test_load_legacy_single_entry_for_single_txt(self, tmp_path):
        """Legacy JSON without 'entries' should load correctly"""
        # Create legacy gap info file
        info_file = tmp_path / "usdxfixgap.info"
        legacy_data = {
            "status": "MATCH",
            "original_gap": 5000,
            "detected_gap": 5200,
            "updated_gap": 0,
            "diff": 200,
            "duration": 180000,
            "notes_overlap": 0.5,
            "processed_time": "2025-10-20 10:00:00",
            "silence_periods": [[0, 5200]],
            "is_normalized": False,
            "normalized_date": None,
            "normalization_level": None,
            "detection_method": "mdx",
            "confidence": 0.95,
        }

        info_file.write_text(json.dumps(legacy_data, indent=4), encoding="utf-8")

        # Load gap info
        gap_info = GapInfo(str(info_file), "Song.txt")
        asyncio.run(GapInfoService.load(gap_info))

        # Verify fields loaded correctly
        assert gap_info.status == GapInfoStatus.MATCH
        assert gap_info.original_gap == 5000
        assert gap_info.detected_gap == 5200
        assert gap_info.diff == 200
        assert gap_info.duration == 180000
        assert gap_info.confidence == 0.95

    def test_load_multi_entry_exact_match(self, tmp_path):
        """Multi-entry file with exact txt_basename match should load that entry"""
        info_file = tmp_path / "usdxfixgap.info"
        multi_data = {
            "version": 2,
            "entries": {
                "SongA.txt": {
                    "status": "MATCH",
                    "original_gap": 1000,
                    "detected_gap": 1100,
                    "updated_gap": 0,
                    "diff": 100,
                    "duration": 120000,
                    "notes_overlap": 0.3,
                    "processed_time": "2025-10-20 10:00:00",
                    "silence_periods": [[0, 1100]],
                    "is_normalized": False,
                    "normalized_date": None,
                    "normalization_level": None,
                    "detection_method": "mdx",
                    "confidence": 0.90,
                },
                "SongB.txt": {
                    "status": "MISMATCH",
                    "original_gap": 2000,
                    "detected_gap": 3000,
                    "updated_gap": 0,
                    "diff": 1000,
                    "duration": 150000,
                    "notes_overlap": 0.7,
                    "processed_time": "2025-10-20 11:00:00",
                    "silence_periods": [[0, 3000]],
                    "is_normalized": False,
                    "normalized_date": None,
                    "normalization_level": None,
                    "detection_method": "mdx",
                    "confidence": 0.85,
                },
            },
        }

        info_file.write_text(json.dumps(multi_data, indent=4), encoding="utf-8")

        # Load for SongA
        gap_info_a = GapInfo(str(info_file), "SongA.txt")
        asyncio.run(GapInfoService.load(gap_info_a))

        assert gap_info_a.status == GapInfoStatus.MATCH
        assert gap_info_a.original_gap == 1000
        assert gap_info_a.detected_gap == 1100
        assert gap_info_a.confidence == 0.90

        # Load for SongB
        gap_info_b = GapInfo(str(info_file), "SongB.txt")
        asyncio.run(GapInfoService.load(gap_info_b))

        assert gap_info_b.status == GapInfoStatus.MISMATCH
        assert gap_info_b.original_gap == 2000
        assert gap_info_b.detected_gap == 3000
        assert gap_info_b.confidence == 0.85

    def test_load_multi_entry_fallback_default(self, tmp_path):
        """Multi-entry file without match should fall back to 'default' if present"""
        info_file = tmp_path / "usdxfixgap.info"
        multi_data = {
            "version": 2,
            "entries": {
                "SongA.txt": {
                    "status": "MATCH",
                    "original_gap": 1000,
                    "detected_gap": 1100,
                    "updated_gap": 0,
                    "diff": 100,
                    "duration": 120000,
                    "notes_overlap": 0.3,
                    "processed_time": "2025-10-20 10:00:00",
                    "silence_periods": [],
                    "is_normalized": False,
                    "normalized_date": None,
                    "normalization_level": None,
                    "detection_method": "mdx",
                    "confidence": 0.90,
                }
            },
            "default": {
                "status": "NOT_PROCESSED",
                "original_gap": 0,
                "detected_gap": 0,
                "updated_gap": 0,
                "diff": 0,
                "duration": 0,
                "notes_overlap": 0.0,
                "processed_time": "",
                "silence_periods": [],
                "is_normalized": False,
                "normalized_date": None,
                "normalization_level": None,
                "detection_method": "mdx",
                "confidence": None,
            },
        }

        info_file.write_text(json.dumps(multi_data, indent=4), encoding="utf-8")

        # Load for SongC (not in entries, should use default)
        gap_info_c = GapInfo(str(info_file), "SongC.txt")
        asyncio.run(GapInfoService.load(gap_info_c))

        assert gap_info_c.status == GapInfoStatus.NOT_PROCESSED
        assert gap_info_c.original_gap == 0
        assert gap_info_c.detected_gap == 0

    def test_load_multi_entry_single_entry_fallback(self, tmp_path):
        """Multi-entry file with exactly one entry should use it as fallback"""
        info_file = tmp_path / "usdxfixgap.info"
        multi_data = {
            "version": 2,
            "entries": {
                "SongA.txt": {
                    "status": "MATCH",
                    "original_gap": 1000,
                    "detected_gap": 1100,
                    "updated_gap": 0,
                    "diff": 100,
                    "duration": 120000,
                    "notes_overlap": 0.3,
                    "processed_time": "2025-10-20 10:00:00",
                    "silence_periods": [],
                    "is_normalized": False,
                    "normalized_date": None,
                    "normalization_level": None,
                    "detection_method": "mdx",
                    "confidence": 0.90,
                }
            },
        }

        info_file.write_text(json.dumps(multi_data, indent=4), encoding="utf-8")

        # Load for SongB (not in entries, but only one entry exists)
        gap_info_b = GapInfo(str(info_file), "SongB.txt")
        asyncio.run(GapInfoService.load(gap_info_b))

        # Should use the single entry as fallback
        assert gap_info_b.status == GapInfoStatus.MATCH
        assert gap_info_b.original_gap == 1000
        assert gap_info_b.detected_gap == 1100

    def test_load_multi_entry_no_match_no_fallback(self, tmp_path):
        """Multi-entry file with no match and no fallback should stay NOT_PROCESSED"""
        info_file = tmp_path / "usdxfixgap.info"
        multi_data = {
            "version": 2,
            "entries": {
                "SongA.txt": {
                    "status": "MATCH",
                    "original_gap": 1000,
                    "detected_gap": 1100,
                    "updated_gap": 0,
                    "diff": 100,
                    "duration": 120000,
                    "notes_overlap": 0.3,
                    "processed_time": "2025-10-20 10:00:00",
                    "silence_periods": [],
                    "is_normalized": False,
                    "normalized_date": None,
                    "normalization_level": None,
                    "detection_method": "mdx",
                    "confidence": 0.90,
                },
                "SongB.txt": {
                    "status": "MISMATCH",
                    "original_gap": 2000,
                    "detected_gap": 3000,
                    "updated_gap": 0,
                    "diff": 1000,
                    "duration": 150000,
                    "notes_overlap": 0.7,
                    "processed_time": "2025-10-20 11:00:00",
                    "silence_periods": [],
                    "is_normalized": False,
                    "normalized_date": None,
                    "normalization_level": None,
                    "detection_method": "mdx",
                    "confidence": 0.85,
                },
            },
        }

        info_file.write_text(json.dumps(multi_data, indent=4), encoding="utf-8")

        # Load for SongC (not in entries, multiple entries exist, no default)
        gap_info_c = GapInfo(str(info_file), "SongC.txt")
        asyncio.run(GapInfoService.load(gap_info_c))

        # Should remain NOT_PROCESSED
        assert gap_info_c.status == GapInfoStatus.NOT_PROCESSED

    def test_save_converts_legacy_to_entries(self, tmp_path):
        """Saving to legacy file should convert it to multi-entry format"""
        info_file = tmp_path / "usdxfixgap.info"

        # Create legacy file
        legacy_data = {
            "status": "MATCH",
            "original_gap": 5000,
            "detected_gap": 5200,
            "updated_gap": 0,
            "diff": 200,
            "duration": 180000,
            "notes_overlap": 0.5,
            "processed_time": "2025-10-20 10:00:00",
            "silence_periods": [[0, 5200]],
            "is_normalized": False,
            "normalized_date": None,
            "normalization_level": None,
            "detection_method": "mdx",
            "confidence": 0.95,
        }

        info_file.write_text(json.dumps(legacy_data, indent=4), encoding="utf-8")

        # Create new gap info for SongA and save
        gap_info = GapInfo(str(info_file), "SongA.txt")
        gap_info.status = GapInfoStatus.MISMATCH
        gap_info.original_gap = 1000
        gap_info.detected_gap = 1500
        gap_info.diff = 500
        gap_info.duration = 120000
        gap_info.confidence = 0.88

        asyncio.run(GapInfoService.save(gap_info))

        # Read file and verify structure
        with open(info_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Should now have entries structure
        assert "entries" in data
        assert "version" in data
        assert data["version"] == 2

        # Should have default from legacy data
        assert "default" in data
        assert data["default"]["original_gap"] == 5000

        # Should have SongA entry with new data
        assert "SongA.txt" in data["entries"]
        assert data["entries"]["SongA.txt"]["original_gap"] == 1000
        assert data["entries"]["SongA.txt"]["detected_gap"] == 1500
        assert data["entries"]["SongA.txt"]["status"] == "MISMATCH"

    def test_save_updates_correct_entry(self, tmp_path):
        """Saving should update only the specific entry, preserving others"""
        info_file = tmp_path / "usdxfixgap.info"

        # Create multi-entry file
        multi_data = {
            "version": 2,
            "entries": {
                "SongA.txt": {
                    "status": "MATCH",
                    "original_gap": 1000,
                    "detected_gap": 1100,
                    "updated_gap": 0,
                    "diff": 100,
                    "duration": 120000,
                    "notes_overlap": 0.3,
                    "processed_time": "2025-10-20 10:00:00",
                    "silence_periods": [],
                    "is_normalized": False,
                    "normalized_date": None,
                    "normalization_level": None,
                    "detection_method": "mdx",
                    "confidence": 0.90,
                },
                "SongB.txt": {
                    "status": "MISMATCH",
                    "original_gap": 2000,
                    "detected_gap": 3000,
                    "updated_gap": 0,
                    "diff": 1000,
                    "duration": 150000,
                    "notes_overlap": 0.7,
                    "processed_time": "2025-10-20 11:00:00",
                    "silence_periods": [],
                    "is_normalized": False,
                    "normalized_date": None,
                    "normalization_level": None,
                    "detection_method": "mdx",
                    "confidence": 0.85,
                },
            },
        }

        info_file.write_text(json.dumps(multi_data, indent=4), encoding="utf-8")

        # Update SongB
        gap_info_b = GapInfo(str(info_file), "SongB.txt")
        gap_info_b.status = GapInfoStatus.UPDATED
        gap_info_b.original_gap = 2000
        gap_info_b.detected_gap = 3000
        gap_info_b.updated_gap = 2500
        gap_info_b.diff = 500

        asyncio.run(GapInfoService.save(gap_info_b))

        # Read file and verify
        with open(info_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        # SongA should be unchanged
        assert data["entries"]["SongA.txt"]["original_gap"] == 1000
        assert data["entries"]["SongA.txt"]["detected_gap"] == 1100
        assert data["entries"]["SongA.txt"]["status"] == "MATCH"

        # SongB should be updated
        assert data["entries"]["SongB.txt"]["status"] == "UPDATED"
        assert data["entries"]["SongB.txt"]["updated_gap"] == 2500
        assert data["entries"]["SongB.txt"]["diff"] == 500

    def test_save_creates_new_entry_in_multi_file(self, tmp_path):
        """Saving new song should add entry without affecting existing ones"""
        info_file = tmp_path / "usdxfixgap.info"

        # Create multi-entry file with one song
        multi_data = {
            "version": 2,
            "entries": {
                "SongA.txt": {
                    "status": "MATCH",
                    "original_gap": 1000,
                    "detected_gap": 1100,
                    "updated_gap": 0,
                    "diff": 100,
                    "duration": 120000,
                    "notes_overlap": 0.3,
                    "processed_time": "2025-10-20 10:00:00",
                    "silence_periods": [],
                    "is_normalized": False,
                    "normalized_date": None,
                    "normalization_level": None,
                    "detection_method": "mdx",
                    "confidence": 0.90,
                }
            },
        }

        info_file.write_text(json.dumps(multi_data, indent=4), encoding="utf-8")

        # Save new SongC
        gap_info_c = GapInfo(str(info_file), "SongC.txt")
        gap_info_c.status = GapInfoStatus.MATCH
        gap_info_c.original_gap = 3000
        gap_info_c.detected_gap = 3100
        gap_info_c.diff = 100
        gap_info_c.confidence = 0.92

        asyncio.run(GapInfoService.save(gap_info_c))

        # Read file and verify
        with open(info_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Should have both entries
        assert len(data["entries"]) == 2
        assert "SongA.txt" in data["entries"]
        assert "SongC.txt" in data["entries"]

        # SongA unchanged
        assert data["entries"]["SongA.txt"]["original_gap"] == 1000

        # SongC added
        assert data["entries"]["SongC.txt"]["original_gap"] == 3000
        assert data["entries"]["SongC.txt"]["detected_gap"] == 3100

    def test_load_nonexistent_file(self, tmp_path):
        """Loading from nonexistent file should return unmodified GapInfo"""
        info_file = tmp_path / "nonexistent.info"

        gap_info = GapInfo(str(info_file), "Song.txt")
        asyncio.run(GapInfoService.load(gap_info))

        # Should remain at default values
        assert gap_info.status == GapInfoStatus.NOT_PROCESSED
        assert gap_info.original_gap == 0
        assert gap_info.detected_gap == 0

    def test_save_empty_txt_basename_fails(self, tmp_path):
        """Saving without txt_basename should fail gracefully"""
        info_file = tmp_path / "usdxfixgap.info"

        gap_info = GapInfo(str(info_file), "")  # Empty txt_basename
        gap_info.status = GapInfoStatus.MATCH
        gap_info.original_gap = 1000

        result = asyncio.run(GapInfoService.save(gap_info))

        # Should return False indicating failure
        assert result is False

    def test_load_malformed_json(self, tmp_path):
        """Loading malformed JSON should handle gracefully"""
        info_file = tmp_path / "usdxfixgap.info"
        info_file.write_text("{ this is not valid json", encoding="utf-8")

        gap_info = GapInfo(str(info_file), "Song.txt")
        asyncio.run(GapInfoService.load(gap_info))

        # Should remain at default values
        assert gap_info.status == GapInfoStatus.NOT_PROCESSED
