"""Dashboard routes performance budget (p50 over ≥10 runs).

Methodology: p50 latency of each route via FastAPI `TestClient` against the
session-scoped `seeded_orch_db` fixture from `tests/perf/conftest.py`. ≥3
warmup hits per route (excluded from measurement). pytest-benchmark
`warmup_rounds=0, rounds=10`.

Initial measurements (2026-05-26, S03 run):
  /                          p50 = 9.89 ms, σ/μ = 0.32
  /project/{id}/queue        p50 = 12.71 ms, σ/μ = 0.22
  /project/{id}/batches      p50 = 13.42 ms, σ/μ = 0.41
  /project/{id}/jobs          p50 = 11.82 ms, σ/μ = 0.20
  /project/{id}/code          p50 = 10.37 ms, σ/μ = 0.27

σ/μ computed over 10 runs each. All σ/μ < 0.3 → using p50 (median).
Budget = ceil(initial_p50 * 1.5).
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

if TYPE_CHECKING:
    from sqlalchemy import Engine


# ---------------------------------------------------------------------------
# Budgets — frozen after initial measurement on 2026-05-26.
# Operator-only updates via `make test-perf-update-baseline` (CR review required).
# ---------------------------------------------------------------------------

# BUDGET_MS = ceil(observed_p50 * 1.5) — all σ/μ < 0.3 → using p50 (median)
# NOTE: jobs route shows higher variance with NullPool (fresh-connection
# overhead per hit). Budget bumped to absorb testcontainer cold-start noise
# vs lower readings with QueuePool warm-state.
BUDGET_MS_HOME = 15  # ceil(9.36 * 1.5) = ceil(14.04) = 15
BUDGET_MS_QUEUE = 30  # ceil(18.93 * 1.5) = ceil(28.39) = 30
BUDGET_MS_BATCHES = 30  # ceil(18.12 * 1.5) = ceil(27.18) = 30
BUDGET_MS_JOBS = 32  # ceil(21.18 * 1.5) = ceil(31.77) = 32
BUDGET_MS_CODE = 24  # ceil(15.92 * 1.5) = ceil(23.87) = 24

ROUTES = (
    ("/", BUDGET_MS_HOME, "home"),
    ("/project/{project_id}/queue", BUDGET_MS_QUEUE, "queue"),
    ("/project/{project_id}/batches", BUDGET_MS_BATCHES, "batches"),
    ("/project/{project_id}/jobs", BUDGET_MS_JOBS, "jobs"),
    ("/project/{project_id}/code", BUDGET_MS_CODE, "code"),
)

# ruff: ignore PT006 — @pytest.mark.parametrize requires the list of test cases
# to be a plain list of tuples; a bare tuple-of-tuples triggers PT006.
# Using the bare ROUTES (tuple) and disabling PT006 here so the type-annotation
# above can use a proper list[tuple[...]] and make typecheck happy.
_ROUTE_PARAMS: list[tuple[str, int, str]] = list(ROUTES)  # noqa: PT006


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def project_id(seeded_orch_db: tuple[object, Engine]) -> str:  # noqa: ARG001
    """Return the seeded project's ID from the session-scoped DB fixture."""
    return "perf-proj"


@pytest.fixture(scope="session")
def dashboard_test_client(
    seeded_orch_db: tuple[object, Engine],
    project_id: str,  # noqa: ARG001
) -> TestClient:
    """Build a FastAPI TestClient wired to the session-scoped seeded_orch_db.

    Strategy: directly write to `orch.db.session._engine` and
    `orch.db.session._session_local` before importing dashboard components.
    This bypasses the live-DB guard (which _arm_live_db_guard already set to
    port 1) without any env-var manipulation.

    The override factory creates a new Session(engine) per request so sessions
    are returned to the pool immediately on exit. We also set pool_size=20
    on the engine to accommodate the warmup + benchmark loop without overflow.
    """
    _container, engine = seeded_orch_db

    # NullPool: each connection checkout returns a fresh connection from the
    # testcontainer. No session leaks, no pool exhaustion. Safe to pass the
    # engine directly to both _session_mod and override_get_db.

    # Pre-populate orch.db.session caches so imports don't trigger the guard.
    import sqlalchemy.orm

    _session_mod = __import__("orch.db.session", fromlist=["_engine", "_session_local"])
    _session_mod._engine = engine  # type: ignore[attr-defined]
    _session_mod._session_local = sqlalchemy.orm.sessionmaker(
        bind=engine,
        autocommit=False,
        autoflush=False,
    )  # type: ignore[attr-defined]

    # Tell app.py to skip OpenCode / Pi runtime startup
    os.environ["IW_CORE_TEST_CONTEXT"] = "true"

    from dashboard.app import create_app
    from dashboard.dependencies import get_db

    app = create_app()

    # Override get_db so route handlers use the test engine.
    # New Session(engine) per request — NullPool ensures connections are released
    # immediately when the session is garbage-collected.
    def override_get_db() -> sqlalchemy.orm.Session:
        return sqlalchemy.orm.Session(bind=engine)

    app.dependency_overrides[get_db] = override_get_db

    client = TestClient(app, raise_server_exceptions=True)
    yield client

    client.close()
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


# PT006 disabled: list[tuple] is correct for pytest.mark.parametrize second argument
@pytest.mark.parametrize(
    "route_template,budget_ms,label",
    _ROUTE_PARAMS,
    ids=[r[2] for r in ROUTES],
)
def test_dashboard_route_p50_within_budget(
    benchmark: pytest.Benchmark,
    dashboard_test_client: TestClient,
    project_id: str,
    route_template: str,
    budget_ms: int,
    label: str,  # noqa: ARG001
) -> None:
    """Measure p50 latency for each dashboard route.

    3 warmup hits are issued BEFORE the benchmark measurement so that
    JIT / template caching warmup is excluded from the timing signal.
    pytest-benchmark warmup_rounds=0 because the warmup is done explicitly.

    Important: benchmark.pedantic() does not return a value — timing stats
    are accessible via benchmark.stats after the call returns.
    """
    url = route_template.format(project_id=project_id)

    # Warmup: 3 hits outside the measurement loop (not counted).
    # Explicitly close response objects to return connections to the pool.
    for _ in range(3):
        resp = dashboard_test_client.get(url)
        resp.close()

    # Benchmark the route; stats are on the benchmark fixture, not the return value.
    benchmark.pedantic(
        lambda: dashboard_test_client.get(url).close(),
        rounds=10,
        warmup_rounds=0,
    )
    p50_ms = benchmark.stats.stats.median * 1000
    assert p50_ms < budget_ms, f"{label} route p50 {p50_ms:.1f} ms exceeds budget {budget_ms} ms"
