"""
DirectoryWatcher: OS-native filesystem monitoring using watchdog.

Monitors a directory tree for changes and emits normalized events.
Uses platform-specific backends (Windows ReadDirectoryChangesW, macOS FSEvents, Linux inotify).
"""

import logging
import os
from enum import Enum
from typing import Optional, Set
from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent

logger = logging.getLogger(__name__)


class WatchEventType(Enum):
    """Normalized filesystem event types"""
    CREATED = "created"
    DELETED = "deleted"
    MODIFIED = "modified"
    MOVED = "moved"


@dataclass
class WatchEvent:
    """Normalized filesystem event"""
    event_type: WatchEventType
    path: str
    src_path: Optional[str] = None  # For moved events
    is_directory: bool = False


class DirectoryWatcher(QObject):
    """
    Monitors a directory tree for filesystem changes using OS-native backends.

    Signals:
        file_event: Emitted when a filesystem event occurs (WatchEvent)
        error_occurred: Emitted when an error occurs (str)
        started: Emitted when watching starts
        stopped: Emitted when watching stops
    """

    file_event = Signal(object)  # WatchEvent
    error_occurred = Signal(str)
    started = Signal()
    stopped = Signal()

    def __init__(self, ignore_patterns: Optional[Set[str]] = None):
        """
        Initialize DirectoryWatcher.

        Args:
            ignore_patterns: Set of file patterns to ignore (e.g., {'.tmp', '~', '.crdownload'})
        """
        super().__init__()
        self._observer: Optional[Observer] = None
        self._watch_path: Optional[str] = None
        self._ignore_patterns = ignore_patterns or set()
        self._event_handler: Optional[_FileSystemEventHandler] = None

    def start_watching(self, path: str) -> bool:
        """
        Start watching a directory.

        Args:
            path: Directory path to watch

        Returns:
            True if watching started successfully, False otherwise
        """
        if self._observer is not None:
            logger.warning(f"Already watching {self._watch_path}")
            return False

        if not os.path.isdir(path):
            logger.error(f"Cannot watch non-existent directory: {path}")
            self.error_occurred.emit(f"Directory does not exist: {path}")
            return False

        try:
            self._watch_path = path
            self._event_handler = _FileSystemEventHandler(
                self._ignore_patterns,
                self._on_event
            )

            self._observer = Observer()
            self._observer.schedule(self._event_handler, path, recursive=True)
            self._observer.start()

            backend_name = type(self._observer).__name__
            logger.info(f"Directory watcher started on {path} using {backend_name}")
            self.started.emit()
            return True

        except Exception as e:
            logger.error(f"Failed to start directory watcher: {e}", exc_info=True)
            self.error_occurred.emit(f"Failed to start watching: {e}")
            self._cleanup()
            return False

    def stop_watching(self):
        """Stop watching the directory."""
        if self._observer is None:
            return

        try:
            self._observer.stop()
            self._observer.join(timeout=5.0)
            logger.info(f"Directory watcher stopped for {self._watch_path}")

        except Exception as e:
            logger.error(f"Error stopping directory watcher: {e}", exc_info=True)

        finally:
            self._cleanup()
            self.stopped.emit()

    def is_watching(self) -> bool:
        """Check if currently watching a directory."""
        return self._observer is not None and self._observer.is_alive()

    def _on_event(self, event: WatchEvent):
        """Internal callback for filesystem events."""
        try:
            self.file_event.emit(event)
        except Exception as e:
            logger.error(f"Error handling file event: {e}", exc_info=True)
            self.error_occurred.emit(f"Error handling event: {e}")

    def _cleanup(self):
        """Clean up resources."""
        self._observer = None
        self._watch_path = None
        self._event_handler = None


class _FileSystemEventHandler(FileSystemEventHandler):
    """Internal event handler that normalizes watchdog events."""

    def __init__(self, ignore_patterns: Set[str], callback):
        super().__init__()
        self._ignore_patterns = ignore_patterns
        self._callback = callback

    def _should_ignore(self, path: str) -> bool:
        """Check if path should be ignored based on patterns."""
        if not self._ignore_patterns:
            return False

        path_lower = path.lower()
        return any(
            path_lower.endswith(pattern.lower())
            for pattern in self._ignore_patterns
        )

    def on_created(self, event: FileSystemEvent):
        """Handle created events."""
        if self._should_ignore(event.src_path):
            return

        watch_event = WatchEvent(
            event_type=WatchEventType.CREATED,
            path=event.src_path,
            is_directory=event.is_directory
        )
        self._callback(watch_event)

    def on_deleted(self, event: FileSystemEvent):
        """Handle deleted events."""
        if self._should_ignore(event.src_path):
            return

        watch_event = WatchEvent(
            event_type=WatchEventType.DELETED,
            path=event.src_path,
            is_directory=event.is_directory
        )
        self._callback(watch_event)

    def on_modified(self, event: FileSystemEvent):
        """Handle modified events."""
        if self._should_ignore(event.src_path):
            return

        # Ignore directory modifications (we only care about file content changes)
        if event.is_directory:
            return

        watch_event = WatchEvent(
            event_type=WatchEventType.MODIFIED,
            path=event.src_path,
            is_directory=event.is_directory
        )
        self._callback(watch_event)

    def on_moved(self, event: FileSystemEvent):
        """Handle moved/renamed events."""
        if hasattr(event, 'dest_path'):
            dest_path = event.dest_path
        else:
            dest_path = event.src_path

        if self._should_ignore(event.src_path) or self._should_ignore(dest_path):
            return

        watch_event = WatchEvent(
            event_type=WatchEventType.MOVED,
            path=dest_path,
            src_path=event.src_path,
            is_directory=event.is_directory
        )
        self._callback(watch_event)
