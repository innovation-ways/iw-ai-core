"""Tests for dashboard/utils/ttl_cache.py."""

from __future__ import annotations

import threading
import time

from dashboard.utils.ttl_cache import TTLCache


class TestTTLCache:
    """Tests for TTLCache scenarios."""

    def test_hit_returns_cached_value(self) -> None:
        """Verifies that hit returns cached value."""
        cache = TTLCache[str](ttl=30)
        cache.set("key", "value")
        assert cache.get("key") == "value"

    def test_miss_returns_none_for_missing_key(self) -> None:
        """Verifies that miss returns none for missing key."""
        cache = TTLCache[str](ttl=30)
        assert cache.get("missing") is None

    def test_expired_key_returns_none(self) -> None:
        """Verifies that expired key returns none."""
        cache = TTLCache[str](ttl=0.1)
        cache.set("key", "value")
        time.sleep(0.15)
        assert cache.get("key") is None

    def test_delete_removes_key(self) -> None:
        """Verifies that delete removes key."""
        cache = TTLCache[str](ttl=30)
        cache.set("key", "value")
        cache.delete("key")
        assert cache.get("key") is None

    def test_clear_removes_all_keys(self) -> None:
        """Verifies that clear removes all keys."""
        cache = TTLCache[str](ttl=30)
        cache.set("a", "1")
        cache.set("b", "2")
        cache.clear()
        assert cache.get("a") is None
        assert cache.get("b") is None

    def test_concurrent_access_does_not_crash(self) -> None:
        """Verifies that concurrent access does not crash."""
        cache = TTLCache[int](ttl=30)
        errors: list[Exception] = []

        def writer(n: int) -> None:
            """Return writer."""
            try:
                for i in range(50):
                    cache.set(f"key-{n}-{i}", n * 100 + i)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        def reader() -> None:
            """Return reader."""
            try:
                for _ in range(50):
                    cache.get("key-0-0")
                    time.sleep(0.001)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(5)]
        threads.append(threading.Thread(target=reader))
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors

    def test_stats_hit_miss(self) -> None:
        """Verifies that stats hit miss."""
        cache = TTLCache[str](ttl=30)
        cache.set("key", "value")
        cache.get("key")  # hit
        cache.get("missing")  # miss
        cache.get("missing")  # miss
        stats = cache.stats()
        assert stats.hits == 1
        assert stats.misses == 2
        assert stats.keys == 1
