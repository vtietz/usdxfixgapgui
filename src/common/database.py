import sqlite3
import os
import pickle
import logging
import datetime
from typing import overload, Literal, Any

from utils.files import get_localappdata_dir

logger = logging.getLogger(__name__)

# Define the database path
DB_PATH = os.path.join(get_localappdata_dir(), "cache.db")
_db_initialized = False
_cache_was_cleared = False  # Track if cache was cleared due to version mismatch

# Cache schema version - increment when cache structure changes
# Version 1: Original cache (pre-multi-txt support)
# Version 2: Multi-txt support (txt_file path is primary key)
CACHE_VERSION = 2


def get_connection():
    """Get a connection to the database."""
    return sqlite3.connect(DB_PATH)


def init_database():
    """
    Initialize the database if it doesn't exist.

    Returns:
        bool: True if cache was cleared due to version upgrade, False otherwise
    """
    global _db_initialized, _cache_was_cleared

    if _db_initialized:
        return _cache_was_cleared

    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    conn = get_connection()
    cursor = conn.cursor()

    # Create the song cache table if it doesn't exist
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS song_cache (
        file_path TEXT PRIMARY KEY,
        song_data BLOB,
        timestamp DATETIME
    )
    """
    )

    # Create metadata table for cache versioning
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS cache_metadata (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """
    )

    # Check cache version
    cursor.execute("SELECT value FROM cache_metadata WHERE key=?", ("version",))
    result = cursor.fetchone()
    current_version = int(result[0]) if result else None  # None for fresh/legacy database

    # Only clear cache if upgrading from old version (not on fresh install)
    if current_version is not None and current_version < CACHE_VERSION:
        # Explicit version mismatch - needs migration
        logger.warning(f"Cache version mismatch detected (current: {current_version}, required: {CACHE_VERSION}).")
        logger.warning("A complete re-scan of all songs is required due to application upgrade.")
        logger.info("Clearing outdated cache...")
        cursor.execute("DELETE FROM song_cache")
        cursor.execute(
            "INSERT OR REPLACE INTO cache_metadata (key, value) VALUES (?, ?)", ("version", str(CACHE_VERSION))
        )
        logger.info(f"Cache cleared and version updated to v{CACHE_VERSION}")
        _cache_was_cleared = True
    elif current_version is None:
        # No version metadata - could be fresh or legacy
        # Check if there are any cache entries to determine if legacy
        cursor.execute("SELECT COUNT(*) FROM song_cache")
        cache_entry_count = cursor.fetchone()[0]

        if cache_entry_count > 0:
            # Legacy database with cache entries - needs migration
            logger.warning(f"Legacy cache detected (no version metadata, {cache_entry_count} entries).")
            logger.warning("A complete re-scan of all songs is required due to application upgrade.")
            logger.info("Clearing legacy cache...")
            cursor.execute("DELETE FROM song_cache")
            logger.info("Legacy cache cleared")
            _cache_was_cleared = True
        else:
            # Fresh database - just set version, no need to clear
            logger.debug("Fresh database detected, initializing with current version")
            _cache_was_cleared = False

        # Set version for both cases
        cursor.execute("INSERT INTO cache_metadata (key, value) VALUES (?, ?)", ("version", str(CACHE_VERSION)))

    conn.commit()
    conn.close()
    _db_initialized = True
    logger.debug("Database initialized")

    return _cache_was_cleared


# Initialize the database when the module is loaded
init_database()


def initialize_song_cache():
    """
    Initialize the song cache database and return its path.

    Returns:
        tuple: (db_path, cache_was_cleared) where cache_was_cleared indicates
               if a re-scan is required due to version upgrade
    """
    cache_cleared = init_database()
    return DB_PATH, cache_cleared


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

        cursor.execute("SELECT song_data, timestamp FROM song_cache WHERE file_path=?", (key,))
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
        cursor.execute("SELECT 1 FROM song_cache WHERE file_path=?", (key,))
        exists = cursor.fetchone() is not None

        data_blob = pickle.dumps(obj)
        timestamp = datetime.datetime.now().isoformat()

        # This will update existing entries or insert new ones
        cursor.execute(
            "INSERT OR REPLACE INTO song_cache (file_path, song_data, timestamp) VALUES (?, ?, ?)",
            (key, data_blob, timestamp),
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
            cursor.execute("DELETE FROM song_cache WHERE file_path=?", (key,))
        else:
            cursor.execute("DELETE FROM song_cache")

        rows_affected = cursor.rowcount
        conn.commit()
        conn.close()
        logger.debug(f"Cleared {rows_affected} cache entries")
    except Exception as e:
        logger.error(f"Failed to clear cache: {e}")


@overload
def get_all_cache_entries(deserialize: Literal[False] = False) -> list[tuple[str, bytes]]:
    ...


@overload
def get_all_cache_entries(deserialize: Literal[True]) -> dict[str, Any]:
    ...


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
