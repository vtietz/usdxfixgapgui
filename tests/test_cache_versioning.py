"""Test cache versioning and migration"""

import sqlite3
import tempfile
import os
import pickle
from unittest.mock import patch

import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


class TestCacheVersioning:
    """Test cache version migration functionality"""

    def test_fresh_database_no_cache_clear(self):
        """New database should be initialized with current version and not flag cache clear"""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "test_cache.db")

            # Mock the _DB_PATH
            with patch("common.database._DB_PATH", db_path):
                # Reset initialization flag
                import common.database as db_module

                db_module._db_initialized = False
                db_module._cache_was_cleared = False

                # Initialize database
                from common.database import init_database, CACHE_VERSION

                cache_was_cleared = init_database()

                # Should NOT flag cache clear on fresh database
                assert cache_was_cleared is False, "Fresh database should not flag cache clear"

                # Check version was set correctly
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT value FROM cache_metadata WHERE key=?", ("version",))
                result = cursor.fetchone()
                conn.close()

                assert result is not None, "Version metadata should be set"
                assert int(result[0]) == CACHE_VERSION, f"Version should be {CACHE_VERSION}"

    def test_version_mismatch_triggers_cache_clear(self):
        """Cache should be cleared when version is outdated and return flag"""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "test_cache.db")

            # Create old cache database (version 1)
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Create tables
            cursor.execute(
                """
            CREATE TABLE song_cache (
                file_path TEXT PRIMARY KEY,
                song_data BLOB,
                timestamp DATETIME
            )
            """
            )

            cursor.execute(
                """
            CREATE TABLE cache_metadata (
                key TEXT PRIMARY KEY,
                value TEXT
            )
            """
            )

            # Set old version
            cursor.execute("INSERT INTO cache_metadata VALUES (?, ?)", ("version", "1"))

            # Add dummy cache entries
            cursor.execute(
                "INSERT INTO song_cache VALUES (?, ?, ?)", ("/path/to/song1.txt", b"dummy_data_1", "2025-01-01")
            )
            cursor.execute(
                "INSERT INTO song_cache VALUES (?, ?, ?)", ("/path/to/song2.txt", b"dummy_data_2", "2025-01-01")
            )

            conn.commit()

            # Verify initial state
            cursor.execute("SELECT COUNT(*) FROM song_cache")
            initial_count = cursor.fetchone()[0]
            assert initial_count == 2, "Should have 2 initial cache entries"

            conn.close()

            # Now initialize with new version
            with patch("common.database._DB_PATH", db_path):
                import common.database as db_module

                db_module._db_initialized = False
                db_module._cache_was_cleared = False

                from common.database import init_database, CACHE_VERSION

                cache_was_cleared = init_database()

                # Version mismatches now preserve entries for lazy upgrade
                assert cache_was_cleared is False, "Version mismatch should no longer clear cache"

                # Verify cache entries remain intact
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()

                # Check version was updated
                cursor.execute("SELECT value FROM cache_metadata WHERE key=?", ("version",))
                new_version = int(cursor.fetchone()[0])
                assert new_version == CACHE_VERSION, f"Version should be updated to {CACHE_VERSION}"

                cursor.execute("SELECT COUNT(*) FROM song_cache")
                final_count = cursor.fetchone()[0]
                assert final_count == 2, "Cache entries should be preserved after metadata upgrade"

                conn.close()

    def test_matching_version_preserves_cache(self):
        """Cache should be preserved when version matches"""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "test_cache.db")

            # Create cache database with current version
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Get current version first
            import common.database as db_module

            current_version = db_module.CACHE_VERSION

            # Create tables
            cursor.execute(
                """
            CREATE TABLE song_cache (
                file_path TEXT PRIMARY KEY,
                song_data BLOB,
                timestamp DATETIME
            )
            """
            )

            cursor.execute(
                """
            CREATE TABLE cache_metadata (
                key TEXT PRIMARY KEY,
                value TEXT
            )
            """
            )

            # Set current version
            cursor.execute("INSERT INTO cache_metadata VALUES (?, ?)", ("version", str(current_version)))

            # Add cache entries
            cursor.execute(
                "INSERT INTO song_cache VALUES (?, ?, ?)", ("/path/to/song1.txt", b"dummy_data_1", "2025-01-01")
            )
            cursor.execute(
                "INSERT INTO song_cache VALUES (?, ?, ?)", ("/path/to/song2.txt", b"dummy_data_2", "2025-01-01")
            )

            conn.commit()
            conn.close()

            # Now initialize (should not clear cache)
            with patch("common.database._DB_PATH", db_path):
                db_module._db_initialized = False
                db_module._cache_was_cleared = False

                from common.database import init_database

                cache_was_cleared = init_database()

                # Should NOT flag cache clear when version matches
                assert cache_was_cleared is False, "Matching version should not flag cache clear"

                # Verify cache was preserved
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()

                cursor.execute("SELECT COUNT(*) FROM song_cache")
                final_count = cursor.fetchone()[0]
                assert final_count == 2, "Cache should be preserved when version matches"

                conn.close()

    def test_legacy_cache_without_metadata_triggers_clear(self):
        """Cache should be cleared when metadata table doesn't exist (very old cache)"""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "test_cache.db")

            # Create old cache without metadata table
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
            CREATE TABLE song_cache (
                file_path TEXT PRIMARY KEY,
                song_data BLOB,
                timestamp DATETIME
            )
            """
            )

            # Add entry
            cursor.execute(
                "INSERT INTO song_cache VALUES (?, ?, ?)", ("/path/to/song1.txt", b"dummy_data_1", "2025-01-01")
            )

            conn.commit()
            conn.close()

            # Initialize with versioning
            with patch("common.database._DB_PATH", db_path):
                import common.database as db_module

                db_module._db_initialized = False
                db_module._cache_was_cleared = False

                from common.database import init_database

                cache_was_cleared = init_database()

                # Legacy caches should now be preserved for lazy upgrade
                assert cache_was_cleared is False, "Legacy caches should be preserved"

                # Verify entries still exist
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()

                cursor.execute("SELECT COUNT(*) FROM song_cache")
                final_count = cursor.fetchone()[0]
                assert final_count == 1, "Legacy cache entry should be preserved for migration"

                conn.close()

    def test_legacy_cache_entry_migrates_without_full_rescan(self):
        """Legacy payloads should be re-written in-place without deleting data."""

        from model.song import Song, SongStatus
        from common.database import (
            init_database,
            get_cache_entry,
            normalize_cache_key,
        )
        from common.cache_schema import CacheEnvelope, CACHE_ENTRY_VERSION

        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "test_cache.db")

            with patch("common.database._DB_PATH", db_path):
                import common.database as db_module

                db_module._db_initialized = False
                db_module._cache_was_cleared = False

                init_database()

                song = Song("/tmp/legacy-song.txt")
                song.title = "Legacy"
                song.artist = "Cache"
                song.status = SongStatus.MATCH

                # Simulate pre-envelope payload missing backing attributes
                song.__dict__["status"] = "MATCH"
                song.__dict__.pop("_status", None)
                song.__dict__.pop("_status_changed_at", None)
                song.__dict__.pop("_status_changed_str", None)

                legacy_blob = pickle.dumps(song)
                timestamp = "2025-01-01T00:00:00"
                normalized_path = normalize_cache_key(song.txt_file).lower()

                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO song_cache (file_path, song_data, timestamp) VALUES (?, ?, ?)",
                    (normalized_path, legacy_blob, timestamp),
                )
                conn.commit()
                conn.close()

                restored = get_cache_entry(song.txt_file)
                assert restored is not None, "Legacy payload should be deserialized"
                assert restored.status == SongStatus.MATCH, "Song status should survive migration"

                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT song_data, timestamp FROM song_cache WHERE file_path=?", (normalized_path,))
                row = cursor.fetchone()
                conn.close()

                assert row is not None, "Migrated row should still exist"
                envelope = pickle.loads(row[0])
                assert isinstance(envelope, CacheEnvelope), "Migrated entry should be wrapped in envelope"
                assert envelope.schema_version == CACHE_ENTRY_VERSION, "Envelope should use latest schema"
                assert row[1] == timestamp, "Original processed timestamp should be preserved"
