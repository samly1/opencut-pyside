from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class _CacheEntry:
    value: Any
    expires_at: float | None


class CacheStore:
    def __init__(self, default_ttl_seconds: float | None = None) -> None:
        self._store: dict[str, _CacheEntry] = {}
        self._default_ttl = default_ttl_seconds

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        if entry.expires_at is not None and time.monotonic() > entry.expires_at:
            del self._store[key]
            return None
        return entry.value

    def set(self, key: str, value: Any, ttl_seconds: float | None = None) -> None:
        ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl
        expires_at = time.monotonic() + ttl if ttl is not None else None
        self._store[key] = _CacheEntry(value=value, expires_at=expires_at)

    def has(self, key: str) -> bool:
        return self.get(key) is not None

    def delete(self, key: str) -> bool:
        if key in self._store:
            del self._store[key]
            return True
        return False

    def clear(self) -> None:
        self._store.clear()

    def size(self) -> int:
        self._evict_expired()
        return len(self._store)

    def _evict_expired(self) -> None:
        now = time.monotonic()
        expired_keys = [
            key for key, entry in self._store.items()
            if entry.expires_at is not None and now > entry.expires_at
        ]
        for key in expired_keys:
            del self._store[key]
