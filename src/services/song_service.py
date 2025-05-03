import os
import logging
import datetime
from model.song import Song, SongStatus
from model.gap_info import GapInfo
from model.usdx_file import USDXFile  # Changed import path
from utils import audio
import utils.files as files
from common.database import get_cache_entry, set_cache_entry, remove_cache_entry
from services.gap_info_service import GapInfoService
from services.usdx_file_service import USDXFileService
from typing import Callable, Optional

logger = logging.getLogger(__name__)

class SongService:
    """Service class for operations on Song objects"""
    
    def __init__(self, tmp_root: str):
        self.tmp_root = tmp_root
        self.gap_info_service = GapInfoService()
    
    async def load_song(self, txt_file: str, songs_root: str, force_reload=False, cancel_check: Optional[Callable] = None) -> Song:
        """Load a song from a text file, using cache if available"""
        logger.debug(f"Starting load for {txt_file}, force_reload={force_reload}")
        
        song = Song(txt_file, songs_root, self.tmp_root)
        
        # Check if file exists
        if not os.path.exists(txt_file):
            logger.error(f"File not found during load: {txt_file}")
            song.status = SongStatus.ERROR
            song.error_message = f"File not found: {txt_file}"
            return song
            
        # Check if we can use cache if not forcing reload
        if not force_reload:
            # Get file modification time
            mod_time = datetime.datetime.fromtimestamp(os.path.getmtime(txt_file))
            cached_song = get_cache_entry(txt_file, mod_time)
            
            if cached_song:
                logger.debug(f"Using cached version of song {txt_file}")
                
                # Backward compatibility: Ensure notes attribute exists
                if not hasattr(cached_song, 'notes'):
                    logger.debug(f"Adding missing notes attribute to cached song {txt_file}")
                    cached_song.notes = None
                
                # Load gap_info for the cached song
                try:
                    if cached_song.gap_info:
                        await GapInfoService.load(cached_song.gap_info)
                except Exception as e:
                    logger.error(f"Failed to load gap_info for cached {txt_file}: {e}", exc_info=True)
                
                # If the notes attribute exists but is None, let's try to load the notes
                if cached_song.notes is None:
                    try:
                        logger.debug(f"Loading notes for cached song {txt_file}")
                        usdx_file = USDXFile(cached_song.txt_file)
                        await USDXFileService.load(usdx_file)
                        cached_song.notes = usdx_file.notes
                    except Exception as e:
                        logger.error(f"Error loading notes for cached song {txt_file}: {e}", exc_info=True)
                
                return cached_song
        
        logger.debug(f"Loading song {txt_file} from disk and updating cache")
        
        # Initialize gap_info
        song.gap_info = GapInfoService.create_for_song_path(song.path)
        
        # Load gap_info
        try:
            logger.debug(f"Loading gap_info for {txt_file}")
            if song.gap_info:
                await GapInfoService.load(song.gap_info)
                logger.debug(f"Gap_info loaded for {txt_file}")
        except Exception as e:
            logger.error(f"Failed to load gap_info for {txt_file}: {e}", exc_info=True)
            song.status = SongStatus.ERROR
            song.error_message = str(e)
            return song
            
        # Load USDX file
        try:
            usdx_file = USDXFile(txt_file)
            await USDXFileService.load(usdx_file)
            await self._initialize_song_from_usdx(song, usdx_file)
            
            # Update the cache
            self.update_cache(song)
        except FileNotFoundError as e:
            logger.error(f"File not found during load: {txt_file}")
            song.status = SongStatus.ERROR
            song.error_message = str(e)
        except Exception as e:
            logger.error(f"Error loading song {txt_file}: {e}", exc_info=True)
            song.status = SongStatus.ERROR
            song.error_message = str(e)
        
        # Check if duration needs to be determined from audio file
        if not song.duration_ms and song.audio_file and os.path.exists(song.audio_file):
            song.duration_ms = audio.get_audio_duration(song.audio_file, cancel_check)
            
        return song
    
    async def _initialize_song_from_usdx(self, song: Song, usdx_file: USDXFile):
        """Initialize song data from a USDX file"""
        if not os.path.exists(song.txt_file):
           raise FileNotFoundError(f"File not found: {song.txt_file}")
        
        # Access usdx_file properties
        logger.debug(f"Accessing USDX tags for {song.txt_file}")
        song.title = usdx_file.tags.TITLE
        song.artist = usdx_file.tags.ARTIST
        song.audio = usdx_file.tags.AUDIO
        song.gap = usdx_file.tags.GAP
        song.bpm = usdx_file.tags.BPM
        song.start = usdx_file.tags.START
        song.is_relative = usdx_file.tags.RELATIVE
        
        # Set the notes from the USDX file
        song.notes = usdx_file.notes

        song.path = usdx_file.path
        song.audio_file = os.path.join(song.path, song.audio)

        # Check if audio file exists
        if not os.path.exists(song.audio_file):
            logger.warning(f"Audio file not found for {song.txt_file}: {song.audio_file}")

        logger.debug(f"Setting up paths for {song.txt_file}")
        # Ensure tmp_root is available
        if not song.tmp_root:
            logger.warning(f"tmp_root not set for {song.txt_file}")
            
        tmp_path = files.get_tmp_path(song.tmp_root, song.audio_file)
        song.tmp_path = tmp_path
        song.vocals_file = files.get_vocals_path(tmp_path)
        song.audio_waveform_file = files.get_waveform_path(tmp_path, "audio")
        song.vocals_waveform_file = files.get_waveform_path(tmp_path, "vocals")

        # Set duration from gap_info
        if song.gap_info:
            song.duration_ms = song.gap_info.duration
        else:
            logger.warning(f"gap_info not available for {song.txt_file}, duration_ms set to 0")
            song.duration_ms = 0

        logger.debug(f"Updating status from gap_info for {song.txt_file}")
        song.update_status_from_gap_info()
    
    def get_notes(self, song: Song):
        """Get notes for a song from its USDX file"""
        try:
            usdx_file = USDXFile(song.txt_file)
            # Using the service to load notes only
            return USDXFileService.load_notes_only(usdx_file)
        except Exception as e:
            logger.error(f"Error getting notes for {song.txt_file}: {e}", exc_info=True)
            return []
    
    def delete_song(self, song: Song):
        """Delete the song folder and remove from cache"""
        try:
            # Remove from cache first
            remove_cache_entry(song.txt_file)
            
            # Then delete physical files
            files.delete_folder(song.path)
            return True
        except Exception as e:
            logger.error(f"Error deleting song {song.path}: {e}", exc_info=True)
            return False
    
    def update_cache(self, song: Song):
        """Update the cache for a song"""
        try:
            if os.path.exists(song.txt_file):
                set_cache_entry(song.txt_file, song)
                logger.debug(f"Song cache updated: {song.txt_file}")
        except Exception as e:
            logger.error(f"Error updating cache for {song.txt_file}: {e}", exc_info=True)
    
    def update_song_status(self, song: Song):
        """Update song status from gap_info and update cache"""
        song.update_status_from_gap_info()
        self.update_cache(song)
        
    async def save_gap_info(self, song: Song):
        """Save the gap info for a song"""
        if song.gap_info:
            await GapInfoService.save(song.gap_info)
            self.update_cache(song)
    
    def normalize_audio(self, song: Song, normalization_level: float = None):
        """Mark a song as normalized and update its gap info"""
        if song.gap_info:
            GapInfoService.set_normalized(song.gap_info, normalization_level)
            self.update_cache(song)
