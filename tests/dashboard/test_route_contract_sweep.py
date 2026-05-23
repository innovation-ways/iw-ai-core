"""CR-00072 — Dashboard route-contract sweep: no dashboard route returns a 5xx.

See ``ai-dev/active/CR-00072/CR-00072_CR_Design.md``.

What this does
──────────────
Enumerates every route registered on the dashboard FastAPI app
(``create_app()`` from ``dashboard.app``), and for every route that serves
``GET`` or ``HEAD`` issues one request against a ``TestClient`` backed by a
seeded testcontainer database, asserting the response status is never a
server error (``status_code < 500``).

The sweep is **parametrized one case per route** (``pytest_generate_tests``)
so a failure names the exact offending route.

Skip set
────────
``SKIP_ROUTES`` documents routes deliberately excluded — streaming/SSE
endpoints (a blind GET holds the connection open and hangs the sweep), the
static-files mount, FastAPI's own OpenAPI/Swagger endpoints, and the AI-runtime
-gated chat endpoints whose 503 is correct behaviour when no runtime is up
(runtime startup is skipped under ``IW_CORE_TEST_CONTEXT``). Each entry carries
a one-line rationale.

Path-parameter resolution
─────────────────────────
``KNOWN_PARAMS`` lists the path parameters the sweep can resolve to real IDs
from the seeded dataset. A route whose parameters are all resolvable is
formatted with real values and swept; a route with any unresolvable parameter
is recorded in ``UNRESOLVED`` and checked against the explicitly-reviewed
``EXPECTED_UNRESOLVED`` set — so a newly-added unresolvable route fails the
test rather than being silently dropped.

EXPECTED_5XX allowlist
──────────────────────
``EXPECTED_5XX`` maps a route path to a one-line rationale for a *genuine*
pre-existing 5xx on ``main`` (a real handler bug, not a test-harness artefact).
Each entry carries a ``TODO(file-incident)`` placeholder; the parametrized
case is ``xfail``-ed. The operator files the Incident on ``main`` post-merge
(see the S01 step report's "Operator follow-up" section). The sweep never
edits production code.

Live-DB guard
─────────────
``dashboard.app`` / ``dashboard.routers.*`` are NEVER imported at module level
— that would trip the live-DB guard at collection time. ``create_app`` is
imported inside ``_collect_get_routes`` (collection) and inside the
``sweep_client`` fixture (test setup); the fixture also rebinds
``orch.db.session._engine`` to the testcontainer engine so any handler that
reaches for ``SessionLocal`` directly hits the test DB, never port 5433.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator

    from fastapi.testclient import TestClient
    from sqlalchemy import Engine
    from sqlalchemy.orm import Session

    from orch.db.models import Project


# ---------------------------------------------------------------------------
# Skip set — path -> one-line rationale
# ---------------------------------------------------------------------------
SKIP_ROUTES: dict[str, str] = {
    # Static-files mount — not an APIRoute; serving depends on bundled assets.
    "/static": "StaticFiles mount, not a sweepable handler.",
    # FastAPI's own schema/docs endpoints — framework-owned, not app routes.
    "/openapi.json": "FastAPI-generated OpenAPI schema endpoint.",
    "/api-docs": "FastAPI Swagger UI (framework-owned).",
    "/api-redoc": "FastAPI ReDoc UI (framework-owned).",
    "/docs/oauth2-redirect": "FastAPI Swagger OAuth2 redirect helper.",
    # Streaming / SSE — a blind GET holds the connection open and hangs the
    # sweep; SSE behaviour is covered by dedicated targeted tests.
    "/api/stream/events": "SSE stream — blind GET never returns.",
    "/api/chat/tabs/{tab_id}/stream": "SSE chat-token stream.",
    "/project/{project_id}/api/code/index/stream": "SSE code-index progress stream.",
    "/project/{project_id}/api/docs/jobs/{job_id}/stream": "SSE doc-job log stream.",
    "/project/{project_id}/jobs/doc_generation/{job_id}/log/stream": "SSE doc-gen log stream.",
    "/project/{project_id}/oss/stream/{job_id}": "SSE OSS-scan progress stream.",
    "/system/worktrees/{batch_item_id}/logs/stream": "SSE worktree-log stream.",
    # AI-runtime-gated chat endpoints — correctly return 503 when no OpenCode/Pi
    # runtime is up; runtime startup is skipped under IW_CORE_TEST_CONTEXT, so a
    # 503 here is expected environment behaviour, not a contract regression.
    "/api/chat/config": "503 by design when the AI runtime is unavailable.",
    "/api/chat/skills": "503 by design when the AI runtime is unavailable.",
}

# ---------------------------------------------------------------------------
# Path parameters the sweep can resolve from the seeded dataset.
# ---------------------------------------------------------------------------
KNOWN_PARAMS: frozenset[str] = frozenset(
    {"project_id", "item_id", "batch_id", "doc_id", "job_id", "step_id", "run_id"}
)

# ---------------------------------------------------------------------------
# Routes whose path parameters cannot all be resolved from the seeded data.
# Explicitly reviewed: a newly-added unresolvable route makes
# test_unresolved_routes_match_expected fail so it gets a conscious decision
# (resolve it by seeding the entity, or add it here with a rationale).
# ---------------------------------------------------------------------------
EXPECTED_UNRESOLVED: frozenset[str] = frozenset(
    {
        "/_help/{slug}",  # help-fragment slug — static allow-list, not seeded
        "/api/chat/tabs/{tab_id}",  # chat tab id — chat tabs not seeded
        "/api/projects/{project_id}/code/modules/{module_slug}",  # RAG module slug
        "/api/projects/{project_id}/code/modules/{module_slug}/diagram",  # RAG module slug
        "/api/projects/{project_id}/conversations/{conversation_id}/messages",  # conversation id
        "/project/{project_id}/api/confirm-batch/{action}/{batch_id}",  # free-text action verb
        "/project/{project_id}/api/confirm-item/{action}/{item_id}",  # free-text action verb
        "/project/{project_id}/api/confirm/{action}/{item_id}/{step_id}",  # free-text action verb
        "/project/{project_id}/api/docs/{doc_id}/diff/sections/{section_name}",  # diff section name
        "/project/{project_id}/auto-merge/events/{event_id}",  # auto-merge event id not seeded
        "/project/{project_id}/batch/{batch_id}/overlap/{held_item_id}",  # overlap modal (CR-00077)
        "/project/{project_id}/item/{item_id}/evidence/{phase}/{filename}",  # evidence file path
        "/project/{project_id}/item/{item_id}/log-content/{step_db_id}/{run_number}",  # log coords
        "/project/{project_id}/jobs/{job_type}/{job_id}",  # job_type discriminator literal
        "/project/{project_id}/oss/findings/{finding_id}/details",  # OSS finding id not seeded
        "/project/{project_id}/tests/report/{run_id}/{file_path:path}",  # Allure report file path
        "/projects/{project_id}/services/{service_name}/restart/confirm",  # service name
        "/projects/{project_id}/services/{service_name}/start/confirm",  # service name
        "/projects/{project_id}/services/{service_name}/stop/confirm",  # service name
        "/system/coverage/files/{package}",  # coverage package name not seeded
        "/system/docs/{doc_path:path}",  # docs/ markdown file path
    }
)

# ---------------------------------------------------------------------------
# EXPECTED_5XX — genuine pre-existing 5xx on `main`. path -> rationale.
# Each entry's parametrized case is xfail-ed; the operator files the Incident
# on `main` post-merge (see the S01 report "Operator follow-up" section).
# Populated only for *genuine handler bugs* — never test-harness artefacts.
# ---------------------------------------------------------------------------
EXPECTED_5XX: dict[str, str] = {
    "/project/{project_id}/docs/{doc_id}/pdf": (
        "TODO(file-incident): docs_pdf() in dashboard/routers/docs.py raises an "
        "unhandled PermissionError (-> HTTP 500) when the optional on-disk PDF "
        "cache dir under project.repo_root is not writable — the PDF itself was "
        "already generated. The sibling handler docs_pdf_view() guards the same "
        "cache write in try/except and degrades gracefully; docs_pdf() must do "
        "the same. Genuine pre-existing handler bug — operator follow-up."
    ),
}


# ---------------------------------------------------------------------------
# Route collection
# ---------------------------------------------------------------------------
_PARAM_RE = re.compile(r"\{([^}:]+)(?::[^}]+)?\}")


def _path_params(path: str) -> list[str]:
    """Return the FastAPI path-parameter names declared in `path`."""
    return _PARAM_RE.findall(path)


def _resolve_path(path: str, substitutions: dict[str, str]) -> str:
    """Substitute every ``{param}`` / ``{param:conv}`` placeholder with a real value."""
    return _PARAM_RE.sub(lambda m: substitutions[m.group(1)], path)


def _collect_get_routes() -> tuple[list[tuple[str, str]], list[str]]:
    """Return ``(resolvable, unresolved)``.

    ``resolvable`` is a sorted list of ``(method, path)`` for every GET/HEAD
    route that is not skipped and whose path parameters are all resolvable.
    ``unresolved`` is the sorted list of distinct paths that have at least one
    unresolvable parameter.

    Deferred import: ``dashboard.app`` is imported here (inside
    ``pytest_generate_tests``) and not at module level.
    """
    from dashboard.app import create_app

    app = create_app()
    resolvable: list[tuple[str, str]] = []
    unresolved: set[str] = set()
    for route in app.routes:
        methods = getattr(route, "methods", None)
        path = getattr(route, "path", "")
        if not methods or not path:
            continue
        if path in SKIP_ROUTES:
            continue
        params = _path_params(path)
        is_resolvable = all(p in KNOWN_PARAMS for p in params)
        for method in sorted(methods):
            if method not in {"GET", "HEAD"}:
                continue
            if is_resolvable:
                resolvable.append((method, path))
            else:
                unresolved.add(path)
    return sorted(resolvable), sorted(unresolved)


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    """Parametrize ``test_route_returns_no_5xx`` one case per resolvable route."""
    if metafunc.definition.name != "test_route_returns_no_5xx":
        return
    resolvable, _ = _collect_get_routes()
    params = []
    for method, path in resolvable:
        marks = []
        if path in EXPECTED_5XX:
            marks.append(
                pytest.mark.xfail(
                    reason=f"EXPECTED_5XX: {EXPECTED_5XX[path]}",
                    strict=True,
                )
            )
        params.append(pytest.param(method, path, marks=marks, id=f"{method} {path}"))
    metafunc.parametrize(("method", "path"), params)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def sweep_client(
    db_engine: Engine,
    db_session: Session,
    test_project: Project,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[tuple[TestClient, dict[str, str]]]:
    """Yield ``(client, substitutions)`` for the route sweep.

    - ``orch.db.session._engine`` is rebound to the testcontainer engine so any
      handler (or middleware) that opens ``SessionLocal()`` directly hits the
      test DB, never the live orch DB on port 5433.
    - ``get_db`` is overridden to the testcontainer ``db_session``.
    - ``IW_CORE_EXPECTED_INSTANCE_ID`` is popped so the DB-identity check does
      not interfere — mirrors ``tests/dashboard/test_jobs_filter_ui.py``.
    - The ``TestClient`` is built with ``raise_server_exceptions=False`` so a
      500 is returned as a response to assert on instead of raising.
    """
    import orch.db.session as session_module

    monkeypatch.setattr(session_module, "_engine", db_engine, raising=False)
    monkeypatch.setattr(session_module, "_session_local", None, raising=False)
    monkeypatch.delenv("IW_CORE_EXPECTED_INSTANCE_ID", raising=False)
    test_session_local = session_module._get_session_local()  # bound to db_engine

    from fastapi.testclient import TestClient

    # `dashboard.app` / `dashboard.dependencies` were imported at collection
    # time (in pytest_generate_tests) and froze module-level `engine` /
    # `SessionLocal` names to a pre-guard engine. Rebind them to the
    # testcontainer engine so any handler/middleware/lifespan code reaching for
    # them lands on the test DB, never the live orch DB on port 5433.
    import dashboard.app as app_module
    import dashboard.dependencies as deps_module
    from dashboard.app import create_app
    from dashboard.dependencies import get_db
    from tests.dashboard.conftest import seed_contract_test_data

    monkeypatch.setattr(app_module, "engine", db_engine, raising=False)
    monkeypatch.setattr(app_module, "SessionLocal", test_session_local, raising=False)
    monkeypatch.setattr(deps_module, "SessionLocal", test_session_local, raising=False)

    substitutions = seed_contract_test_data(db_session, test_project)
    db_session.commit()

    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client, substitutions
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def test_unresolved_routes_match_expected() -> None:
    """The set of routes with unresolvable path params must match the reviewed set.

    A newly-added route whose parameters the sweep cannot resolve fails here —
    forcing a conscious decision (seed the entity so it becomes resolvable, or
    add it to ``EXPECTED_UNRESOLVED`` with a rationale) instead of the route
    being silently excluded from the no-5xx contract.
    """
    _, unresolved = _collect_get_routes()
    actual = set(unresolved)
    missing = actual - EXPECTED_UNRESOLVED
    stale = EXPECTED_UNRESOLVED - actual
    assert actual == EXPECTED_UNRESOLVED, (
        f"UNRESOLVED route set drifted.\n"
        f"  Newly unresolvable (resolve by seeding, or add to EXPECTED_UNRESOLVED): "
        f"{sorted(missing)}\n"
        f"  No longer present (remove from EXPECTED_UNRESOLVED): {sorted(stale)}"
    )


def test_route_sweep_covers_a_meaningful_surface() -> None:
    """Guard against the sweep silently collecting nothing.

    If route collection regresses to an empty list, every parametrized case
    vanishes and the sweep passes vacuously. Pin a floor so that failure mode
    is itself a test failure.
    """
    resolvable, _ = _collect_get_routes()
    assert len(resolvable) >= 60, (
        f"Route sweep collected only {len(resolvable)} GET/HEAD routes; "
        f"expected >= 60 — route collection has regressed."
    )


def test_route_returns_no_5xx(
    method: str,
    path: str,
    sweep_client: tuple[TestClient, dict[str, str]],
) -> None:
    """Every resolvable GET/HEAD dashboard route must respond with status < 500."""
    client, substitutions = sweep_client
    url = _resolve_path(path, substitutions)

    response = client.request(method, url)

    assert response.status_code < 500, (
        f"Route {method} {path} (requested as {method} {url}) returned HTTP "
        f"{response.status_code}.\n"
        f"Response body (truncated): {response.text[:500]!r}\n"
        f"If this is a genuine pre-existing handler bug, add {path!r} to "
        f"EXPECTED_5XX with a TODO(file-incident) rationale and surface it as "
        f"operator follow-up; otherwise fix the test harness (seed data / "
        f"parameter resolution)."
    )
