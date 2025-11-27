"""SQLite-backed song cache management.

This module centralizes cache responsibilities:

- Handles per-entry schema envelopes/migrations so cached songs survive refactors
- Provides CRUD helpers used by services/workers (get/set/stream/remove)
- Manages the cache database initialization and metadata versioning

Callers should import the public helpers only; internal migration helpers remain private.
"""

import sqlite3
import os
import logging
import datetime
import time
from typing import overload, Literal, Any

from utils.files import get_localappdata_dir
from common.cache_schema import CacheEnvelope, serialize_payload, deserialize_payload

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration & constants
# ---------------------------------------------------------------------------


def normalize_cache_key(file_path: str) -> str:
    """
    Normalize a file path for use as a cache key.
    Converts all backslashes to forward slashes for consistent comparison.

    Args:
        file_path: Raw file path with potentially mixed separators

    Returns:
        Normalized path with forward slashes only

    Example:
        'Z:/Songs\\ABBA\\song.txt' -> 'Z:/Songs/ABBA/song.txt'
    """
    return file_path.replace('\\', '/')


# Define the database path (lazy initialization to avoid import-time side effects)
_DB_PATH: str | None = None
_db_initialized = False
_cache_was_cleared = False  # Track if cache was cleared due to version mismatch


def _ensure_initialized() -> None:
    """Initialize the cache database on first use."""

    if not _db_initialized:
        init_database()


def _persist_cache_payload(
    key: str,
    payload: Any,
    timestamp_override: str | None = None,
    *,
    key_is_normalized: bool = False,
) -> None:
    """Write the provided payload into the cache using the envelope wrapper."""

    normalized_key = key if key_is_normalized else normalize_cache_key(key).lower()
    data_blob = serialize_payload(payload)
    timestamp_value = timestamp_override or datetime.datetime.now().isoformat()

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO song_cache (file_path, song_data, timestamp) VALUES (?, ?, ?)",
        (normalized_key, data_blob, timestamp_value),
    )
    conn.commit()
    conn.close()


def deserialize_cache_blob(
    file_path: str,
    data_blob: bytes,
    timestamp_str: str | None = None,
    *,
    key_is_normalized: bool = False,
):
    """Public helper for callers that need to deserialize cache rows on the fly."""

    normalized_key = file_path if key_is_normalized else normalize_cache_key(file_path).lower()
    payload, migrated = deserialize_payload(normalized_key, data_blob)
    if payload is None:
        return None

    if migrated:
        _persist_cache_payload(normalized_key, payload, timestamp_override=timestamp_str, key_is_normalized=True)

    return payload


def _get_db_path() -> str:
    """Get database path, initializing it on first access."""
    global _DB_PATH
    if _DB_PATH is None:
        _DB_PATH = os.path.join(get_localappdata_dir(), "cache.db")
    return _DB_PATH


# Cache schema version - increment when cache structure changes
# Version 1: Original cache (pre-multi-txt support)
# Version 2: Multi-txt support (txt_file path is primary key)
CACHE_VERSION = 2
# Versions that absolutely require a destructive reset (reserved for structural DB changes)
CACHE_VERSIONS_REQUIRING_CLEAR: set[int] = set()


def get_connection():
    """Get a connection to the database with optimized settings."""
    conn = sqlite3.connect(_get_db_path())
    cursor = conn.cursor()
    # Performance optimizations for read-heavy workloads
    cursor.execute("PRAGMA journal_mode=WAL")  # Write-ahead logging for better concurrency
    cursor.execute("PRAGMA synchronous=NORMAL")  # Balance safety and speed
    cursor.execute("PRAGMA temp_store=MEMORY")  # Use memory for temp tables
    cursor.execute("PRAGMA cache_size=-32768")  # ~32 MB page cache
    return conn


# ---------------------------------------------------------------------------
# Maintenance & migrations
# ---------------------------------------------------------------------------


