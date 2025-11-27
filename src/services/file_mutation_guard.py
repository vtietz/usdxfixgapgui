import threading
import time
from contextlib import contextmanager
from typing import Dict

from model.songs import normalize_path


class FileMutationGuard:
    """Tracks in-process file mutations to suppress watcher echo events."""

    _ACTIVE_SENTINEL = -1.0
    _lock = threading.Lock()
    _guarded_paths: Dict[str, float] = {}

    @classmethod
    @contextmanager
    def guard(cls, path: str, linger_seconds: float = 0.75):
        """Context manager shielding the given path while the block executes."""

        if not path:
            yield
            return

        key = normalize_path(path)
        cls._acquire(key)
        try:
            yield
        finally:
            cls._release(key, linger_seconds)

    @classmethod
    def is_guarded(cls, path: str) -> bool:
        if not path:
            return False

        key = normalize_path(path)
        now = time.monotonic()

        with cls._lock:
            expiry = cls._guarded_paths.get(key)
            if expiry is None:
                return False

            if expiry == cls._ACTIVE_SENTINEL:
                return True

            if expiry > now:
                return True

            # Expired - clean up entry
            cls._guarded_paths.pop(key, None)
            return False

    @classmethod
    def _acquire(cls, key: str):
        with cls._lock:
            cls._guarded_paths[key] = cls._ACTIVE_SENTINEL

    @classmethod
    def _release(cls, key: str, linger_seconds: float):
        expiry = time.monotonic() + max(linger_seconds, 0.0)
        with cls._lock:
            cls._guarded_paths[key] = expiry
