from datetime import datetime
from enum import Enum
from utils import audio, files
from enum import Enum
import json
import os
import aiofiles
import logging
from typing import List, Tuple, Optional

logger = logging.getLogger(__name__)

class GapInfoStatus(Enum):
    NOT_PROCESSED = 'NOT_PROCESSED'
    MATCH = 'MATCH'
    MISMATCH = 'MISMATCH'
    SOLVED = 'SOLVED'
    UPDATED = 'UPDATED'
    ERROR = 'ERROR'

class GapInfo:
    """Data class for song gap analysis information"""

    def __init__(self, file_path: str = ""):
        # File path where the gap info will be stored
        self.file_path = file_path
        
        # Status and gap information
        self._status = GapInfoStatus.NOT_PROCESSED
        self.original_gap = 0
        self.detected_gap = 0
        self.updated_gap = 0
        self.diff = 0
        
        # Audio information
        self.duration = 0
        self.notes_overlap = 0
        
        # Metadata
        self.processed_time = ""
        self.silence_periods: List[Tuple[float, float]] = []
        
        # Normalization data
        self.is_normalized = False
        self.normalized_date: Optional[str] = None
        self.normalization_level: Optional[float] = None
        
        # Reference to owner song
        self.owner = None
    
    @property
    def status(self):
        return self._status
        
    @status.setter
    def status(self, value):
        self._status = value
        # Update owner's status when this status changes
        if hasattr(self, 'owner') and self.owner is not None:
            self.owner._gap_info_updated()
    
    def set_normalized(self):
        """Mark the audio as normalized with current timestamp"""
        self.is_normalized = True
        self.normalized_date = datetime.now().isoformat()
        
    async def save(self):
        """For backward compatibility - delegates to GapInfoService"""
        from services.gap_info_service import GapInfoService
        return await GapInfoService.save(self)
    
    def __str__(self):
        return f"GapInfo({self.status.value}, orig={self.original_gap}, det={self.detected_gap})"

