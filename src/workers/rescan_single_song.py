"""
RescanSingleSongWorker: Targeted song rescanning without full directory scan.

Used by watch mode to efficiently add newly created songs to the cache.
"""

import os
import logging
from typing import Optional
from PySide6.QtCore import Signal
from model.song import Song
from services.song_service import SongService
from managers.worker_queue_manager import IWorker, IWorkerSignals

logger = logging.getLogger(__name__)


class WorkerSignals(IWorkerSignals):
    """Signals emitted by RescanSingleSongWorker"""

    songScanned = Signal(Song)


class RescanSingleSongWorker(IWorker):
    """Worker for scanning/rescanning a single song folder."""

    def __init__(self, song_path: str, usdb_id: Optional[int] = None):
        """
        Initialize RescanSingleSongWorker.

        Args:
            song_path: Path to the song folder or .txt file
            usdb_id: Optional USDB ID to associate with the song
        """
        super().__init__(is_instant=True)  # Instant task - don't wait behind long queues
        self.signals = WorkerSignals()
        self.song_path = song_path
        self.usdb_id = usdb_id
        self.description = f"Scanning song {os.path.basename(song_path)}"
        self.song_service = SongService()

    async def load(self) -> Song:
        """Load/scan the song from file."""
        try:
            # Determine txt file path
            if os.path.isfile(self.song_path) and self.song_path.endswith(".txt"):
                txt_file = self.song_path
            else:
                # Find txt file in directory
                from utils import files

                txt_file = files.find_txt_file(self.song_path)

            # Load song with force_reload=True to bypass cache
            song = await self.song_service.load_song(txt_file, force_reload=True, cancel_check=self.is_cancelled)

            # Set USDB ID if provided
            if self.usdb_id is not None:
                song.usdb_id = self.usdb_id

            return song

        except Exception as e:
            logger.error(f"Error scanning song '{self.song_path}': {e}", exc_info=True)

            # Create minimal song with error status
            txt_path = self.song_path if self.song_path.endswith(".txt") else ""
            song = Song(txt_file=txt_path)
            song.set_error(str(e))

            return song

    async def run(self):
        """Execute the scan."""
        logger.info(f"Scanning single song: {self.song_path}")

        song = await self.load()

        if not self.is_cancelled():
            self.signals.songScanned.emit(song)
            logger.debug(f"Finished scanning song: {self.song_path}")
        else:
            logger.debug(f"Cancelled scanning song: {self.song_path}")

        # Always emit finished
        self.signals.finished.emit()
