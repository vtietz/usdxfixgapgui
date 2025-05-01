import os
import datetime
import logging
from utils.usdx_file import USDXFile
from common.database import get_cache_entry, set_cache_entry

logger = logging.getLogger(__name__)

class USDXFileCached(USDXFile):
    """
    An extended version of USDXFile that uses SQLite caching to improve performance.
    """
    
    async def load(self):
        """
        Load the file content, using cache if available and not stale.
        """
        # Check if file exists
        if not os.path.exists(self.filepath):
            raise FileNotFoundError(f"File {self.filepath} does not exist")
        
        # Get file modification time
        mod_time = datetime.datetime.fromtimestamp(os.path.getmtime(self.filepath))
        
        # Try to get cached content
        cached_file = get_cache_entry(self.filepath, mod_time)
        
        if cached_file:
            logger.debug(f"Using cached version of {self.filepath}")
            # Copy the relevant attributes from the cached file
            self.encoding = cached_file.encoding
            self.content = cached_file.content
            self.tags = cached_file.tags
            self.notes = cached_file.notes
            self.path = cached_file.path
            return
        
        # If cache miss or stale cache, load normally
        logger.debug(f"Loading {self.filepath} from disk and updating cache")
        await super().load()
        
        # Update the cache
        set_cache_entry(self.filepath, self)
    
    async def save(self):
        """
        Save the file and update the cache.
        """
        # Save the file normally
        await super().save()
        
        # Update the cache
        set_cache_entry(self.filepath, self)
        
        logger.debug(f"File saved and cache updated: {self.filepath}")
