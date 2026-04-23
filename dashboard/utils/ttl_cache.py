"""TTL cache helper for dashboard — thread-safe in-memory cache with explicit expiry."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable

T = TypeVar("T")


@dataclass
class CacheStats:
    hits: int
    misses: int
    keys: int


class TTLCache[T]:
    def __init__(self, ttl: float) -> None:
        self._ttl = ttl
        self._lock = threading.Lock()
        self._store: dict[str, tuple[float, T]] = {}
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> T | None:
        with self._lock:
            if key in self._store:
                expiry, value = self._store[key]
                if time.monotonic() < expiry:
                    self._hits += 1
                    return value
                del self._store[key]
            self._misses += 1
            return None

    def set(self, key: str, value: T) -> None:
        with self._lock:
            self._store[key] = (time.monotonic() + self._ttl, value)

    def delete(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def stats(self) -> CacheStats:
        with self._lock:
            return CacheStats(hits=self._hits, misses=self._misses, keys=len(self._store))

    def wrap(self, fn: Callable[..., T]) -> Callable[..., T]:
        def cached(*args: object, **kwargs: object) -> T:
            key = str((args, kwargs))
            val = self.get(key)
            if val is None:
                val = fn(*args, **kwargs)
                self.set(key, val)
            return val

        def stats_fn() -> CacheStats:
            return self.stats()

        cached.stats = stats_fn  # type: ignore[attr-defined]
        return cached
