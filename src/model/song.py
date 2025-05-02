from enum import Enum
import os
from model.gap_info import GapInfo, GapInfoStatus
import utils.files as files
import utils.audio as audio
from utils.usdx_file import USDXFile
from model.song_cache import SongCache
import logging

logger = logging.getLogger(__name__)

class SongStatus(Enum):
    NOT_PROCESSED = 'NOT_PROCESSED'
    QUEUED = 'QUEUED'
    PROCESSING = 'PROCESSING'
    SOLVED = 'SOLVED'
    UPDATED = 'UPDATED'
    MATCH = 'MATCH'
    MISMATCH = 'MISMATCH'
    ERROR = 'ERROR'

class Song:

    txt_file: str = ""

    path: str = ""
    relative_path: str = ""
    tmp_path: str = ""
    audio_file: str = ""
    
    title: str = ""
    artist: str = ""
    audio: str = "" 
    gap: int = 0
    bpm: int = 0
    start: int = 0
    is_relative: bool = False

    usdb_id: str = None
    
    duration_ms: int = 0

    audio_waveform_file: str = ""
    vocals_file: str = ""
    vocals_waveform_file: str = ""
    vocals_duration_ms: int = 0

    gap_info: GapInfo = None
    
    status: SongStatus = SongStatus.NOT_PROCESSED

    error_message: str = ""

    def __init__(self, txt_file: str, songs_root:str, tmp_root: str):
        self.txt_file = txt_file
        self.tmp_root = tmp_root
        self.path = os.path.dirname(txt_file)
        self.relative_path = os.path.relpath(self.path, songs_root)
        self._usdx_file = None  # Initialize as None for lazy loading
        self.gap_info = GapInfo(self.path)

    @property
    def usdx_file(self):
        """Lazy load the USDX file on first access"""
        if self._usdx_file is None:
            self._usdx_file = USDXFile(self.txt_file)
            # Don't run async load in the property - this could cause deadlocks
            # The caller should ensure usdx_file is loaded before accessing properties
        return self._usdx_file
    
    @property
    def notes(self):
        """Get notes from usdx_file"""
        if self._usdx_file is None:
            return []  # Return empty list if usdx_file not loaded yet
        return self._usdx_file.notes
    
    async def ensure_usdx_loaded(self):
        """Ensure the USDX file is loaded. Returns True on success, False on failure."""
        try:
            if self._usdx_file is None:
                logger.debug(f"Creating USDXFile instance for {self.txt_file}")
                self._usdx_file = USDXFile(self.txt_file)

            if not getattr(self._usdx_file, '_loaded', False):
                logger.debug(f"Calling _usdx_file.load() for {self.txt_file}")
                await self._usdx_file.load()
                # Verify loading succeeded
                if not getattr(self._usdx_file, '_loaded', False):
                    logger.error(f"USDX file load() completed but _loaded flag is still False for {self.txt_file}")
                    return False
                logger.debug(f"USDX file loaded successfully for {self.txt_file}")
            else:
                logger.debug(f"USDX file already loaded for {self.txt_file}")
            return True
        except Exception as e:
            logger.error(f"Exception during ensure_usdx_loaded for {self.txt_file}: {e}", exc_info=True)
            # Ensure _usdx_file exists even on error, but mark as not loaded
            if self._usdx_file:
                 setattr(self._usdx_file, '_loaded', False)
            return False
    
    async def load(self, force_reload=False):
        """
        Load the song data from the file.
        
        Args:
            force_reload (bool): If True, force reload even if cached
        """
        logger.debug(f"Starting load for {self.txt_file}, force_reload={force_reload}")
        # Clear _usdx_file if forcing reload
        if force_reload and self._usdx_file is not None:
            logger.debug(f"Forcing reload, clearing _usdx_file for {self.txt_file}")
            self._usdx_file = None

        # Load gap_info first
        try:
            logger.debug(f"Loading gap_info for {self.txt_file}")
            await self.gap_info.load()
            logger.debug(f"Gap_info loaded for {self.txt_file}")
        except Exception as e:
            logger.error(f"Failed to load gap_info for {self.txt_file}: {e}", exc_info=True)
            # Decide if you want to proceed without gap_info or raise error
            # For now, let's log and continue, init might fail later if gap_info is crucial

        # Explicitly load the USDX file and wait for it
        logger.debug(f"Ensuring USDX file is loaded for {self.txt_file}")
        usdx_load_success = await self.ensure_usdx_loaded()

        if not usdx_load_success:
            # If ensure_usdx_loaded failed, raise the error here before calling init
            raise RuntimeError(f"Failed to ensure USDX file was loaded for {self.txt_file}")
        logger.debug(f"USDX file ensured loaded for {self.txt_file}")

        # Initialize the song data ONLY if USDX loading succeeded
        logger.debug(f"Calling init() for {self.txt_file}")
        self.init()
        logger.debug(f"Finished load() for {self.txt_file}")

    def init(self):
        logger.debug(f"Starting init() for {self.txt_file}")
        if not os.path.exists(self.txt_file):
           raise FileNotFoundError(f"File not found during init: {self.txt_file}")

        # Final check: This should always pass if load() worked correctly
        if not self._usdx_file or not getattr(self._usdx_file, '_loaded', False):
            # This indicates a logic error somewhere if reached
            logger.critical(f"CRITICAL: init() called but USDX file not loaded for {self.txt_file}")
            raise RuntimeError(f"Internal Error: init() called but USDX file not loaded for {self.txt_file}")

        # Access usdx_file properties
        logger.debug(f"Accessing USDX tags for {self.txt_file}")
        self.title = self.usdx_file.tags.TITLE
        self.artist = self.usdx_file.tags.ARTIST
        self.audio = self.usdx_file.tags.AUDIO
        self.gap = self.usdx_file.tags.GAP
        self.bpm = self.usdx_file.tags.BPM
        self.start = self.usdx_file.tags.START
        self.is_relative = self.usdx_file.tags.RELATIVE

        self.path = self.usdx_file.path
        self.audio_file = os.path.join(self.path, self.audio)

        # Check if audio file exists early
        if not os.path.exists(self.audio_file):
             logger.warning(f"Audio file not found for {self.txt_file}: {self.audio_file}")
             # Consider setting an error status or handling this case

        logger.debug(f"Setting up paths for {self.txt_file}")
        # Ensure tmp_root is available
        if not self.tmp_root:
             logger.warning(f"tmp_root not set during init for {self.txt_file}")
             # Handle case where tmp_root might be missing (e.g., if deserialized incorrectly)
             # For now, we'll let get_tmp_path potentially fail or use a default if implemented there
        tmp_path = files.get_tmp_path(self.tmp_root, self.audio_file)
        self.tmp_path = tmp_path
        self.vocals_file = files.get_vocals_path(tmp_path)
        self.audio_waveform_file = files.get_waveform_path(tmp_path, "audio")
        self.vocals_waveform_file = files.get_waveform_path(tmp_path, "vocals")

        # Ensure gap_info is available before accessing duration
        if self.gap_info:
            self.duration_ms = self.gap_info.duration
        else:
            logger.warning(f"gap_info not available during init for {self.txt_file}, duration_ms set to 0")
            self.duration_ms = 0 # Or handle appropriately

        logger.debug(f"Updating status from gap_info for {self.txt_file}")
        self.update_status_from_gap_info()

        # After initializing, update the cache
        logger.debug(f"Caching song data for {self.txt_file}")
        self._cache_song_data()
        logger.debug(f"Finished init() for {self.txt_file}")

    def _cache_song_data(self):
        """Cache the song data in the SQLite database"""
        try:
            cache = SongCache.get_instance()
            song_data = {
                'title': self.title,
                'artist': self.artist,
                'audio': self.audio,
                'gap': self.gap,
                'bpm': self.bpm,
                'start': self.start,
                'is_relative': self.is_relative,
                'usdb_id': self.usdb_id
            }
            cache.cache_song_data(self.txt_file, song_data)
        except Exception as e:
            logger.error(f"Error caching song data: {e}")

    def __str__(self):
        return f"Song {self.artist} - {self.title}"

    def __repr__(self):
        # This will be used when printing a list of Song objects
        return f"<Song: {self.artist} - {self.title}>"
    
    def delete(self):
        files.delete_folder(self.path)

    @property
    def duration_str(self):
        if(self.duration_ms):
            return audio.milliseconds_to_str(self.duration_ms)
        else:
            "N/A"
    
    @property
    def normalized_str(self):
        """Return a string representation of the normalization status with level"""
        if self.gap_info and self.gap_info.is_normalized:
            if self.gap_info.normalization_level is not None:
                return f"{self.gap_info.normalization_level:.1f} dB"
            return "YES"  # Fallback if level not available
        return "NO"
    
    def update_status_from_gap_info(self):
        info = self.gap_info
        if info.status == GapInfoStatus.MATCH:
            self.status = SongStatus.MATCH
        elif info.status == GapInfoStatus.MISMATCH:
            self.status = SongStatus.MISMATCH
        elif info.status == GapInfoStatus.ERROR:
            self.status = SongStatus.ERROR
        elif info.status == GapInfoStatus.UPDATED:
            self.status = SongStatus.UPDATED
        elif info.status == GapInfoStatus.SOLVED:
            self.status = SongStatus.SOLVED            
        else:
            self.status = SongStatus.NOT_PROCESSED

    def __getstate__(self):
        # Return a dictionary of attributes to serialize
        state = self.__dict__.copy()
        # Don't serialize _usdx_file, it will be loaded on demand
        state.pop('_usdx_file', None)
        return state

    def __setstate__(self, state):
        # Restore the object's state
        self.__dict__.update(state)
        # _usdx_file will be lazily loaded when needed
        self._usdx_file = None
