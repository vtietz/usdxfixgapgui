import logging
import os
from typing import Optional

from model.song import Song
from model.gap_info import GapInfo
from model.songs import normalize_path
from utils import files

logger = logging.getLogger(__name__)

TEXT_EXTENSIONS = {".txt"}
AUDIO_EXTENSIONS = {".mp3", ".m4a", ".ogg", ".flac", ".wav"}


class SongSignatureService:
    """Utility helpers for tracking and comparing song content signatures."""

    @staticmethod
    def capture_processed_signatures(
        song: Song,
        include_txt: bool = True,
        include_audio: bool = True,
    ) -> None:
        """Persist the current txt/audio signatures as the processed baseline."""

        gap_info: Optional[GapInfo] = song.gap_info if song else None
        if not song or not gap_info:
            return

        if include_txt and song.txt_file:
            gap_info.processed_txt_signature = files.build_file_signature(
                song.txt_file,
                include_hash=True,
            )

        if include_audio and song.audio_file:
            gap_info.processed_audio_signature = files.build_file_signature(song.audio_file)

    @staticmethod
    def has_meaningful_change(song: Song, changed_path: str) -> bool:
        """Check if a modified path differs from the last processed baseline."""

        if not song or not changed_path:
            return False

        _, ext = os.path.splitext(changed_path)
        ext = ext.lower()

        if ext in TEXT_EXTENSIONS:
            return SongSignatureService._txt_changed(song, changed_path)

        if ext in AUDIO_EXTENSIONS:
            return SongSignatureService._audio_changed(song, changed_path)

        return False

    @staticmethod
    def _txt_changed(song: Song, changed_path: str) -> bool:
        gap_info: Optional[GapInfo] = song.gap_info
        if not gap_info:
            return True

        stored_signature = gap_info.processed_txt_signature
        current_signature = files.build_file_signature(changed_path, include_hash=True)

        if stored_signature is None or current_signature is None:
            return True

        match = files.signatures_match(current_signature, stored_signature)
        logger.debug(
            "Txt change comparison for %s: match=%s", os.path.basename(changed_path), match
        )
        return not match

    @staticmethod
    def _audio_changed(song: Song, changed_path: str) -> bool:
        gap_info: Optional[GapInfo] = song.gap_info
        if not gap_info or not song.audio_file:
            return True

        if normalize_path(song.audio_file) != normalize_path(changed_path):
            # Different audio file within folder; rely on txt change to reconcile.
            return False

        stored_signature = gap_info.processed_audio_signature
        current_signature = files.build_file_signature(changed_path)

        if stored_signature is None or current_signature is None:
            return True

        match = files.signatures_match(current_signature, stored_signature)
        logger.debug(
            "Audio change comparison for %s: match=%s", os.path.basename(changed_path), match
        )
        return not match
