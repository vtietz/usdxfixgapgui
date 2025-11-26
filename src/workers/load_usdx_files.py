import os
import logging
import time
import datetime
import pickle
import asyncio
import threading
from typing import AsyncGenerator, Optional, Tuple
from PySide6.QtCore import Signal
from model.song import Song
from services.song_service import SongService
from managers.worker_queue_manager import IWorker, IWorkerSignals
from common.database import (
    cleanup_stale_entries,
    stream_cache_entries,
    normalize_cache_key,
    get_cache_entry,
    get_all_cache_entries,  # noqa: F401 - Backward compatibility for tests that patch symbol
)

logger = logging.getLogger(__name__)

__all__ = ["LoadUsdxFilesWorker", "WorkerSignals", "get_all_cache_entries"]


class WorkerSignals(IWorkerSignals):
    songLoaded = Signal(Song)
    songsLoadedBatch = Signal(list)  # Batch signal for better performance
    cacheCleanup = Signal(int)  # Signal to report stale cache entries cleaned up


class LoadUsdxFilesWorker(IWorker):
    def __init__(self, directory, tmp_root, config=None):
        super().__init__()
        self.signals = WorkerSignals()
        self.directory = directory
        self.tmp_root = tmp_root
        self.description = f"Preparing to scan {directory}"
        self.path_usdb_id_map = {}
        self.loaded_paths = set()  # Track files we've loaded to detect stale cache entries
        self.reload_single_file = None  # Path to single file to reload (when used for reload)
        self.song_service = SongService()  # Create song service

        # Batching for performance - use config or default to 50
        self.batch_size = config.song_list_batch_size if config else 50
        self._pending_scan_batch: list[Song] = []
        self._ttfb_start = 0.0  # Track time to first batch
        self._ttfb_logged = False

    async def _cooperative_pause(self, interval_ms: int = 50):
        """
        Cooperatively pause while the queue indicates we should yield to higher-priority work.
        This does NOT cancel; it simply yields the event loop until the yield condition clears.
        """
        while not self.is_cancelled() and self.should_yield():
            await asyncio.sleep(interval_ms / 1000.0)

    async def _maybe_yield(self):
        """
        Single check: if a yield is requested, pause cooperatively until cleared.
        """
        if self.should_yield():
            await self._cooperative_pause()

    async def _emit_batch(self, batch: list[Song]):
        """Emit provided batch and yield to event loop for UI updates."""
        if not batch:
            return

        songs = list(batch)
        batch.clear()
        batch_size = len(songs)

        self.signals.songsLoadedBatch.emit(songs)

        if not self._ttfb_logged and self._ttfb_start:
            ttfb_ms = (time.time() - self._ttfb_start) * 1000
            logger.debug("Time to first batch: %.1f ms", ttfb_ms)
            self._ttfb_logged = True

        if self._ttfb_start:
            elapsed_ms = (time.time() - self._ttfb_start) * 1000
        else:
            elapsed_ms = 0
        logger.debug("Worker emitted batch (%s songs) at %.1f ms", batch_size, elapsed_ms)

        self.signals.progress.emit()

        # Yield to asyncio event loop to allow signal processing
        await asyncio.sleep(0)
        # Cooperative yield if higher-priority work is pending
        await self._maybe_yield()

        logger.debug("Emitted batch of %s songs", batch_size)

    async def _append_scan_song(self, song: Song | None):
        if not song:
            return
        self._pending_scan_batch.append(song)
        if len(self._pending_scan_batch) >= self.batch_size:
            await self._emit_batch(self._pending_scan_batch)

    async def _flush_scan_batch(self):
        if self._pending_scan_batch:
            await self._emit_batch(self._pending_scan_batch)

    async def load(self, txt_file_path, force_reload=False) -> Song | None:
        """Load a song from file, optionally forcing reload."""
        self.description = f"Loading file {txt_file_path}"

        # Check for cancellation before loading
        if self.is_cancelled():
            return None

        # Cooperatively yield before heavy load
        await self._maybe_yield()

        try:
            # Use the service to load the song with proper argument order:
            # load_song(txt_file, force_reload, cancel_check)
            song = await self.song_service.load_song(txt_file_path, force_reload, self.is_cancelled)
            song.usdb_id = self.path_usdb_id_map.get(song.path, None)
            return song

        except Exception as e:
            # Create minimal song data for error reporting
            song = Song(txt_file_path)
            song.set_error(str(e))
            logger.error(f"Error loading song '{txt_file_path}")
            logger.exception(e)
            return song

    async def load_from_cache(self):
        """Load all songs from the cache database first (using streaming for fast initial display)."""
        start_time = time.time()
        self._ttfb_start = start_time
        self._ttfb_logged = False
        self.description = "Loading songs from cache"
        logger.info("Loading songs from cache for directory: %s", self.directory)

        # Use SQL-side filtering for massive performance boost
        loaded = 0
        # Stream with directory filter (rowid-based pagination, SQL LIKE pre-filter)
        page_songs: list[Song] = []
        for file_path, song_data, timestamp_str in stream_cache_entries(page_size=500, directory_filter=self.directory):
            if self.is_cancelled():
                await self._emit_batch(page_songs)
                return

            # Yield to allow UI/instant tasks to progress between cache rows
            await self._maybe_yield()

            # Deserialize song (only directory-relevant entries thanks to SQL filter)
            try:
                song = pickle.loads(song_data)
            except Exception as e:
                logger.error("Failed to deserialize cache for %s: %s", file_path, e)
                continue

            # Ensure song is valid
            if not hasattr(song, "path"):
                continue

            # Apply USDB ID mapping to cached songs
            song.usdb_id = self.path_usdb_id_map.get(song.path, None)

            page_songs.append(song)
            if len(page_songs) >= self.batch_size:
                await self._emit_batch(page_songs)

            # Track loaded paths for cleanup
            self.loaded_paths.add(normalize_cache_key(file_path).lower())
            loaded += 1

        # Track how many songs we loaded from cache for cleanup logic
        self._cache_loaded_count = loaded

        elapsed_ms = (time.time() - start_time) * 1000
        logger.info("Loaded %s cached songs in %.1f ms", loaded, elapsed_ms)

        # Flush any remaining songs in batch
        await self._emit_batch(page_songs)

    async def _async_os_walk(self, directory: str) -> AsyncGenerator[Tuple[str, list[str], list[str]], None]:
        """Stream os.walk results from a background thread without blocking the event loop."""

        loop = asyncio.get_running_loop()
        queue: "asyncio.Queue[Optional[Tuple[str, list[str], list[str]] | Exception]]" = asyncio.Queue()
        stop_event = threading.Event()

        def _walker():
            try:
                for root, dirs, files in os.walk(directory):
                    if stop_event.is_set():
                        break
                    loop.call_soon_threadsafe(queue.put_nowait, (root, dirs, files))
            except Exception as exc:  # pragma: no cover - defensive
                loop.call_soon_threadsafe(queue.put_nowait, exc)
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        threading.Thread(target=_walker, name="LoadUsdxFilesWalker", daemon=True).start()

        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                if isinstance(item, Exception):
                    raise item
                yield item
        finally:
            stop_event.set()

    async def scan_directory(self):
        """Scan directory for new or changed songs and USDB metadata."""
        self.description = "Scanning directory for new/changed songs"
        logger.info("Scanning directory %s for songs and USDB metadata", self.directory)

        # Throttling: only emit progress every N files or every X seconds
        file_count = 0
        last_progress_time = time.time()
        # Use batch_size for progress interval to align with UI batching
        PROGRESS_FILE_INTERVAL = self.batch_size  # Emit progress aligned with batch size
        PROGRESS_TIME_INTERVAL = 0.3  # Or every 300ms

        async for root, dirs, files in self._async_os_walk(self.directory):
            self.description = f"Searching for updates in {root}"
            if await self._handle_scan_cancellation():
                return

            await self._maybe_yield()
            self._extract_usdb_metadata(root, files)

            file_count, last_progress_time, cancelled = await self._process_directory_files(
                root,
                files,
                file_count,
                last_progress_time,
                PROGRESS_FILE_INTERVAL,
                PROGRESS_TIME_INTERVAL,
            )
            if cancelled:
                return

        # Flush any remaining songs in batch
        await self._flush_scan_batch()

        # Log USDB IDs found during scan
        if self.path_usdb_id_map:
            logger.info("Found %s USDB metadata files", len(self.path_usdb_id_map))

    async def _handle_scan_cancellation(self) -> bool:
        if self.is_cancelled():
            await self._flush_scan_batch()
            return True
        return False

    def _extract_usdb_metadata(self, root: str, files: list[str]):
        if root in self.path_usdb_id_map:
            return
        for file in files:
            if not file.endswith(".usdb"):
                continue
            usdb_file_path = os.path.join(root, file)
            try:
                import json

                with open(usdb_file_path, "r", encoding="utf-8") as f:
                    usdb_data = json.load(f)
                    song_id = usdb_data.get("song_id")
                    if song_id is not None:
                        self.path_usdb_id_map[root] = song_id
            except Exception as e:
                logger.warning("Failed to parse .usdb file %s: %s", usdb_file_path, e)
            break

    async def _process_directory_files(
        self,
        root: str,
        files: list[str],
        file_count: int,
        last_progress_time: float,
        file_interval: int,
        time_interval: float,
    ) -> tuple[int, float, bool]:
        for file in files:
            if not file.endswith(".txt"):
                continue
            if await self._handle_scan_cancellation():
                return file_count, last_progress_time, True

            await self._process_text_file(root, file)
            file_count += 1
            last_progress_time = self._maybe_emit_progress(
                file_count,
                last_progress_time,
                file_interval,
                time_interval,
            )

        last_progress_time = self._maybe_emit_progress(
            file_count,
            last_progress_time,
            file_interval,
            time_interval,
        )
        return file_count, last_progress_time, False

    async def _process_text_file(self, root: str, filename: str):
        await self._maybe_yield()
        song_path = os.path.join(root, filename)
        normalized_path = normalize_cache_key(song_path).lower()
        if normalized_path in self.loaded_paths:
            await self._handle_cached_song(song_path)
            return

        await self._handle_new_song(song_path, normalized_path)

    async def _handle_cached_song(self, song_path: str):
        try:
            mod_time = datetime.datetime.fromtimestamp(os.path.getmtime(song_path))
            cached_song = get_cache_entry(song_path, mod_time)
            if cached_song:
                return

            logger.info("Detected modified file: %s", song_path)
            await self._maybe_yield()
            song = await self.load(song_path, force_reload=True)
            if song:
                await self._append_scan_song(song)
        except Exception as e:
            logger.warning("Error checking mtime for %s: %s", song_path, e)

    async def _handle_new_song(self, song_path: str, normalized_path: str):
        await self._maybe_yield()
        song = await self.load(song_path)
        if song:
            await self._append_scan_song(song)
            self.loaded_paths.add(normalized_path)

    def _maybe_emit_progress(
        self,
        file_count: int,
        last_progress_time: float,
        file_interval: int,
        time_interval: float,
    ) -> float:
        current_time = time.time()
        if (file_interval and file_count % file_interval == 0) or (current_time - last_progress_time) > time_interval:
            self.signals.progress.emit()
            return current_time
        return last_progress_time

    async def cleanup_cache(self):
        """Clean up stale cache entries."""
        self.description = "Cleaning up stale cache entries"
        logger.info("Cleaning up stale cache entries")

        stale_entries_removed = cleanup_stale_entries(self.loaded_paths)
        self.signals.cacheCleanup.emit(stale_entries_removed)

    async def run(self):
        logger.debug(self.description)

        # If this is a single file reload operation
        if self.reload_single_file:
            self.description = f"Reloading song {self.reload_single_file}"
            logger.info(f"Reloading song: {self.reload_single_file}")

            song = await self.load(self.reload_single_file, force_reload=True)
            if song:
                self.signals.songLoaded.emit(song)
                # Normalize path to match cache key format (forward slashes)
                self.loaded_paths.add(normalize_cache_key(song.txt_file).lower())

            self.signals.finished.emit()
            return

        # Regular operation - loading all songs
        # IMPORTANT ORDER:
        # 1. Load cache FIRST for fast UI population (USDB IDs applied during scan)
        # 2. Scan for USDB metadata files in parallel
        # 3. Scan directory for new/changed files
        # NOTE: USDB metadata scan happens during directory scan to avoid double os.walk()
        await self.load_from_cache()

        # Scan directory for new/changed songs (USDB metadata collected inline)
        await self.scan_directory()

        # Clean up stale cache entries ONLY if we successfully loaded from cache
        # This prevents deleting freshly-created cache entries when starting with empty cache
        # Stale entries are only possible if we loaded songs from cache that no longer exist on disk
        if hasattr(self, "_cache_loaded_count") and self._cache_loaded_count > 0:
            await self.cleanup_cache()
        else:
            logger.debug("Skipping cache cleanup (no songs loaded from cache)")

        # Flush any remaining songs in batch (safety net)
        await self._flush_scan_batch()

        # Always emit finished signal, even if cancelled
        self.signals.finished.emit()
        if self.is_cancelled():
            logger.debug("Song loading cancelled.")
        else:
            logger.debug("Finished loading songs.")
