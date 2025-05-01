import os
import sys
from model.song_cache import SongCache
import logging

logger = logging.getLogger(__name__)

def initialize_song_cache():
    """Initialize the song cache database"""
    # Use get_app_dir function similar to the one in usdxfixgap.py
    def get_app_dir():
        if hasattr(sys, '_MEIPASS'):
            # Running in PyInstaller bundle
            return os.path.dirname(sys.executable)
        # Running as script
        return os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    
    # Define the database file location
    app_data_dir = os.path.join(get_app_dir(), 'data')
    os.makedirs(app_data_dir, exist_ok=True)
    db_path = os.path.join(app_data_dir, 'song_cache.db')
    
    # Initialize the SongCache
    SongCache.initialize(db_path)
    logger.info(f"Song cache database initialized at: {db_path}")
    return db_path

# Call this early in your application startup
db_path = initialize_song_cache()
print(f"Song cache database initialized at: {db_path}")
