import sqlite3
import os
import pickle
import logging
import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Define the database path
DB_PATH = os.path.join(Path.home(), '.usdxfixgapgui', 'cache.db')
_db_initialized = False

def init_database():
    """Initialize the database if it doesn't exist."""
    global _db_initialized
    
    if _db_initialized:
        return
        
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create the cache table if it doesn't exist
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS cache (
        key TEXT PRIMARY KEY,
        data BLOB,
        timestamp DATETIME
    )
    ''')
    
    conn.commit()
    conn.close()
    _db_initialized = True
    logger.debug("Database initialized")

# Initialize the database when the module is loaded
init_database()

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
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('SELECT data, timestamp FROM cache WHERE key=?', (key,))
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
    Store an object in the cache.
    
    Args:
        key (str): The cache key (filepath)
        obj (object): The object to cache
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check if entry already exists to provide better logging
        cursor.execute('SELECT 1 FROM cache WHERE key=?', (key,))
        exists = cursor.fetchone() is not None
        
        data_blob = pickle.dumps(obj)
        timestamp = datetime.datetime.now().isoformat()
        
        cursor.execute(
            'INSERT OR REPLACE INTO cache (key, data, timestamp) VALUES (?, ?, ?)',
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
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        if key:
            cursor.execute('DELETE FROM cache WHERE key=?', (key,))
        else:
            cursor.execute('DELETE FROM cache')
        
        rows_affected = cursor.rowcount
        conn.commit()
        conn.close()
        logger.debug(f"Cleared {rows_affected} cache entries")
    except Exception as e:
        logger.error(f"Failed to clear cache: {e}")
