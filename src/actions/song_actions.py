import logging
import os
from typing import List, Set
from actions.base_actions import BaseActions
from model.song import Song, SongStatus
from workers.reload_song_worker import ReloadSongWorker
from services.usdx_file_service import USDXFileService
from services.song_service import SongService
from services.gap_state import GapState
from model.usdx_file import USDXFile
from utils.audio import get_audio_duration
from utils.run_async import run_async

logger = logging.getLogger(__name__)

# Global registry of in-flight reloads across all SongActions instances to prevent duplicate reload tasks
_GLOBAL_INFLIGHT_RELOADS: Set[str] = set()

class SongActions(BaseActions):
    """Song selection and management actions"""

    def __init__(self, data):
        super().__init__(data)
        # In-flight reloads are tracked globally to prevent duplicates across different action instances

    def set_selected_songs(self, songs: List[Song]):
        logger.debug(f"Setting selected songs: {[s.title for s in songs]}")
        self.data.selected_songs = songs

        # Track B: Create GapState for single selection
        if len(songs) == 1:
            song = songs[0]
            self.data.gap_state = GapState.from_song(
                current_gap=song.gap_info.original_gap if song.gap_info else 0,
                detected_gap=song.gap_info.detected_gap if song.gap_info else None
            )
            if self.data.gap_state:  # Add type guard
                logger.debug(f"Created GapState for {song.title}: current={self.data.gap_state.current_gap_ms}, detected={self.data.gap_state.detected_gap_ms}")
        else:
            # Multi-selection or no selection
            self.data.gap_state = None
            logger.debug("Cleared GapState (multi/no selection)")

        # Removed waveform creation here - will be handled by MediaPlayerComponent

    def _mark_reload_started(self, song_path: str):
        """Mark a song path as having an in-flight reload to prevent duplicate tasks."""
        _GLOBAL_INFLIGHT_RELOADS.add(song_path)

    def _mark_reload_finished(self, song_path: str):
        """Clear the in-flight flag when a reload worker finishes, errors, or is canceled."""
        _GLOBAL_INFLIGHT_RELOADS.discard(song_path)


    def reload_song(self, specific_song=None):
        """
        Reload a song or songs from disk.
        If specific_song is provided, only loads that song.
        Otherwise loads all selected songs.
        Prevents duplicate concurrent reload tasks per song by path.
        """
        # Resolve target songs
        songs_to_load = [specific_song] if specific_song else self.data.selected_songs

        if not songs_to_load:
            logger.error("No songs selected to reload.")
            return

        logger.info(f"Reloading {len(songs_to_load)} songs.")

        for song in songs_to_load:
            # Skip if already scheduled/running to avoid duplicate tasks (global guard)
            if song.path in _GLOBAL_INFLIGHT_RELOADS:
                logger.debug(f"Skip duplicate reload for already in-flight song: {song.path}")
                continue

            logger.info(f"Reloading song {song.path}")
            try:
                # Reset ERROR or PROCESSING states before reloading
                # This allows users to retry after errors or stuck processing states
                if song.status in (SongStatus.ERROR, SongStatus.PROCESSING):
                    logger.info(f"Resetting status from {song.status} to NOT_PROCESSED for reload")
                    song.clear_error()  # Clears error message and resets to NOT_PROCESSED

                # Mark as queued so viewport lazy loader does not re-queue it
                song.status = SongStatus.QUEUED
                self.data.songs.updated.emit(song)

                # Extract directory from song.path (which should be the full file path)
                song_directory = os.path.dirname(song.path)

                # Create the new ReloadSongWorker for this specific song reload
                worker = ReloadSongWorker(song.path, song_directory)

                # Mark inflight before starting
                self._mark_reload_started(song.path)

                # Update song status to PROCESSING on start
                worker.signals.started.connect(lambda s=song: (
                    setattr(s, 'status', SongStatus.PROCESSING),
                    self.data.songs.updated.emit(s)
                ))

                # When the worker reloads the song, clear inflight and update model
                worker.signals.songReloaded.connect(lambda reloaded_song, p=song.path: (
                    self._mark_reload_finished(p),
                    self._on_song_loaded(reloaded_song)
                ))

                # Clear inflight on error/cancel/finish to avoid stuck state
                worker.signals.error.connect(lambda e, s=song, p=song.path: (
                    self._mark_reload_finished(p),
                    self._on_song_worker_error(s, e)
                ))
                worker.signals.canceled.connect(lambda p=song.path: self._mark_reload_finished(p))
                worker.signals.finished.connect(lambda p=song.path: self._mark_reload_finished(p))

                # Add the task to the worker queue (start immediately)
                self.worker_queue.add_task(worker, True)

            except Exception as e:
                # Ensure we clear inflight in case of immediate exception
                self._mark_reload_finished(song.path)
                song.set_error(str(e))
                logger.exception(f"Error setting up song reload: {e}")
                self.data.songs.updated.emit(song)

    def reload_song_light(self, specific_song=None):
        """
        Light reload: loads only metadata (USDX tags and notes) without gap_info.
        Does NOT change song.status, does NOT queue workers, does NOT create waveforms.
        Used for viewport lazy-loading to avoid triggering heavy processing.

        Now fully asynchronous - does NOT block GUI thread.

        If specific_song is provided, only loads that song.
        Otherwise loads all selected songs.
        """
        # Resolve target songs
        songs_to_load = [specific_song] if specific_song else self.data.selected_songs

        if not songs_to_load:
            logger.debug("No songs to light-reload.")
            return

        logger.debug(f"Light-reloading {len(songs_to_load)} songs (metadata only).")

        for song in songs_to_load:
            # Skip if already has data loaded (title, artist, notes)
            if song.title and song.artist and song.notes:
                logger.debug(f"Skip light-reload for already loaded song: {song.title}")
                continue

            logger.debug(f"Light-reloading metadata for {song.txt_file}")

            # Use run_async with callback to avoid blocking GUI thread
            song_service = SongService()
            run_async(
                song_service.load_song_metadata_only(song.txt_file),
                callback=lambda reloaded_song, s=song: self._apply_light_reload(s, reloaded_song)
            )

    def _apply_light_reload(self, song: Song, reloaded_song: Song):
        """
        Apply metadata from light reload to the song object.
        Called asynchronously after metadata-only load completes.
        Does NOT change Song.status for success path.
        """
        try:
            if reloaded_song and reloaded_song.status != SongStatus.ERROR:
                # Update the existing song object with metadata
                song.title = reloaded_song.title
                song.artist = reloaded_song.artist
                song.audio = reloaded_song.audio
                song.gap = reloaded_song.gap
                song.bpm = reloaded_song.bpm
                song.start = reloaded_song.start
                song.is_relative = reloaded_song.is_relative
                song.notes = reloaded_song.notes
                song.audio_file = reloaded_song.audio_file
                song.duration_ms = reloaded_song.duration_ms

                # DO NOT set gap_info - keeps status unchanged
                # DO NOT change status - remains NOT_PROCESSED

                logger.debug(f"Light-reload complete for {song.title}, status unchanged: {song.status}")
                self.data.songs.updated.emit(song)
            else:
                if reloaded_song and reloaded_song.status == SongStatus.ERROR:
                    # Only set error if error_message is not None
                    if reloaded_song.error_message:
                        song.set_error(reloaded_song.error_message)
                    else:
                        song.set_error("Unknown error during reload")
                    self.data.songs.updated.emit(song)

        except Exception as e:
            song.set_error(str(e))
            logger.exception(f"Error applying light reload: {e}")
            self.data.songs.updated.emit(song)

    async def load_notes_for_song_async(self, song: Song):
        """Load just the notes for a song without fully reloading it.
        Also compute per-note start/end/duration in milliseconds so waveform rendering works.

        NOTE: This is async and should be called via run_async, not run_sync.
        Prefer using reload_song_light() for viewport operations.
        """
        if not song:
            logger.error("No song provided to load notes for")
            return

        logger.info(f"Loading notes for {song}")

        try:
            # Use USDXFile and USDXFileService directly to load just the notes
            usdx_file = USDXFile(song.txt_file)
            song.notes = await USDXFileService.load_notes_only(usdx_file)
            logger.debug(f"Notes loaded for song: {song.title}, count: {len(song.notes) if song.notes else 0}")

            # Compute note timing (ms) required by waveform drawing if we have BPM information
            if song.notes and song.bpm and song.bpm > 0:
                try:
                    beats_per_ms = (song.bpm / 60 / 1000) * 4
                    for note in song.notes:
                        # Guard against missing fields
                        if note.StartBeat is None or note.Length is None:
                            # Skip malformed notes
                            continue
                        if song.is_relative:
                            note.start_ms = note.StartBeat / beats_per_ms
                            note.end_ms = (note.StartBeat + note.Length) / beats_per_ms
                        else:
                            note.start_ms = song.gap + (note.StartBeat / beats_per_ms)
                            note.end_ms = song.gap + ((note.StartBeat + note.Length) / beats_per_ms)
                        note.duration_ms = note.end_ms - note.start_ms
                    logger.debug(f"Computed note timings for {song.title} using bpm={song.bpm}, gap={song.gap}, relative={song.is_relative}")
                except Exception as timing_err:
                    logger.warning(f"Failed computing note timings for {song.title}: {timing_err}")

            # Notify that the song was updated
            self.data.songs.updated.emit(song)

        except Exception as e:
            logger.error(f"Error loading notes for song {song.title}: {e}", exc_info=True)
            song.error_message = str(e)
            self.data.songs.updated.emit(song)

    def _on_song_loaded(self, reloaded_song):
        """Handle a reloaded song from the worker"""
        # Find the matching song in our data model
        for i, song in enumerate(self.data.songs.songs):
            if song.path == reloaded_song.path:
                # Instead of replacing the song object, update its attributes
                # This avoids 'Songs' object does not support item assignment error
                self._update_song_attributes(song, reloaded_song)

                # Regenerate waveforms after reload
                # This ensures waveforms reflect the current song data
                from actions.audio_actions import AudioActions
                audio_actions = AudioActions(self.data)
                audio_actions._create_waveforms(song, overwrite=True, use_queue=True)
                logger.info(f"Queued waveform regeneration after reload for {song.title}")

                # Notify update after successful reload
                self.data.songs.updated.emit(song)

                # If this was a selected song, update the selection
                if song in self.data.selected_songs:
                    # No need to replace in the selection array since we modified the object in-place
                    # Just refresh the selection to trigger UI updates
                    self.set_selected_songs(self.data.selected_songs)

                logger.info(f"Successfully reloaded {song}")
                break

    def _update_song_attributes(self, target_song: Song, source_song: Song):
        """Transfer all relevant attributes from source_song to target_song"""
        # Copy all attributes from source to target song object
        attributes_to_copy = [
            'title', 'artist', 'audio', 'gap', 'bpm', 'start', 'is_relative',
            'txt_file', 'audio_file', 'relative_path', 'usdb_id', 'notes'
        ]

        for attr in attributes_to_copy:
            if hasattr(source_song, attr):
                try:
                    # First check if the attribute is accessible via setattr
                    setattr(target_song, attr, getattr(source_song, attr))
                except AttributeError:
                    # If we can't set it directly, log this issue
                    logger.warning(f"Could not set attribute {attr} on song {target_song.title}")

        # Copy status and error_message after other attributes to ensure they're properly set
        if hasattr(source_song, 'status'):
            target_song.status = source_song.status
        if hasattr(source_song, 'error_message'):
            target_song.error_message = source_song.error_message

        # Handle special objects like gap_info
        if hasattr(source_song, 'gap_info') and source_song.gap_info:
            try:
                target_song.gap_info = source_song.gap_info
            except AttributeError:
                # If gap_info is a property with no setter, try to update its contents
                logger.warning(f"Could not set gap_info directly, attempting to update contents")
                if hasattr(target_song, 'gap_info') and target_song.gap_info is not None:
                    # Copy attributes from source gap_info to target gap_info
                    for gap_attr in dir(source_song.gap_info):
                        if not gap_attr.startswith('_') and gap_attr != 'owner':  # Skip private attributes and owner
                            try:
                                setattr(target_song.gap_info, gap_attr,
                                        getattr(source_song.gap_info, gap_attr))
                            except AttributeError:
                                pass

                    # Explicitly update duration from gap_info if available
                    if source_song.gap_info.duration:
                        target_song.duration_ms = int(source_song.gap_info.duration)  # Convert to int

        # Double-check duration after all other operations
        if target_song.duration_ms == 0 and target_song.audio_file and os.path.exists(target_song.audio_file):
            try:
                duration = get_audio_duration(target_song.audio_file)
                if duration is not None:
                    target_song.duration_ms = int(duration)  # Convert float to int
                    logger.info(f"Fallback method: set duration to {target_song.duration_ms}ms from audio file")
            except Exception as e:
                logger.warning(f"Could not load duration from audio file: {e}")

    def delete_selected_song(self):
        """
        Delete selected songs following architecture principles:
        - Actions orchestrate between services and models
        - Services handle business logic
        - Models only update their own state via methods
        - Signals emitted through data model, not directly from actions
        """
        selected_songs = self.data.selected_songs
        if not selected_songs:
            logger.error("No songs selected to delete.")
            return

        logger.info(f"Attempting to delete {len(selected_songs)} songs.")
        # Confirmation should happen in the UI layer (MenuBar) before calling this
        songs_to_remove = list(selected_songs) # Copy list as we modify the source
        successfully_deleted = []

        # Use service for deletion logic
        song_service = SongService()

        for song in songs_to_remove:
            logger.info(f"Deleting song {song.path}")
            try:
                if song_service.delete_song(song):  # Service handles the deletion
                    successfully_deleted.append(song)
                    logger.info(f"Successfully deleted song {song.path}")
                else:
                    # Delete returned False - let model handle its state
                    song.set_error("Failed to delete song files")
                    self.data.songs.updated.emit(song)  # Signal via data model
                    logger.error(f"Failed to delete song {song.path}")
            except Exception as e:
                # Exception occurred - let model handle its state
                song.set_error(f"Delete error: {str(e)}")
                self.data.songs.updated.emit(song)  # Signal via data model
                logger.error(f"Exception deleting song {song.path}: {e}")

        # Only remove successfully deleted songs from the list
        for song in successfully_deleted:
            try:
                self.data.songs.remove(song)
            except ValueError:
                # Song was already removed somehow
                pass

        # After attempting deletion, clear the selection
        self.set_selected_songs([])
        # Explicitly trigger a list change signal
        self.data.songs.list_changed()
