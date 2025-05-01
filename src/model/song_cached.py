import os
import datetime
import logging
from model.song import Song
from common.database import get_cache_entry, set_cache_entry

logger = logging.getLogger(__name__)

class SongCached(Song):
    """
    An extended version of Song that uses SQLite caching to improve performance.
    """
    
    async def load(self, force_reload=False):
        """
        Load the song data, using cache if available and not stale.
        
        Args:
            force_reload (bool): If True, bypass cache and reload from file
        """
        # Check if file exists
        if not os.path.exists(self.txt_file):
            raise FileNotFoundError(f"File {self.txt_file} does not exist")
        
        # Get file modification time
        mod_time = datetime.datetime.fromtimestamp(os.path.getmtime(self.txt_file))
        
        # Try to get cached content if not forcing reload
        cached_song = None if force_reload else get_cache_entry(self.txt_file, mod_time)
        
        if cached_song:
            logger.debug(f"Using cached version of song {self.txt_file}")
            
            # First load the core components that have their own caching
            await self.usdx_file.load()
            await self.gap_info.load()
            
            # Initialize the song data based on usdx_file
            self.init()
            
            # Now copy cached attributes that aren't derived from usdx_file
            for attr in ["status", "duration_ms", "vocals_duration_ms", "error_message", "usdb_id"]:
                if hasattr(cached_song, attr) and getattr(cached_song, attr) is not None:
                    setattr(self, attr, getattr(cached_song, attr))
            
            return
        
        # If cache miss or stale cache, load normally
        logger.debug(f"Loading song {self.txt_file} from disk and updating cache")
        await super().load()
        
        # Update the cache
        set_cache_entry(self.txt_file, self)
    
    def update_status_from_gap_info(self):
        """
        Update the status based on gap info and update the cache.
        """
        # Update normally
        super().update_status_from_gap_info()
        
        # Update the cache - only if the file exists (to prevent errors during deletion)
        if os.path.exists(self.txt_file):
            set_cache_entry(self.txt_file, self)
            logger.debug(f"Song status updated and cache updated: {self.txt_file}")
