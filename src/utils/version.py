"""Utilities for retrieving the application version string."""

from __future__ import annotations

import os
import threading
from pathlib import Path

from utils.files import resource_path

_version_cache: str | None = None
_version_lock = threading.Lock()


def get_version() -> str:
    """Return the application version string, cached after first read."""
    global _version_cache
    if _version_cache is not None:
        return _version_cache

    with _version_lock:
        if _version_cache is not None:
            return _version_cache

        candidate_paths = [
            resource_path("VERSION"),
            Path(__file__).resolve().parents[2] / "VERSION",
            Path.cwd() / "VERSION",
        ]
        for path in candidate_paths:
            try:
                if path and os.path.exists(path):
                    with open(path, "r", encoding="utf-8") as handle:
                        content = handle.read().strip()
                        if content:
                            _version_cache = content
                            return _version_cache
            except Exception:
                continue

        _version_cache = "unknown"
        return _version_cache
