import os
import sqlite3
import logging

logger = logging.getLogger(__name__)

class SongCache:
    """A cache for song metadata using SQLite"""
    
    _instance = None
    
    @classmethod
    def initialize(cls, db_path):
        """Initialize the global SongCache instance"""
        if cls._instance is None:
            cls._instance = SongCache(db_path)
        return cls._instance
    
    @classmethod
    def get_instance(cls):
        """Get the initialized SongCache instance"""
        if cls._instance is None:
            raise RuntimeError("SongCache has not been initialized. Call SongCache.initialize() first.")
        return cls._instance
    
    def __init__(self, db_path):
        self.db_path = db_path
        self._init_db()
        logger.info(f"Song cache initialized with database: {db_path}")
    
    def _init_db(self):
        """Initialize the database schema if it doesn't exist"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS song_cache (
                txt_file TEXT PRIMARY KEY,
                last_modified INTEGER,
                title TEXT,
                artist TEXT,
                audio TEXT,
                gap INTEGER,
                bpm INTEGER,
                start INTEGER,
                is_relative INTEGER,
                usdb_id TEXT
            )
            ''')
            
            conn.commit()
            conn.close()
        except sqlite3.Error as e:
            logger.error(f"Database initialization error: {e}")
    
    def get_song_data(self, txt_file):
        """Get cached song data if it exists and is up-to-date"""
        if not os.path.exists(txt_file):
            return None
        
        try:
            file_mtime = int(os.path.getmtime(txt_file))
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT last_modified, title, artist, audio, gap, bpm, start, is_relative, usdb_id "
                "FROM song_cache WHERE txt_file = ?",
                (txt_file,)
            )
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                db_mtime, title, artist, audio, gap, bpm, start, is_relative, usdb_id = result
                
                # If the file hasn't changed since it was cached
                if db_mtime >= file_mtime:
                    return {
                        'title': title,
                        'artist': artist,
                        'audio': audio,
                        'gap': gap,
                        'bpm': bpm,
                        'start': start,
                        'is_relative': bool(is_relative),
                        'usdb_id': usdb_id if usdb_id != 'None' else None
                    }
            
            return None
        except Exception as e:
            logger.error(f"Error getting song data from cache: {e}")
            return None
    
    def cache_song_data(self, txt_file, song_data):
        """Update or insert song data in the cache"""
        if not os.path.exists(txt_file):
            return
        
        try:
            file_mtime = int(os.path.getmtime(txt_file))
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                """
                INSERT OR REPLACE INTO song_cache
                (txt_file, last_modified, title, artist, audio, gap, bpm, start, is_relative, usdb_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    txt_file,
                    file_mtime,
                    song_data.get('title', ''),
                    song_data.get('artist', ''),
                    song_data.get('audio', ''),
                    song_data.get('gap', 0),
                    song_data.get('bpm', 0),
                    song_data.get('start', 0),
                    1 if song_data.get('is_relative', False) else 0,
                    str(song_data.get('usdb_id'))
                )
            )
            
            conn.commit()
            conn.close()
            logger.debug(f"Cached song data for {txt_file}")
        except Exception as e:
            logger.error(f"Error caching song data: {e}")