def migrate_cache_paths():
    """
    One-time migration to normalize all file_path entries in the cache.
    Converts backslashes to forward slashes and removes duplicates.

    This fixes the issue where the same song was cached with both
    Z:/Songs/Artist/song.txt and Z:/Songs\\Artist\\song.txt paths.

    Returns:
        int: Number of duplicate entries removed
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get all cache entries
        cursor.execute("SELECT file_path, song_data, timestamp FROM song_cache")
        all_entries = cursor.fetchall()

        if not all_entries:
            conn.close()
            return 0

        # Track normalized paths to detect duplicates
        normalized_map = {}  # normalized_path -> (song_data, timestamp, original_path)
        duplicates_removed = 0

        for file_path, song_data, timestamp in all_entries:
            normalized_path = normalize_cache_key(file_path).lower()

            # If normalized path already exists, keep the newer entry
            if normalized_path in normalized_map:
                duplicates_removed += 1
                existing_timestamp = normalized_map[normalized_path][1]
                # Keep the newer timestamp
                if timestamp > existing_timestamp:
                    normalized_map[normalized_path] = (song_data, timestamp, file_path)
            else:
                normalized_map[normalized_path] = (song_data, timestamp, file_path)

        if duplicates_removed > 0:
            logger.info(
                "Found %s duplicate cache entries with different path separators",
                duplicates_removed,
            )

            # Clear the entire cache table
            cursor.execute("DELETE FROM song_cache")

            # Re-insert with normalized paths
            for normalized_path, (song_data, timestamp, _) in normalized_map.items():
                cursor.execute(
                    "INSERT INTO song_cache (file_path, song_data, timestamp) VALUES (?, ?, ?)",
                    (normalized_path, song_data, timestamp)
                )

            conn.commit()
            logger.info(
                "Cache normalized: removed %s duplicates, kept %s unique songs",
                duplicates_removed,
                len(normalized_map),
            )

        conn.close()
        return duplicates_removed
    except Exception as e:
        logger.error("Error migrating cache paths: %s", str(e))
        return 0


    # ---------------------------------------------------------------------------
    # Initialization
    # ---------------------------------------------------------------------------


def init_database():
    """
    Initialize the database if it doesn't exist.

    Returns:
        bool: True if cache was cleared due to version upgrade, False otherwise
    """
    global _db_initialized, _cache_was_cleared

    if _db_initialized:
        return _cache_was_cleared

    os.makedirs(os.path.dirname(_get_db_path()), exist_ok=True)

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

    # Create index on file_path for fast prefix filtering
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_song_cache_file_path ON song_cache(file_path)"
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
        logger.warning(
            "Cache version mismatch detected (current: %s, required: %s).",
            current_version,
            CACHE_VERSION,
        )
        if current_version in CACHE_VERSIONS_REQUIRING_CLEAR:
            logger.warning("This upgrade requires clearing the cache due to structural changes.")
            cursor.execute("DELETE FROM song_cache")
            _cache_was_cleared = True
            logger.info("Cache cleared as part of version upgrade")
        else:
            logger.info("Preserving existing cache entries for lazy envelope migration")
            _cache_was_cleared = False

        cursor.execute(
            "INSERT OR REPLACE INTO cache_metadata (key, value) VALUES (?, ?)", ("version", str(CACHE_VERSION))
        )
        if _cache_was_cleared:
            logger.info("Cache version updated to v%s (entries cleared)", CACHE_VERSION)
        else:
            logger.info("Cache version metadata updated to v%s (entries preserved)", CACHE_VERSION)
    elif current_version is None:
        # No version metadata - could be fresh or legacy
        # Check if there are any cache entries to determine if legacy
        cursor.execute("SELECT COUNT(*) FROM song_cache")
        cache_entry_count = cursor.fetchone()[0]

        if cache_entry_count > 0:
            logger.warning(
                "Legacy cache detected (no version metadata, %s entries).",
                cache_entry_count,
            )
            logger.info("Preserving legacy cache entries and marking them for lazy migration")
            _cache_was_cleared = False
        else:
            # Fresh database - just set version, no need to clear
            logger.debug("Fresh database detected, initializing with current version")
            _cache_was_cleared = False

        # Set version for both cases
        cursor.execute(
            "INSERT OR REPLACE INTO cache_metadata (key, value) VALUES (?, ?)", ("version", str(CACHE_VERSION))
        )

    conn.commit()
    conn.close()
    _db_initialized = True
    logger.debug("Database initialized")

    # Run path normalization migration (one-time cleanup of duplicates)
    # This is safe to run multiple times - only processes duplicates
    if not _cache_was_cleared:  # Only migrate if we didn't just clear the cache
        migrate_cache_paths()

    return _cache_was_cleared


# ---------------------------------------------------------------------------
# Public API (CRUD helpers)
# ---------------------------------------------------------------------------


def initialize_song_cache():
    """
    Initialize the song cache database and return its path.

    Returns:
        tuple: (db_path, cache_was_cleared) where cache_was_cleared indicates
               if a re-scan is required due to version upgrade
    """
    cache_cleared = init_database()
    return _get_db_path(), cache_cleared


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
    _ensure_initialized()
    key = normalize_cache_key(key).lower()  # Normalize path separators and lowercase
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT song_data, timestamp FROM song_cache WHERE file_path=?", (key,))
        result = cursor.fetchone()
        conn.close()

        if result is None:
            return None

        data_blob, timestamp_str = result
        cached_timestamp = datetime.datetime.fromisoformat(timestamp_str)

        # Check if cache is stale
        if modified_time and modified_time > cached_timestamp:
            return None

        payload = deserialize_cache_blob(key, data_blob, timestamp_str, key_is_normalized=True)
        return payload
    except Exception as e:
        logger.error("Error retrieving from cache for key %s: %s", key, e)
        return None


def set_cache_entry(key, obj):
    """
    Store or update an object in the cache.

    Args:
        key (str): The cache key (filepath)
        obj (object): The object to cache
    """
    _ensure_initialized()
    key = normalize_cache_key(key).lower()  # Normalize path separators and lowercase for indexing
    start_time = time.perf_counter()

    try:
        _persist_cache_payload(key, obj)

        duration_ms = (time.perf_counter() - start_time) * 1000
        if duration_ms > 100:
            logger.warning("SLOW cache operation: %.1fms for %s", duration_ms, key)
    except Exception as e:
        logger.error("Failed to cache data for key %s: %s", key, e)


def clear_cache(key=None):
    """
    Clear the cache.

    Args:
        key (str, optional): If provided, only clear this specific key.
                            If None, clear the entire cache.
    """
    _ensure_initialized()
    if key:
        key = normalize_cache_key(key)  # Normalize path separators
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
        if rows_affected > 0:
            logger.info("Cleared %s cache entries", rows_affected)
    except Exception as e:
        logger.error("Failed to clear cache: %s", e)


@overload
def get_all_cache_entries(deserialize: Literal[False] = False) -> list[tuple[str, bytes]]: ...


@overload
def get_all_cache_entries(deserialize: Literal[True]) -> dict[str, Any]: ...


def get_all_cache_entries(deserialize=False):
    """
    Return all song entries from the cache database.

    Args:
        deserialize (bool): If True, deserialize the song objects before returning

    Returns:
        If deserialize=False: List of tuples containing (file_path, serialized_song_data)
        If deserialize=True: Dictionary mapping file_path to deserialized song objects
    """
    _ensure_initialized()
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
        # NOTE: os.path.exists() check removed for performance - defer to caller
        # For 5000 songs, checking file existence for each adds 2-5 seconds delay
        # The existence check will happen during directory scan anyway
        deserialized = {}
        for file_path, song_data, timestamp_str in results:
            song_obj = deserialize_cache_blob(file_path, song_data, timestamp_str)
            if song_obj is not None:
                deserialized[file_path] = song_obj

        return deserialized
    except Exception as e:
        logger.error("Error getting all cache entries: %s", str(e))
        return [] if not deserialize else {}


def stream_cache_entries(page_size=500, directory_filter=None):
    """
    Stream cache entries in pages for progressive loading.
    Yields tuples of (file_path, song_data, timestamp) for memory efficiency.

    Args:
        page_size: Number of rows to fetch per iteration (default 500)
        directory_filter: Optional directory path to filter by (uses rowid-based pagination)

    Yields:
        tuple: (file_path, song_data, timestamp) for each cache entry
    """
    _ensure_initialized()
    try:
        conn = get_connection()
        cursor = conn.cursor()

        if directory_filter:
            # Optimized rowid-based pagination with directory pre-filtering
            # Normalize and prepare LIKE pattern (stored lowercase for index usage)
            dir_prefix = normalize_cache_key(directory_filter).lower().rstrip("/\\") + "/"
            like_pattern = dir_prefix + "%"

            last_rowid = 0
            while True:
                cursor.execute(
                    """SELECT rowid, file_path, song_data, timestamp
                       FROM song_cache
                       WHERE file_path LIKE ? ESCAPE '\\' AND rowid > ?
                       ORDER BY rowid
                       LIMIT ?""",
                    (like_pattern, last_rowid, page_size)
                )
                rows = cursor.fetchall()

                if not rows:
                    break

                for row in rows:
                    last_rowid = row[0]
                    yield (row[1], row[2], row[3])  # file_path, song_data, timestamp
        else:
            # Legacy OFFSET/LIMIT for backward compatibility (no filter)
            offset = 0
            while True:
                cursor.execute(
                    "SELECT file_path, song_data, timestamp FROM song_cache LIMIT ? OFFSET ?", (page_size, offset)
                )
                rows = cursor.fetchall()

                if not rows:
                    break

                for row in rows:
                    yield row

                offset += page_size

        conn.close()
    except Exception as e:
        logger.error("Error streaming cache entries: %s", str(e))


def remove_cache_entry(file_path):
    """
    Remove a cache entry for the given file path.

    Args:
        file_path (str): Path of the file to remove from cache
    """
    _ensure_initialized()
    file_path = normalize_cache_key(file_path)  # Normalize path separators
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM song_cache WHERE file_path = ?", (file_path,))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error("Error removing cache entry for %s: %s", file_path, str(e))


def cleanup_stale_entries(valid_paths):
    """
    Remove cache entries for files that no longer exist.

    Args:
        valid_paths (set): Set of file paths that still exist

    Returns:
        int: Number of stale entries removed
    """
    _ensure_initialized()
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
            logger.info("Removed %s stale cache entries", len(stale_paths))

        return len(stale_paths)
    except Exception as e:
        logger.error("Error cleaning up stale cache entries: %s", str(e))
        return 0
