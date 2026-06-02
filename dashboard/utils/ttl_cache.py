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
    """Snapshot of TTLCache hit/miss counters and current key count.

    Attributes:
        hits: Total number of successful cache lookups since creation.
        misses: Total number of cache lookups that found no valid entry.
        keys: Current number of non-expired keys held in the store.
    """

    hits: int
    misses: int
    keys: int


class TTLCache[T]:
    """Thread-safe in-memory key/value cache with per-entry time-to-live expiry.

    Attributes:
        _ttl: Seconds after insertion before a cached entry is considered expired.
        _lock: Mutex protecting all reads and writes to the internal store.
        _store: Mapping from string key to ``(expiry_monotonic, value)`` pairs.
        _hits: Cumulative count of successful cache hits since instantiation.
        _misses: Cumulative count of cache misses since instantiation.
    """

    def __init__(self, ttl: float) -> None:
        self._ttl = ttl
        self._lock = threading.Lock()
        self._store: dict[str, tuple[float, T]] = {}
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> T | None:
        """Return the cached value for key, or None if absent or expired.

        Args:
            key: Cache lookup key.

        Returns:
            Cached value when present and not yet expired, otherwise None.
        """
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
        """Store value under key with a TTL expiry from the current time.

        Args:
            key: Cache key to associate with the value.
            value: Value to store; overwrites any existing entry for the key.
        """
        with self._lock:
            self._store[key] = (time.monotonic() + self._ttl, value)

    def delete(self, key: str) -> None:
        """Remove an entry by key, silently ignoring missing keys.

        Args:
            key: Cache key to remove.
        """
        with self._lock:
            self._store.pop(key, None)

    def clear(self) -> None:
        """Evict all entries from the cache regardless of expiry."""
        with self._lock:
            self._store.clear()

    def stats(self) -> CacheStats:
        """Return a snapshot of hit/miss counters and current live key count.

        Returns:
            CacheStats with cumulative hits, misses, and the current number of stored keys.
        """
        with self._lock:
            return CacheStats(hits=self._hits, misses=self._misses, keys=len(self._store))

    def wrap(self, fn: Callable[..., T]) -> Callable[..., T]:
        """Return a cached wrapper around fn that uses str((args, kwargs)) as the key.

        The returned callable has an extra ``.stats()`` attribute that returns a
        CacheStats snapshot for observability.

        Args:
            fn: Callable to wrap; must be deterministic for a given set of arguments.

        Returns:
            Wrapped callable that transparently caches return values with this TTLCache's TTL.
        """

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
