import os
import logging
import datetime
from typing import Callable, Optional

from model.song import Song, SongStatus
from model.usdx_file import USDXFile
from utils import audio
import utils.files as files
from common.database import get_cache_entry, set_cache_entry, remove_cache_entry
from services.gap_info_service import GapInfoService
from services.usdx_file_service import USDXFileService

logger = logging.getLogger(__name__)


class SongService:
    """Service class for operations on Song objects"""

    def __init__(self) -> None:
        self.gap_info_service = GapInfoService()

    async def load_song(
        self, txt_file: str, force_reload: bool = False, cancel_check: Optional[Callable] = None
    ) -> Song:
        """Load a song from a text file, using cache if available."""
        logger.debug(
            "Loading %s, force_reload=%s, cancel_check=%s",
            txt_file,
            force_reload,
            "provided" if cancel_check else "None",
        )

        song = Song(txt_file)

        if not os.path.exists(txt_file):
            logger.error("File not found during load: %s", txt_file)
            song.set_error(f"File not found: {txt_file}")
            return song

        if not force_reload:
            logger.debug("Checking cache for %s", txt_file)
            mod_time = datetime.datetime.fromtimestamp(os.path.getmtime(txt_file))
            cached_song = get_cache_entry(txt_file, mod_time)
            if cached_song:
                logger.debug("Cache hit for %s", txt_file)
                return cached_song
            logger.debug("Cache miss for %s, loading from disk", txt_file)

        logger.info("Loading new/changed song from disk: %s", txt_file)

        try:
            usdx_file = USDXFile(txt_file)
            await USDXFileService.load(usdx_file)
            await self._initialize_song_from_usdx(song, usdx_file)
        except FileNotFoundError as e:
            logger.error("File not found during load: %s", txt_file)
            song.set_error(str(e))
        except Exception as e:  # pragma: no cover - unexpected errors
            logger.error("Error loading song %s: %s", txt_file, e, exc_info=True)
            song.set_error(str(e))

        # Load gap_info (multi-entry support uses txt basename)
        txt_basename = os.path.basename(txt_file)
        song.gap_info = GapInfoService.create_for_song_path(song.path, txt_basename)
        song.gap_info.owner = song
        try:
            logger.debug("Loading gap_info for %s", txt_file)
            if song.gap_info:
                await GapInfoService.load(song.gap_info)
                logger.debug("Gap_info loaded for %s", txt_file)
            else:
                logger.warning("gap_info not available for %s, duration_ms set to 0", song.txt_file)
        except Exception as e:  # pragma: no cover - unexpected errors
            logger.error("Failed to load gap_info for %s: %s", txt_file, e, exc_info=True)
            song.set_error(str(e))
            return song

        # Determine duration if still missing
        if (not song.duration_ms or song.duration_ms == 0) and song.audio_file and os.path.exists(song.audio_file):
            song.duration_ms = audio.get_audio_duration(song.audio_file, cancel_check)

        if song.status != SongStatus.ERROR:
            self.update_cache(song)

        return song

    async def _initialize_song_from_usdx(self, song: Song, usdx_file: USDXFile) -> None:
        """Populate song fields from USDX file."""
        if not os.path.exists(song.txt_file):
            raise FileNotFoundError(f"File not found: {song.txt_file}")

        logger.debug("Accessing USDX tags for %s", song.txt_file)
        song.title = usdx_file.tags.TITLE
        song.artist = usdx_file.tags.ARTIST
        song.audio = usdx_file.tags.AUDIO
        song.gap = usdx_file.tags.GAP
        song.bpm = usdx_file.tags.BPM
        song.start = usdx_file.tags.START
        song.is_relative = usdx_file.tags.RELATIVE
        song.notes = usdx_file.notes
        
        # Handle missing or invalid audio file
        if not song.audio:
            logger.warning("AUDIO tag is missing for %s", song.txt_file)
            song.status = SongStatus.MISSING_AUDIO
        else:
            song.audio_file = os.path.join(song.path, song.audio)
            if not os.path.exists(song.audio_file):
                logger.warning("Audio file not found for %s: %s", song.txt_file, song.audio_file)
                song.status = SongStatus.MISSING_AUDIO

        logger.debug("Updating status from gap_info for %s", song.txt_file)

    async def load_song_metadata_only(self, txt_file: str, cancel_check: Optional[Callable] = None) -> Song:
        """Load only metadata (tags + notes) without gap_info or status mutation."""
        logger.debug("Loading metadata only for %s", txt_file)
        song = Song(txt_file)

        if os.path.isdir(txt_file):
            logger.error("Expected file path but got directory: %s", txt_file)
            song.set_error("Invalid path: expected file, got directory")
            return song

        if not os.path.exists(txt_file):
            logger.error("File not found during metadata load: %s", txt_file)
            song.set_error(f"File not found: {txt_file}")
            return song

        try:
            usdx_file = USDXFile(txt_file)
            await USDXFileService.load(usdx_file)
            await self._initialize_song_from_usdx(song, usdx_file)
        except FileNotFoundError as e:
            logger.error("File not found during metadata load: %s", txt_file)
            song.set_error(str(e))
            return song
        except PermissionError:
            logger.error("Permission denied during metadata load: %s", txt_file)
            song.set_error(f"Permission denied: {txt_file}")
            return song
        except Exception as e:  # pragma: no cover - unexpected errors
            logger.error("Error loading song metadata %s: %s", txt_file, e, exc_info=True)
            song.set_error(str(e))
            return song

        if not song.duration_ms or song.duration_ms == 0:
            if song.audio_file and os.path.exists(song.audio_file):
                try:
                    song.duration_ms = audio.get_audio_duration(song.audio_file, cancel_check)
                except Exception as e:  # pragma: no cover - unexpected errors
                    logger.warning("Could not determine audio duration for %s: %s", txt_file, e)

        logger.debug("Metadata loaded for %s, status remains %s", txt_file, song.status)
        return song

    def get_notes(self, song: Song):  # type: ignore[override]
        """Return notes from USDX file."""
        try:
            usdx_file = USDXFile(song.txt_file)
            return USDXFileService.load_notes_only(usdx_file)
        except Exception as e:  # pragma: no cover - unexpected errors
            logger.error("Error getting notes for %s: %s", song.txt_file, e, exc_info=True)
            return []

    def delete_song(self, song: Song) -> bool:
        """Delete the song folder and remove from cache."""
        try:
            remove_cache_entry(song.txt_file)
            files.delete_folder(song.path)
            return True
        except Exception as e:  # pragma: no cover - unexpected errors
            logger.error("Error deleting song %s: %s", song.path, e, exc_info=True)
            return False

    def update_cache(self, song: Song) -> None:
        """Update the song cache entry if file exists."""
        try:
            if os.path.exists(song.txt_file):
                set_cache_entry(song.txt_file, song)
                logger.debug("Song cache updated: %s", song.txt_file)
        except Exception as e:  # pragma: no cover - unexpected errors
            logger.error("Error updating cache for %s: %s", song.txt_file, e, exc_info=True)

    async def save_gap_info(self, song: Song) -> None:
        """Persist gap info and refresh cache."""
        if song.gap_info:
            await GapInfoService.save(song.gap_info)
            self.update_cache(song)

    def normalize_audio(self, song: Song, normalization_level: float | None = None) -> None:
        """Mark a song as normalized and update its gap info."""
        if song.gap_info:
            GapInfoService.set_normalized(song.gap_info, normalization_level)
            self.update_cache(song)
