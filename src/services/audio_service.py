"""
Audio Service - Facade for audio playback operations.

Provides a simplified interface for audio playback with support for:
- Original and extracted (vocals) audio sources
- Play/pause/stop controls
- Position seeking and gap jumping
- Preloading for responsive playback
- Playback state notifications
"""

import logging
from enum import Enum
from typing import Optional, Callable
from pathlib import Path

logger = logging.getLogger(__name__)


class AudioSource(Enum):
    """Audio source types."""
    ORIGINAL = "original"
    EXTRACTED = "extracted"
    BOTH = "both"  # Future: overlay both sources


class AudioService:
    """
    Facade for audio playback operations.

    Wraps existing PlayerController to provide a cleaner API
    for the UI redesign while maintaining compatibility with
    existing audio infrastructure.
    """

    def __init__(self, player_controller):
        """
        Initialize AudioService.

        Args:
            player_controller: Existing PlayerController instance
        """
        self._player = player_controller
        self._current_source = AudioSource.ORIGINAL
        self._current_song = None
        self._next_song = None
        self._position_ms = 0
        self._is_playing = False

        # Callbacks
        self._playback_change_callbacks: list[Callable] = []

        # Connect to player signals
        self._player.position_changed.connect(self._on_position_changed)
        self._player.is_playing_changed.connect(self._on_playing_changed)

    @property
    def source(self) -> AudioSource:
        """Get current audio source."""
        return self._current_source

    @property
    def is_playing(self) -> bool:
        """Check if audio is currently playing."""
        return self._is_playing

    @property
    def position_ms(self) -> int:
        """Get current playback position in milliseconds."""
        return self._position_ms

    def set_source(self, source: AudioSource) -> None:
        """
        Set audio source (original or extracted vocals).

        Args:
            source: AudioSource.ORIGINAL or AudioSource.EXTRACTED

        Note:
            AudioSource.BOTH is not yet implemented
        """
        if source == AudioSource.BOTH:
            logger.warning("AudioSource.BOTH not yet implemented, using ORIGINAL")
            source = AudioSource.ORIGINAL

        if source == self._current_source:
            return

        old_source = self._current_source
        self._current_source = source

        # Reload current song with new source
        if self._current_song:
            self._load_for_source(self._current_song, source)

        logger.debug(f"Audio source changed: {old_source.value} -> {source.value}")
        self._notify_playback_change()

    def play(self) -> None:
        """Start or resume playback."""
        self._player.play()

    def pause(self) -> None:
        """Pause playback."""
        if self._is_playing:
            self._player.play()  # play() toggles, so this pauses

    def stop(self) -> None:
        """Stop playback and reset position."""
        self._player.stop()

    def seek_ms(self, position_ms: int) -> None:
        """
        Seek to specific position.

        Args:
            position_ms: Position in milliseconds
        """
        self._player.media_player.setPosition(position_ms)
        logger.debug(f"Seeked to {position_ms}ms")

    def jump_to_current_gap(self, gap_ms: int) -> None:
        """
        Jump to current gap position.

        Args:
            gap_ms: Gap position in milliseconds
        """
        self.seek_ms(gap_ms)
        logger.debug(f"Jumped to current gap: {gap_ms}ms")

    def jump_to_detected_gap(self, gap_ms: int) -> None:
        """
        Jump to detected gap position.

        Args:
            gap_ms: Detected gap position in milliseconds
        """
        self.seek_ms(gap_ms)
        logger.debug(f"Jumped to detected gap: {gap_ms}ms")

    def preload(self, song, next_song=None) -> None:
        """
        Preload audio for current and next song.

        Args:
            song: Current song to load
            next_song: Optional next song to preload for instant transition
        """
        self._current_song = song
        self._next_song = next_song

        if song:
            self._load_for_source(song, self._current_source)
            logger.debug(f"Preloaded song: {song.name if hasattr(song, 'name') else song}")

        # Future: preload next_song in background
        if next_song:
            logger.debug(f"Next song queued: {next_song.name if hasattr(next_song, 'name') else next_song}")

    def subscribe_on_playback_change(self, callback: Callable[[], None]) -> None:
        """
        Subscribe to playback state changes.

        Args:
            callback: Function to call when playback state changes
        """
        if callback not in self._playback_change_callbacks:
            self._playback_change_callbacks.append(callback)

    def unsubscribe_on_playback_change(self, callback: Callable[[], None]) -> None:
        """
        Unsubscribe from playback state changes.

        Args:
            callback: Function to remove from callbacks
        """
        if callback in self._playback_change_callbacks:
            self._playback_change_callbacks.remove(callback)

    def _load_for_source(self, song, source: AudioSource) -> None:
        """
        Load audio file for given source.

        Args:
            song: Song object with audio_file/vocals_file paths
            source: AudioSource to load
        """
        if source == AudioSource.ORIGINAL:
            self._player.audio_mode()
            if hasattr(song, 'audio_file') and song.audio_file:
                self._player.load_media(song.audio_file)
        elif source == AudioSource.EXTRACTED:
            self._player.vocals_mode()
            if hasattr(song, 'vocals_file') and song.vocals_file:
                self._player.load_media(song.vocals_file)
            else:
                logger.warning(f"No vocals file available for {song}")
                # Fall back to original
                self._current_source = AudioSource.ORIGINAL
                self._player.audio_mode()
                if hasattr(song, 'audio_file') and song.audio_file:
                    self._player.load_media(song.audio_file)

    def _on_position_changed(self, position_ms: int) -> None:
        """Handle position change from player."""
        self._position_ms = position_ms
        # Don't notify on every position change (too frequent)
        # UI can poll position_ms property if needed

    def _on_playing_changed(self, is_playing: bool) -> None:
        """Handle playing state change from player."""
        self._is_playing = is_playing
        self._notify_playback_change()

    def _notify_playback_change(self) -> None:
        """Notify all subscribers of playback state change."""
        for callback in self._playback_change_callbacks:
            try:
                callback()
            except Exception as e:
                logger.error(f"Error in AudioService callback: {e}")
