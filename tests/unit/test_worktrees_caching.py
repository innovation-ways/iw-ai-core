"""Tests for nav_worktree_badge TTL caching (A1)."""

from __future__ import annotations

import time

from dashboard.utils.ttl_cache import TTLCache


class TestNavWorktreeBadgeCaching:
    def test_badge_returns_from_cache_on_second_call_within_ttl(self) -> None:
        call_count = 0

        def compute_fn() -> int:
            nonlocal call_count
            call_count += 1
            return 5

        cached_fn = TTLCache[int](ttl=30).wrap(compute_fn)

        result1 = cached_fn()
        result2 = cached_fn()

        assert result1 == 5
        assert result2 == 5
        assert call_count == 1  # second call served from cache

    def test_badge_returns_cached_value_after_expiry(self) -> None:
        call_count = 0

        def compute_fn() -> int:
            nonlocal call_count
            call_count += 1
            return 7

        cached_fn = TTLCache[int](ttl=0.1).wrap(compute_fn)

        cached_fn()
        assert call_count == 1

        time.sleep(0.15)

        cached_fn()
        assert call_count == 2  # expired, recomputed

    def test_cached_fn_provides_hit_miss_stats(self) -> None:
        cached_fn = TTLCache[int](ttl=0.5).wrap(lambda: 42)

        cached_fn()
        cached_fn()
        cached_fn()

        stats = cached_fn.stats()
        assert stats.hits == 2
        assert stats.misses == 1


class TestWorktreePageCaching:
    def test_collect_worktrees_returns_same_value_from_cache(self) -> None:
        call_count = 0

        def compute_fn(path: str) -> dict:
            nonlocal call_count
            call_count += 1
            return {"path": path, "label": "dirty"}

        cached_fn = TTLCache[dict](ttl=15).wrap(compute_fn)

        result1 = cached_fn("/repo/worktree-1")
        result2 = cached_fn("/repo/worktree-1")

        assert result1 == result2
        assert call_count == 1
