"""Test cache versioning and migration"""
import pytest
import sqlite3
import tempfile
import os
from unittest.mock import patch

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestCacheVersioning:
    """Test cache version migration functionality"""

    def test_cache_version_initialized_on_fresh_database(self):
        """New database should be initialized with current version"""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, 'test_cache.db')
            
            # Mock the DB_PATH
            with patch('common.database.DB_PATH', db_path):
                # Reset initialization flag
                import common.database as db_module
                db_module._db_initialized = False
                
                # Initialize database
                from common.database import init_database, CACHE_VERSION
                init_database()
                
                # Check version was set
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute('SELECT value FROM cache_metadata WHERE key=?', ('version',))
                result = cursor.fetchone()
                conn.close()
                
                assert result is not None, "Version metadata should be set"
                assert int(result[0]) == CACHE_VERSION, f"Version should be {CACHE_VERSION}"

    def test_cache_cleared_on_version_mismatch(self):
        """Cache should be cleared when version is outdated"""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, 'test_cache.db')
            
            # Create old cache database (version 1)
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Create tables
            cursor.execute('''
            CREATE TABLE song_cache (
                file_path TEXT PRIMARY KEY,
                song_data BLOB,
                timestamp DATETIME
            )
            ''')
            
            cursor.execute('''
            CREATE TABLE cache_metadata (
                key TEXT PRIMARY KEY,
                value TEXT
            )
            ''')
            
            # Set old version
            cursor.execute('INSERT INTO cache_metadata VALUES (?, ?)', ('version', '1'))
            
            # Add some dummy cache entries
            cursor.execute('INSERT INTO song_cache VALUES (?, ?, ?)', 
                          ('/path/to/song1.txt', b'dummy_data_1', '2025-01-01'))
            cursor.execute('INSERT INTO song_cache VALUES (?, ?, ?)',
                          ('/path/to/song2.txt', b'dummy_data_2', '2025-01-01'))
            cursor.execute('INSERT INTO song_cache VALUES (?, ?, ?)',
                          ('/path/to/song3.txt', b'dummy_data_3', '2025-01-01'))
            
            conn.commit()
            
            # Verify initial state
            cursor.execute('SELECT COUNT(*) FROM song_cache')
            initial_count = cursor.fetchone()[0]
            assert initial_count == 3, "Should have 3 initial cache entries"
            
            cursor.execute('SELECT value FROM cache_metadata WHERE key=?', ('version',))
            initial_version = int(cursor.fetchone()[0])
            assert initial_version == 1, "Initial version should be 1"
            
            conn.close()
            
            # Now initialize with new version
            with patch('common.database.DB_PATH', db_path):
                import common.database as db_module
                db_module._db_initialized = False
                
                from common.database import init_database, CACHE_VERSION
                init_database()
                
                # Verify migration happened
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                # Check version was updated
                cursor.execute('SELECT value FROM cache_metadata WHERE key=?', ('version',))
                new_version = int(cursor.fetchone()[0])
                assert new_version == CACHE_VERSION, f"Version should be updated to {CACHE_VERSION}"
                
                # Check cache was cleared
                cursor.execute('SELECT COUNT(*) FROM song_cache')
                final_count = cursor.fetchone()[0]
                assert final_count == 0, "Cache should be cleared after version upgrade"
                
                conn.close()

    def test_cache_preserved_on_matching_version(self):
        """Cache should be preserved when version matches"""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, 'test_cache.db')
            
            # Create cache database with current version
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Get current version first
            import common.database as db_module
            current_version = db_module.CACHE_VERSION
            
            # Create tables
            cursor.execute('''
            CREATE TABLE song_cache (
                file_path TEXT PRIMARY KEY,
                song_data BLOB,
                timestamp DATETIME
            )
            ''')
            
            cursor.execute('''
            CREATE TABLE cache_metadata (
                key TEXT PRIMARY KEY,
                value TEXT
            )
            ''')
            
            # Set current version
            cursor.execute('INSERT INTO cache_metadata VALUES (?, ?)', 
                          ('version', str(current_version)))
            
            # Add cache entries
            cursor.execute('INSERT INTO song_cache VALUES (?, ?, ?)', 
                          ('/path/to/song1.txt', b'dummy_data_1', '2025-01-01'))
            cursor.execute('INSERT INTO song_cache VALUES (?, ?, ?)',
                          ('/path/to/song2.txt', b'dummy_data_2', '2025-01-01'))
            
            conn.commit()
            
            # Verify initial state
            cursor.execute('SELECT COUNT(*) FROM song_cache')
            initial_count = cursor.fetchone()[0]
            assert initial_count == 2, "Should have 2 initial cache entries"
            
            conn.close()
            
            # Now initialize (should not clear cache)
            with patch('common.database.DB_PATH', db_path):
                db_module._db_initialized = False
                
                from common.database import init_database, CACHE_VERSION
                init_database()
                
                # Verify cache was preserved
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                # Check version is still current
                cursor.execute('SELECT value FROM cache_metadata WHERE key=?', ('version',))
                version = int(cursor.fetchone()[0])
                assert version == CACHE_VERSION, f"Version should still be {CACHE_VERSION}"
                
                # Check cache was NOT cleared
                cursor.execute('SELECT COUNT(*) FROM song_cache')
                final_count = cursor.fetchone()[0]
                assert final_count == 2, "Cache should be preserved when version matches"
                
                conn.close()

    def test_cache_cleared_when_no_version_metadata(self):
        """Cache should be cleared when metadata table doesn't exist (very old cache)"""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, 'test_cache.db')
            
            # Create old cache without metadata table
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
            CREATE TABLE song_cache (
                file_path TEXT PRIMARY KEY,
                song_data BLOB,
                timestamp DATETIME
            )
            ''')
            
            # Add some entries
            cursor.execute('INSERT INTO song_cache VALUES (?, ?, ?)', 
                          ('/path/to/song1.txt', b'dummy_data_1', '2025-01-01'))
            
            conn.commit()
            
            # Verify initial state
            cursor.execute('SELECT COUNT(*) FROM song_cache')
            initial_count = cursor.fetchone()[0]
            assert initial_count == 1, "Should have 1 initial cache entry"
            
            # Verify metadata table doesn't exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cache_metadata'")
            assert cursor.fetchone() is None, "Metadata table should not exist"
            
            conn.close()
            
            # Initialize with versioning
            with patch('common.database.DB_PATH', db_path):
                import common.database as db_module
                db_module._db_initialized = False
                
                from common.database import init_database, CACHE_VERSION
                init_database()
                
                # Verify migration
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                # Metadata table should now exist with version
                cursor.execute('SELECT value FROM cache_metadata WHERE key=?', ('version',))
                version = int(cursor.fetchone()[0])
                assert version == CACHE_VERSION
                
                # Cache should be cleared (version 0 -> current version)
                cursor.execute('SELECT COUNT(*) FROM song_cache')
                final_count = cursor.fetchone()[0]
                assert final_count == 0, "Cache should be cleared when migrating from no-version to versioned"
                
                conn.close()
