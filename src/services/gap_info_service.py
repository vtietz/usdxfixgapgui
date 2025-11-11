import os
import json
import logging
import aiofiles
from datetime import datetime
from typing import Optional
from model.gap_info import GapInfo, GapInfoStatus
from utils import files

logger = logging.getLogger(__name__)


class GapInfoService:
    """Service class for operations on GapInfo objects"""

    @staticmethod
    async def load(gap_info: GapInfo) -> GapInfo:
        """
        Load gap info from file with multi-entry support.

        Supports both legacy (single entry) and new (multi-entry) formats:
        - Legacy: entire JSON is one gap info entry
        - New: {"entries": {"SongA.txt": {...}, "SongB.txt": {...}}, "default": {...}, "version": 2}

        For multi-entry files:
        - Try to load entry matching gap_info.txt_basename
        - Fall back to "default" if present
        - Fall back to single entry if only one exists
        - Otherwise mark as NOT_PROCESSED
        """
        logger.debug(f"Loading gap info from {gap_info.file_path} for {gap_info.txt_basename}")

        if not gap_info.file_path or not os.path.exists(gap_info.file_path):
            logger.debug(f"Gap info file does not exist: {gap_info.file_path}")
            return gap_info

        try:
            async with aiofiles.open(gap_info.file_path, "r", encoding="utf-8") as file:
                content = await file.read()
                data = json.loads(content)

            # Check if this is a multi-entry file
            entry_data = None
            if "entries" in data:
                # New multi-entry format
                entries = data["entries"]

                # Try exact match first
                if gap_info.txt_basename and gap_info.txt_basename in entries:
                    entry_data = entries[gap_info.txt_basename]
                    logger.debug(f"Loaded entry for {gap_info.txt_basename}")
                # Fall back to default
                elif "default" in data:
                    entry_data = data["default"]
                    logger.debug(f"Using default entry for {gap_info.txt_basename}")
                # Fall back to single entry if only one exists
                elif len(entries) == 1:
                    entry_data = list(entries.values())[0]
                    logger.debug(f"Using single entry fallback for {gap_info.txt_basename}")
                else:
                    logger.warning(
                        f"No matching entry for {gap_info.txt_basename} in multi-entry file. "
                        f"Available: {list(entries.keys())}. Marking as NOT_PROCESSED."
                    )
                    return gap_info
            else:
                # Legacy single-entry format
                entry_data = data
                logger.debug("Loaded legacy single-entry format")

            # Populate gap_info from entry_data
            if entry_data:
                GapInfoService._populate_from_dict(gap_info, entry_data)

        except Exception as e:
            logger.error(f"Error loading gap info: {e}")

        return gap_info

    @staticmethod
    def _populate_from_dict(gap_info: GapInfo, data: dict):
        """Populate GapInfo fields from dictionary"""
        # Map the status string to enum
        status_str = data.get("status", "NOT_PROCESSED")
        gap_info.status = GapInfoService.map_string_to_status(status_str)

        # Load all properties
        gap_info.original_gap = data.get("original_gap", 0)
        gap_info.detected_gap = data.get("detected_gap", 0)
        gap_info.updated_gap = data.get("updated_gap", 0)
        gap_info.diff = data.get("diff", 0)
        gap_info.duration = data.get("duration", 0)
        gap_info.notes_overlap = data.get("notes_overlap", 0)
        gap_info.processed_time = data.get("processed_time", "")
        gap_info.silence_periods = data.get("silence_periods", [])
        gap_info.is_normalized = data.get("is_normalized", False)
        gap_info.normalized_date = data.get("normalized_date", None)
        gap_info.normalization_level = data.get("normalization_level", None)

        # Load new detection metadata fields (backward compatible)
        gap_info.detection_method = data.get("detection_method", "mdx")
        gap_info.preview_wav_path = data.get("preview_wav_path", None)
        gap_info.waveform_json_path = data.get("waveform_json_path", None)
        gap_info.confidence = data.get("confidence", None)
        gap_info.detected_gap_ms = data.get("detected_gap_ms", None)
        gap_info.first_note_ms = data.get("first_note_ms", None)
        gap_info.tolerance_band_ms = data.get("tolerance_band_ms", None)

    @staticmethod
    async def save(gap_info: GapInfo) -> bool:
        """
        Save gap info to file with multi-entry support.

        Uses read-modify-write to update the specific entry for this song:
        - Reads existing file if present
        - Converts legacy format to multi-entry on first save
        - Updates entries[txt_basename] with new data
        - Preserves other entries
        """
        logger.debug(f"Saving gap info to {gap_info.file_path} for {gap_info.txt_basename}")

        if not gap_info.file_path:
            logger.error("Cannot save gap info: file path is not set")
            return False

        if not gap_info.txt_basename:
            logger.error("Cannot save gap info: txt_basename is not set")
            return False

        try:
            # Update processed time
            gap_info.processed_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Prepare entry data for this song
            # Ensure status is an enum (defensive coding)
            from model.gap_info import GapInfoStatus

            if isinstance(gap_info.status, str):
                try:
                    gap_info.status = GapInfoStatus[gap_info.status]
                except KeyError:
                    gap_info.status = GapInfoStatus.ERROR

            # Handle None status gracefully (can occur when detection fails)
            status_value = gap_info.status.value if gap_info.status else "ERROR"
            entry_data = {
                "status": status_value,
                "original_gap": gap_info.original_gap,
                "detected_gap": gap_info.detected_gap,
                "updated_gap": gap_info.updated_gap,
                "diff": gap_info.diff,
                "duration": gap_info.duration,
                "notes_overlap": gap_info.notes_overlap,
                "processed_time": gap_info.processed_time,
                "silence_periods": gap_info.silence_periods,
                "is_normalized": gap_info.is_normalized,
                "normalized_date": gap_info.normalized_date,
                "normalization_level": gap_info.normalization_level,
                # New detection metadata fields
                "detection_method": gap_info.detection_method,
                "preview_wav_path": gap_info.preview_wav_path,
                "waveform_json_path": gap_info.waveform_json_path,
                "confidence": gap_info.confidence,
                "detected_gap_ms": gap_info.detected_gap_ms,
                "first_note_ms": gap_info.first_note_ms,
                "tolerance_band_ms": gap_info.tolerance_band_ms,
            }

            # Read existing file (if any) to preserve other entries
            document = {"entries": {}, "version": 2}
            if os.path.exists(gap_info.file_path):
                try:
                    async with aiofiles.open(gap_info.file_path, "r", encoding="utf-8") as file:
                        content = await file.read()
                        existing_data = json.loads(content)

                    # Check format
                    if "entries" in existing_data:
                        # Already multi-entry format
                        document = existing_data
                    else:
                        # Legacy format - convert to multi-entry
                        logger.info(f"Converting legacy gap info file to multi-entry format: {gap_info.file_path}")
                        document = {"entries": {}, "default": existing_data, "version": 2}
                except json.JSONDecodeError as e:
                    logger.warning(f"Could not parse existing gap info file, will overwrite: {e}")
                except Exception as e:
                    logger.warning(f"Error reading existing gap info file, will overwrite: {e}")

            # Update the entry for this song
            document["entries"][gap_info.txt_basename] = entry_data

            # Save to file
            os.makedirs(os.path.dirname(gap_info.file_path), exist_ok=True)
            async with aiofiles.open(gap_info.file_path, "w", encoding="utf-8") as file:
                await file.write(json.dumps(document, indent=4))

            logger.debug(f"Successfully saved gap info for {gap_info.txt_basename}")
            return True
        except Exception as e:
            logger.error(f"Error saving gap info: {e}")
            return False

    @staticmethod
    def set_normalized(gap_info: GapInfo, level: Optional[float] = None) -> None:
        """Mark the audio as normalized with current timestamp and level"""
        gap_info.is_normalized = True
        gap_info.normalized_date = datetime.now().isoformat()
        gap_info.normalization_level = level

    @staticmethod
    def map_string_to_status(status_string: str) -> GapInfoStatus:
        """Map a string status to GapInfoStatus enum"""
        status_map = {
            "NOT_PROCESSED": GapInfoStatus.NOT_PROCESSED,
            "MATCH": GapInfoStatus.MATCH,
            "MISMATCH": GapInfoStatus.MISMATCH,
            "ERROR": GapInfoStatus.ERROR,
            "UPDATED": GapInfoStatus.UPDATED,
            "SOLVED": GapInfoStatus.SOLVED,
        }
        return status_map.get(status_string, GapInfoStatus.NOT_PROCESSED)

    @staticmethod
    def create_for_song_path(song_path: str, txt_basename: str = "") -> GapInfo:
        """
        Create a new GapInfo instance for the given song path.

        Args:
            song_path: Path to the song folder or txt file
            txt_basename: Basename of the txt file (e.g., "SongA.txt") for multi-entry support

        Returns:
            GapInfo instance with file_path set to folder-level usdxfixgap.info
        """
        file_path = files.get_info_file_path(song_path)
        return GapInfo(file_path, txt_basename)
