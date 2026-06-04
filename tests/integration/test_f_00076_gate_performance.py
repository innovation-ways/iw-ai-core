"""Performance smoke test for F-00076 — cross-batch scope gate.

Seeds 50 in-flight items with random globs and verifies the gate evaluation
for one new candidate completes under 100ms.

This is a probe-based intersection check; at 50 items with ~3-5 globs each,
the worst-case comparison count is manageable. The test serves as a
regression guard against algorithmic regressions (e.g. O(n²) without
early exit, or pathological glob patterns).
"""

from __future__ import annotations

import random
import time
import uuid

from orch.daemon.scope_overlap import (
    DEFAULT_ALLOW_PATTERNS,
    DEFAULT_BLOCK_PATTERNS,
    find_blocking_items,
)

# ---------------------------------------------------------------------------
# Glob generation helpers
# ---------------------------------------------------------------------------

_VALID_GLOBS = [
    "src/app/main.py",
    "src/app/config.py",
    "src/app/utils.py",
    "src/lib/core.py",
    "src/lib/helpers.py",
    "src/daemon/main.py",
    "src/daemon/batch_manager.py",
    "src/daemon/merge_queue.py",
    "src/batch_planner.py",
    "src/cli/main.py",
    "src/cli/item_commands.py",
    "orch/handlers/*.py",
    "orch/models/*.py",
    "tests/unit/*.py",
    "tests/integration/*.py",
    "tests/fixtures/*.py",
    "dashboard/**/*.ts",
    "dashboard/**/*.html",
    "docs/**/*.md",
    "pyproject.toml",
    "uv.lock",
    "README.md",
    "LICENSE",
    "src/app/**/*.py",
    "src/lib/**/*.py",
    "tests/**/*.py",
    "dashboard/**/*.js",
    "src/daemon/**/*.py",
    "orch/**/*.py",
    "scripts/**/*.sh",
    "configs/**/*.json",
    "templates/**/*.md",
]


def _random_globs(rng: random.Random, n: int = 3) -> list[str]:
    """Return n random globs from the valid set (with replacement)."""
    return rng.sample(_VALID_GLOBS, k=min(n, len(_VALID_GLOBS)))


def _generate_in_flight(rng: random.Random, count: int) -> list[tuple[str, list[str]]]:
    """Generate `count` (item_id, globs) tuples for in-flight items."""
    return [
        (f"F-{uuid.uuid4().hex[:8].upper()}", _random_globs(rng, rng.randint(2, 5)))
        for _ in range(count)
    ]


# ---------------------------------------------------------------------------
# Performance test
# ---------------------------------------------------------------------------


class TestGatePerformance:
    """Smoke test: gate evaluation must complete under 100ms at scale."""

    def test_50_in_flight_items_under_100ms(self) -> None:
        """50 in-flight items, 3 candidate globs → gate evaluation < 100ms."""
        rng = random.Random(0xF00076)  # noqa: S311

        in_flight = _generate_in_flight(rng, 50)
        candidate = _random_globs(rng, 3)

        start = time.perf_counter()
        result = find_blocking_items(
            candidate,
            in_flight,
            block_patterns=list(DEFAULT_BLOCK_PATTERNS),
            allow_patterns=list(DEFAULT_ALLOW_PATTERNS),
        )
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert elapsed_ms < 100, (
            f"Gate evaluation took {elapsed_ms:.1f}ms (limit: 100ms). Result: {result}"
        )

    def test_100_in_flight_items_under_200ms(self) -> None:
        """100 in-flight items, 5 candidate globs → gate evaluation < 200ms."""
        rng = random.Random(0xF00076)  # noqa: S311

        in_flight = _generate_in_flight(rng, 100)
        candidate = _random_globs(rng, 5)

        start = time.perf_counter()
        result = find_blocking_items(
            candidate,
            in_flight,
            block_patterns=list(DEFAULT_BLOCK_PATTERNS),
            allow_patterns=list(DEFAULT_ALLOW_PATTERNS),
        )
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert elapsed_ms < 200, (
            f"Gate evaluation took {elapsed_ms:.1f}ms (limit: 200ms). Result: {result}"
        )

    def test_all_items_non_overlapping_fast_path(self) -> None:
        """Non-overlapping 50-item set returns empty quickly."""
        # Generate globs from disjoint top-level directories
        in_flight = [(f"F-{i:04d}", [f"src/module_{i}/file.py"]) for i in range(50)]
        candidate = ["completely/different/path.py"]

        start = time.perf_counter()
        result = find_blocking_items(
            candidate,
            in_flight,
            block_patterns=list(DEFAULT_BLOCK_PATTERNS),
            allow_patterns=list(DEFAULT_ALLOW_PATTERNS),
        )
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert result == []
        assert elapsed_ms < 50, f"Non-overlapping case took {elapsed_ms:.1f}ms (expected < 50ms)"
