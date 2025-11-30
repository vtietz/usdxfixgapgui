import os
import logging
import json
from PySide6.QtCore import Signal
from model.song import Song
from services import song_service
from utils import files
from managers.worker_queue_manager import IWorker, IWorkerSignals

logger = logging.getLogger(__name__)


class WorkerSignals(IWorkerSignals):
    songReloaded = Signal(Song)


class ReloadSongWorker(IWorker):
    """Worker specifically designed for reloading a single song"""

    def __init__(self, song_path, directory):
        super().__init__(is_instant=True)  # Reload is instant - don't wait behind long tasks
        self.signals = WorkerSignals()
        self.song_path = song_path
        self.directory = directory
        self.description = f"Loading song {os.path.basename(song_path)}"
        self.song_service = song_service.SongService()

    def _get_usdb_id_for_directory(self, directory: str) -> int | None:
        """Scan directory for .usdb file and extract song_id."""
        try:
            for file in os.listdir(directory):
                if file.endswith(".usdb"):
                    usdb_file_path = os.path.join(directory, file)
                    try:
                        with open(usdb_file_path, "r", encoding="utf-8") as f:
                            usdb_data = json.load(f)
                            if "song_id" in usdb_data:
                                logger.debug("Found USDB ID %s for %s", usdb_data["song_id"], directory)
                                return usdb_data["song_id"]
                    except Exception as e:
                        logger.warning("Failed to parse .usdb file %s: %s", usdb_file_path, e)
                    break  # Only process one .usdb file per directory
        except Exception as e:
            logger.warning("Failed to scan directory %s for .usdb files: %s", directory, e)
        return None

    async def load(self) -> Song:
        """Load a song from file, forcing reload."""
        try:
            txt_file = files.find_txt_file(self.song_path)
            song = await self.song_service.load_song(txt_file, True, self.is_cancelled)

            # Apply USDB ID from .usdb file if present
            song.usdb_id = self._get_usdb_id_for_directory(song.path)

            return song

        except RuntimeError as e:
            # Specific handling for RuntimeError (failed to load USDX file)
            logger.error("RuntimeError reloading song '%s': %s", self.song_path, e)
            logger.exception(e)

            # Create a basic song with error status
            song = Song()
            song.path = self.song_path
            song.txt_file = self.song_path if self.song_path.endswith(".txt") else ""
            song.set_error(str(e))

            return song

    async def run(self):
        """Execute the worker's task."""
        logger.debug("Loading song: %s", self.song_path)

        song = await self.load()

        if not self.is_cancelled():
            self.signals.songReloaded.emit(song)
            logger.debug("Finished reloading song: %s", self.song_path)
        else:
            logger.debug("Cancelled reloading song: %s", self.song_path)

        # Always emit finished signal, even if cancelled
        self.signals.finished.emit()
