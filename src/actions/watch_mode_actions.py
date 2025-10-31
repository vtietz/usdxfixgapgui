"""
WatchModeActions: Actions for controlling watch mode functionality.

Provides start/stop/status methods for filesystem watching with automated
cache updates and gap detection.
"""

import logging
from typing import Optional
from PySide6.QtCore import Signal

from actions.base_actions import BaseActions
from managers.watch_mode_controller import WatchModeController
from model.song import Song

logger = logging.getLogger(__name__)


class WatchModeActions(BaseActions):
    """Actions for watch mode control"""

    # Signal emitted when watch mode state changes
    watch_mode_enabled_changed = Signal(bool)
    # Signal emitted when initial scan completes (for UI enablement)
    initial_scan_completed = Signal()

    def __init__(self, data):
        super().__init__(data)
        self._watch_controller: Optional[WatchModeController] = None
        self._is_initial_scan_complete = False

        # Connect to loading finished signal
        self.data.is_loading_songs_changed.connect(self._on_loading_changed)

        # Connect to gap detection finished to mark tasks complete
        self.data.gap_detection_finished.connect(self._on_gap_detection_finished)

    def _on_loading_changed(self, is_loading: bool):
        """Track when initial scan completes."""
        if not is_loading and not self._is_initial_scan_complete:
            self._is_initial_scan_complete = True
            self.initial_scan_completed.emit()
            logger.info("Initial scan completed - watch mode can now be enabled")

    def _on_gap_detection_finished(self, song: Song):
        """Mark gap detection as complete in scheduler."""
        if self._watch_controller:
            self._watch_controller.mark_detection_complete(song)

    def can_enable_watch_mode(self) -> bool:
        """
        Check if watch mode can be enabled.

        Returns:
            True if directory is set and initial scan is complete
        """
        return self.data.directory is not None and self.data.directory != "" and self._is_initial_scan_complete

    def is_watch_mode_enabled(self) -> bool:
        """
        Check if watch mode is currently enabled.

        Returns:
            True if watch mode is active
        """
        return self._watch_controller is not None and self._watch_controller.is_running()

    def start_watch_mode(self) -> bool:
        """
        Start watch mode.

        Returns:
            True if started successfully, False otherwise
        """
        if not self.can_enable_watch_mode():
            logger.warning("Cannot start watch mode - requirements not met")
            return False

        if self.is_watch_mode_enabled():
            logger.warning("Watch mode already enabled")
            return False

        try:
            # Parse ignore patterns from config
            ignore_patterns_str = self.config.watch_ignore_patterns
            ignore_patterns = set(p.strip() for p in ignore_patterns_str.split(",") if p.strip())

            # Create controller
            self._watch_controller = WatchModeController(
                directory=self.data.directory,
                debounce_ms=self.config.watch_debounce_ms,
                ignore_patterns=ignore_patterns,
                worker_queue_add_task=self.worker_queue.add_task,
                start_gap_detection=self._start_gap_detection,
                songs_get_by_txt_file=self.data.songs.get_by_txt_file,
                songs_get_by_path=self.data.songs.get_by_path,
                songs_add=self.data.songs.add,
                songs_remove_by_txt_file=self.data.songs.remove_by_txt_file,
            )

            # Connect error signal
            self._watch_controller.error_occurred.connect(self._on_watch_error)

            # Start watching
            success = self._watch_controller.start()

            if success:
                logger.info("Watch mode started successfully")
                self.watch_mode_enabled_changed.emit(True)
            else:
                logger.error("Failed to start watch mode")
                self._watch_controller = None

            return success

        except Exception as e:
            logger.error(f"Error starting watch mode: {e}", exc_info=True)
            self._watch_controller = None
            return False

    def stop_watch_mode(self):
        """Stop watch mode."""
        if not self.is_watch_mode_enabled():
            return

        try:
            self._watch_controller.stop()
            self._watch_controller = None

            logger.info("Watch mode stopped")
            self.watch_mode_enabled_changed.emit(False)

        except Exception as e:
            logger.error(f"Error stopping watch mode: {e}", exc_info=True)

    def toggle_watch_mode(self) -> bool:
        """
        Toggle watch mode on/off.

        Returns:
            New state (True if enabled, False if disabled)
        """
        if self.is_watch_mode_enabled():
            self.stop_watch_mode()
            return False
        else:
            return self.start_watch_mode()

    def _start_gap_detection(self, song: Song):
        """Start gap detection for a song (called by scheduler)."""
        try:
            # Import here to avoid circular dependency
            from actions.gap_actions import GapActions

            gap_actions = GapActions(self.data)
            gap_actions._detect_gap(song)

        except Exception as e:
            logger.error(f"Error starting gap detection for {song}: {e}", exc_info=True)

    def _on_watch_error(self, error: str):
        """Handle watch mode error."""
        logger.error(f"Watch mode error: {error}")
        # Could emit a signal here for UI notification if needed
