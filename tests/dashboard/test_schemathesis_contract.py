"""CR-00072 — schemathesis property-fuzz of the dashboard's JSON API operations.

See ``ai-dev/active/CR-00072/CR-00072_CR_Design.md``.

What this does
──────────────
Loads the dashboard's OpenAPI schema from the in-process ASGI app built by
``create_app()`` and property-fuzzes its **JSON API operations** with
schemathesis, asserting the schemathesis ``not_a_server_error`` contract on
every generated case — the response is never a 5xx (``status_code < 500``).

Fuzz target
───────────
The dashboard is predominantly HTML/htmx; those routes are covered by
``test_route_contract_sweep.py``, not the fuzzer. ``JSON_API_PATHS`` is the
explicit allow-list of the dashboard's JSON API operations — derived by the
rule "an operation whose OpenAPI response declares an ``application/json``
media type": the keep-alive API (``/api/keep-alive/*``) and the
runtime-overrides endpoint. The set is deliberately narrow — that is expected.

OpenAPI generation
──────────────────
``create_app().openapi()`` now generates the full app's OpenAPI schema cleanly
(I-00111, 2026-05-24, fixed the Pydantic ForwardRef('Response') resolution
error in the offending route handler). The ``contract_schema`` fixture loads
the real full-app schema via ``schemathesis.openapi.from_asgi``; the fuzz
target is narrowed downstream by the ``JSON_API_FUZZ_PATHS`` filter on the
lazy schema. No production code override is needed.

Marker
──────
The whole module is marked ``contract_fuzz`` (``pytestmark``) so it is excluded
from the default ``pytest`` selection (``addopts`` carries
``-m 'not ... and not contract_fuzz'``) and from the blocking suite. It runs
only via ``make test-contract-fuzz`` and the nightly ``contract-fuzz.yml``
workflow.

Live-DB guard
─────────────
``dashboard.app`` is NEVER imported at module level — importing it eagerly
resolves ``SessionLocal`` and trips the live-DB guard at collection time. The
``contract_app`` fixture rebinds ``orch.db.session._engine`` to the
testcontainer engine *before* importing ``dashboard.app``, so the guard
resolves to the test DB and every fuzzed request hits the seeded testcontainer
DB, never the live orch DB on port 5433.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
import schemathesis

if TYPE_CHECKING:
    from collections.abc import Iterator

    from fastapi import FastAPI
    from sqlalchemy import Engine
    from sqlalchemy.orm import Session

    from orch.db.models import Project

# Every test in this module is a slow nightly contract-fuzz test.
pytestmark = pytest.mark.contract_fuzz

# ---------------------------------------------------------------------------
# JSON API operation allow-list.
#
# Derived from the rule: an operation is a "JSON API operation" when its
# OpenAPI response declares an ``application/json`` media type (a handler
# returning JSONResponse or a pydantic model — not HTMLResponse). Fuzzing the
# HTML/htmx routes is out of scope (the route sweep covers those). In today's
# dashboard that rule yields the keep-alive API and the runtime-overrides
# endpoint. When a new JSON endpoint is added, add its path here.
# ---------------------------------------------------------------------------
JSON_API_PATHS: list[str] = [
    "/api/keep-alive/config",
    "/api/keep-alive/slots",
    "/api/keep-alive/slots/{slot_id}",
    "/api/keep-alive/slots/{slot_id}/toggle",
    "/api/keep-alive/runs",
    "/project/{project_id}/api/runtime-options",
]

# ---------------------------------------------------------------------------
# Genuine pre-existing 5xx surfaced by the fuzzer — path -> rationale.
#
# These operations are excluded from the fuzz target (the fuzzer would fail on
# them every run) but kept in JSON_API_PATHS so test_json_api_paths_exist_in
# _schema still verifies they are part of the JSON API surface. Each entry is
# surfaced as operator follow-up in the S01 step report; the operator files the
# Incident on `main` post-merge. CR-00072 never edits production code.
# ---------------------------------------------------------------------------
KNOWN_CONTRACT_5XX: dict[str, str] = {}

# The operations schemathesis actually fuzzes — JSON_API_PATHS minus the
# genuine pre-existing 5xx above.
JSON_API_FUZZ_PATHS: list[str] = [p for p in JSON_API_PATHS if p not in KNOWN_CONTRACT_5XX]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def contract_app(
    db_engine: Engine,
    db_session: Session,
    test_project: Project,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[FastAPI]:
    """Build a dashboard app wired to the seeded testcontainer DB.

    Rebinds ``orch.db.session._engine`` to the testcontainer engine *before*
    importing ``dashboard.app`` so the live-DB guard resolves to the test DB,
    overrides ``get_db`` with the testcontainer ``db_session``, and seeds a
    representative dataset.  No ``openapi()`` override is needed — I-00111
    fixed the underlying Pydantic ForwardRef resolution error.
    """
    import orch.db.session as session_module

    monkeypatch.setattr(session_module, "_engine", db_engine, raising=False)
    monkeypatch.setattr(session_module, "_session_local", None, raising=False)
    monkeypatch.delenv("IW_CORE_EXPECTED_INSTANCE_ID", raising=False)

    from dashboard.app import create_app
    from dashboard.dependencies import get_db
    from tests.dashboard.conftest import seed_contract_test_data

    seed_contract_test_data(db_session, test_project)
    db_session.commit()

    def _override_get_db() -> Iterator[Session]:
        # schemathesis generates many requests per operation against this one
        # app/session. Dashboard handlers raise HTTPException on a DB error
        # without rolling back, so a poisoned session would leak across
        # generated cases as `InFailedSqlTransaction`. Rolling back before each
        # request clears that poison (a no-op for read-only requests) while
        # keeping the committed seed data visible.
        db_session.rollback()
        yield db_session

    app = create_app()
    app.dependency_overrides[get_db] = _override_get_db
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
def contract_schema(contract_app: FastAPI) -> Any:
    """Load the app's full OpenAPI schema (I-00111 restored full-app schema
    generation; the JSON_API_FUZZ_PATHS filter narrows the fuzz target downstream)."""
    return schemathesis.openapi.from_asgi("/openapi.json", contract_app)


# The fuzz surface is narrowed to JSON_API_FUZZ_PATHS (JSON_API_PATHS minus the
# KNOWN_CONTRACT_5XX operations). The filter is applied on the lazy schema —
# the documented place for from_fixture-loaded schemas.
schema = schemathesis.pytest.from_fixture("contract_schema")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def test_json_api_paths_exist_in_schema(contract_schema: Any) -> None:
    """Guard: every JSON_API_PATHS entry must exist in the app's OpenAPI schema.

    If ``JSON_API_PATHS`` drifts out of sync with the dashboard (a path renamed
    or removed) the schemathesis filter silently matches nothing and
    ``test_json_api_never_returns_5xx`` passes vacuously. Asserting each
    allow-listed path is present in the schema makes that drift a test failure.
    """
    schema_paths = {path for path, _ in contract_schema.items()}
    missing = sorted(p for p in JSON_API_PATHS if p not in schema_paths)
    assert not missing, (
        f"JSON_API_PATHS entries absent from the dashboard OpenAPI schema: {missing}. "
        f"Update JSON_API_PATHS to match the current JSON API operations."
    )
    assert len(JSON_API_PATHS) >= 5, (
        f"JSON_API_PATHS has only {len(JSON_API_PATHS)} entries — the JSON API "
        f"fuzz surface has shrunk unexpectedly."
    )


@schema.include(path=JSON_API_FUZZ_PATHS).parametrize()
def test_json_api_never_returns_5xx(case: Any) -> None:
    """Every fuzzed JSON-API request must satisfy not_a_server_error (no 5xx).

    schemathesis generates random/edge-case/invalid inputs for each operation;
    the response status must never be a server error. The explicit
    ``status_code < 500`` assertion is exactly schemathesis's
    ``not_a_server_error`` check, named so a failure points at the operation.
    """
    response = case.call()
    assert response.status_code < 500, (
        f"{case.method} {case.path} returned HTTP {response.status_code} "
        f"— schemathesis not_a_server_error contract violated.\n"
        f"Generated case: path_parameters={case.path_parameters} "
        f"query={case.query} body={case.body!r}"
    )
