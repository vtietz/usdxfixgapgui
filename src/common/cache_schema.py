"""Cache entry schema helpers for the SQLite song cache."""

from __future__ import annotations

import logging
import pickle
from dataclasses import dataclass
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass
class CacheEnvelope:
    """Wrapper stored in the cache to track per-entry schema versioning."""

    schema_version: int
    payload_type: str
    payload: Any


# Per-entry payload schema (independent from SQLite layout)
CACHE_ENTRY_VERSION = 1
PAYLOAD_TYPE_SONG = "song"


def _legacy_payload_migration(payload: Any) -> Any:
    """Migration hook for legacy payloads without envelopes."""

    # We rely on Song.__setstate__ to normalize legacy structures.
    # This hook simply preserves backwards compatibility and can host
    # future payload transformations without forcing Demucs reruns.
    return payload


_CACHE_ENTRY_MIGRATIONS: dict[int, Callable[[Any], Any]] = {
    0: _legacy_payload_migration,  # Legacy blobs -> envelope v1
}


def _run_entry_migrations(payload: Any, version: int) -> Any | None:
    """Apply sequential migrations until the payload reaches the current schema."""

    current_version = version
    upgraded = payload

    while current_version < CACHE_ENTRY_VERSION:
        migration = _CACHE_ENTRY_MIGRATIONS.get(current_version)
        if migration is None:
            logger.error(
                "Missing migration path for cache payload (entry version %s, target %s)",
                current_version,
                CACHE_ENTRY_VERSION,
            )
            return None
        upgraded = migration(upgraded)
        current_version += 1

    return upgraded


def serialize_payload(payload: Any, payload_type: str = PAYLOAD_TYPE_SONG) -> bytes:
    """Serialize a payload into an envelope blob."""

    envelope = CacheEnvelope(schema_version=CACHE_ENTRY_VERSION, payload_type=payload_type, payload=payload)
    return pickle.dumps(envelope)


def deserialize_payload(file_path: str, data_blob: bytes) -> tuple[Any | None, bool]:
    """Return (payload, migrated) from raw cache bytes."""

    try:
        obj = pickle.loads(data_blob)
    except Exception as exc:
        logger.error("Failed to deserialize cache payload for %s: %s", file_path, exc)
        return None, False

    if isinstance(obj, CacheEnvelope):
        payload = obj.payload
        version = obj.schema_version
    else:
        payload = obj
        version = 0

    if version > CACHE_ENTRY_VERSION:
        logger.error(
            "Cache entry for %s uses schema v%s but this build only supports up to v%s",
            file_path,
            version,
            CACHE_ENTRY_VERSION,
        )
        return None, False

    if version < CACHE_ENTRY_VERSION:
        upgraded = _run_entry_migrations(payload, version)
        if upgraded is None:
            return None, False
        return upgraded, True

    return payload, False
