import sqlite3
import os
import pickle
import logging
import datetime
from pathlib import Path

from utils.files import get_app_dir

logger = logging.getLogger(__name__)

# Define the database path
DB_PATH = os.path.join(get_app_dir(), 'cache.db')
_db_initialized = False

def get_connection():
    """Get a connection to the database."""
    return sqlite3.connect(DB_PATH)

def init_database():
    """Initialize the database if it doesn't exist."""
    global _db_initialized
    
    if (_db_initialized):
        return
        
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Create the song cache table if it doesn't exist
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS song_cache (
        file_path TEXT PRIMARY KEY,
        song_data BLOB,
        timestamp DATETIME
    )
    ''')
    
    conn.commit()
    conn.close()
    _db_initialized = True
    logger.debug("Database initialized")

# Initialize the database when the module is loaded
init_database()

def initialize_song_cache():
    """Initialize the song cache database and return its path."""
    init_database()
    return DB_PATH

def get_cache_entry(key, modified_time=None):
    """
    Retrieve a cache entry by key.
    
    Args:
        key (str): The cache key (filepath)
        modified_time (datetime, optional): If provided, the cache will only be returned
                                           if it's newer than this datetime.
    
    Returns:
        object or None: The cached object if found and valid, None otherwise.
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT song_data, timestamp FROM song_cache WHERE file_path=?', (key,))
        result = cursor.fetchone()
        conn.close()
        
        if result is None:
            logger.debug(f"Cache miss: {key}")
            return None
        
        data_blob, timestamp_str = result
        cached_timestamp = datetime.datetime.fromisoformat(timestamp_str)
        
        # Check if cache is stale
        if modified_time and modified_time > cached_timestamp:
            logger.debug(f"Cache stale: {key}, file mod: {modified_time}, cache: {cached_timestamp}")
            return None
        
        try:
            obj = pickle.loads(data_blob)
            logger.debug(f"Cache hit: {key}")
            return obj
        except Exception as e:
            logger.error(f"Failed to deserialize cache for key {key}: {e}")
            return None
    except Exception as e:
        logger.error(f"Error retrieving from cache for key {key}: {e}")
        return None

def set_cache_entry(key, obj):
    """
    Store or update an object in the cache.
    
    Args:
        key (str): The cache key (filepath)
        obj (object): The object to cache
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Check if entry already exists to provide better logging
        cursor.execute('SELECT 1 FROM song_cache WHERE file_path=?', (key,))
        exists = cursor.fetchone() is not None
        
        data_blob = pickle.dumps(obj)
        timestamp = datetime.datetime.now().isoformat()
        
        # This will update existing entries or insert new ones
        cursor.execute(
            'INSERT OR REPLACE INTO song_cache (file_path, song_data, timestamp) VALUES (?, ?, ?)',
            (key, data_blob, timestamp)
        )
        conn.commit()
        conn.close()
        
        if exists:
            logger.debug(f"Cache updated: {key}")
        else:
            logger.debug(f"New cache entry created: {key}")
    except Exception as e:
        logger.error(f"Failed to cache data for key {key}: {e}")

def clear_cache(key=None):
    """
    Clear the cache.
    
    Args:
        key (str, optional): If provided, only clear this specific key.
                            If None, clear the entire cache.
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        if key:
            cursor.execute('DELETE FROM song_cache WHERE file_path=?', (key,))
        else:
            cursor.execute('DELETE FROM song_cache')
        
        rows_affected = cursor.rowcount
        conn.commit()
        conn.close()
        logger.debug(f"Cleared {rows_affected} cache entries")
    except Exception as e:
        logger.error(f"Failed to clear cache: {e}")

def get_all_cache_entries(deserialize=False):
    """
    Return all song entries from the cache database.
    
    Args:
        deserialize (bool): If True, deserialize the song objects before returning
    
    Returns:
        If deserialize=False: List of tuples containing (file_path, serialized_song_data)
        If deserialize=True: Dictionary mapping file_path to deserialized song objects
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT file_path, song_data, timestamp FROM song_cache")
        results = cursor.fetchall()
        conn.close()
        
        if not deserialize:
            # Return raw data (file_path, song_data) tuples
            return [(row[0], row[1]) for row in results]
        
        # Deserialize the song objects
        deserialized = {}
        for file_path, song_data, timestamp_str in results:
            if not os.path.exists(file_path):
                continue  # Skip files that no longer exist
                
            try:
                song_obj = pickle.loads(song_data)
                deserialized[file_path] = song_obj
            except Exception as e:
                logger.error(f"Failed to deserialize cache for {file_path}: {e}")
        
        return deserialized
    except Exception as e:
        logger.error(f"Error getting all cache entries: {str(e)}")
        return [] if not deserialize else {}

def remove_cache_entry(file_path):
    """
    Remove a cache entry for the given file path.
    
    Args:
        file_path (str): Path of the file to remove from cache
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM song_cache WHERE file_path = ?", (file_path,))
        conn.commit()
        conn.close()
        logger.debug(f"Removed cache entry for {file_path}")
    except Exception as e:
        logger.error(f"Error removing cache entry for {file_path}: {str(e)}")

def cleanup_stale_entries(valid_paths):
    """
    Remove cache entries for files that no longer exist.
    
    Args:
        valid_paths (set): Set of file paths that still exist
    
    Returns:
        int: Number of stale entries removed
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get all cached paths
        cursor.execute("SELECT file_path FROM song_cache")
        cached_paths = [row[0] for row in cursor.fetchall()]
        
        # Find paths that are in cache but not in valid_paths
        stale_paths = [path for path in cached_paths if path not in valid_paths]
        
        # Remove stale entries
        for path in stale_paths:
            cursor.execute("DELETE FROM song_cache WHERE file_path = ?", (path,))
        
        conn.commit()
        conn.close()
        
        if stale_paths:
            logger.info(f"Removed {len(stale_paths)} stale cache entries")
        
        return len(stale_paths)
    except Exception as e:
        logger.error(f"Error cleaning up stale cache entries: {str(e)}")
        return 0
