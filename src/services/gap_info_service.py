import os
import json
import logging
import aiofiles
from datetime import datetime
from typing import Optional
from model.gap_info import GapInfo, GapInfoStatus
from utils import audio, files

logger = logging.getLogger(__name__)

class GapInfoService:
    """Service class for operations on GapInfo objects"""
    
    @staticmethod
    async def load(gap_info: GapInfo) -> GapInfo:
        """Load gap info from file"""
        logger.debug(f"Loading gap info from {gap_info.file_path}")
        
        if not gap_info.file_path or not os.path.exists(gap_info.file_path):
            logger.debug(f"Gap info file does not exist: {gap_info.file_path}")
            return gap_info
        
        try:
            async with aiofiles.open(gap_info.file_path, "r", encoding="utf-8") as file:
                content = await file.read()
                data = json.loads(content)
            
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

        except Exception as e:
            logger.error(f"Error loading gap info: {e}")
        
        return gap_info
    
    @staticmethod
    async def save(gap_info: GapInfo) -> bool:
        """Save gap info to file"""
        logger.debug(f"Saving gap info to {gap_info.file_path}")
        
        if not gap_info.file_path:
            logger.error("Cannot save gap info: file path is not set")
            return False
        
        try:
            # Update processed time
            gap_info.processed_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Prepare data for serialization
            data = {
                "status": gap_info.status.value,
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
                "normalization_level": gap_info.normalization_level
            }
            
            # Save to file
            os.makedirs(os.path.dirname(gap_info.file_path), exist_ok=True)
            async with aiofiles.open(gap_info.file_path, "w", encoding="utf-8") as file:
                await file.write(json.dumps(data, indent=4))
            
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
            'NOT_PROCESSED': GapInfoStatus.NOT_PROCESSED,
            'MATCH': GapInfoStatus.MATCH,
            'MISMATCH': GapInfoStatus.MISMATCH,
            'ERROR': GapInfoStatus.ERROR,
            'UPDATED': GapInfoStatus.UPDATED,
            'SOLVED': GapInfoStatus.SOLVED,
        }
        return status_map.get(status_string, GapInfoStatus.NOT_PROCESSED)
    
    @staticmethod
    def create_for_song_path(song_path: str) -> GapInfo:
        """Create a new GapInfo instance for the given song path"""
        file_path = files.get_info_file_path(song_path)
        return GapInfo(file_path)
