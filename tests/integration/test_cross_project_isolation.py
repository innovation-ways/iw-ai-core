"""Cross-project isolation test matrix (CR-00074).

IW AI Core is a multi-project platform: every project-scoped dashboard route,
every project-scoped ``iw`` command, and every project-scoped query must return
**only** the requested project's data, while the *global* aggregation surfaces
must span every project. A cross-project leak is a security/correctness bug.

This module is the systematic matrix that proves it, across four axes:

* **Axis 1 — dashboard-route isolation.** For each project-scoped list/index
  route, a request scoped to project B returns a body that contains project
  B's own identifier (proving the route rendered real data) and **none** of
  project A's distinguishing identifiers.
* **Axis 2 — ``iw``-command isolation.** Read commands scoped to project B
  must not expose project A's identifiers in their output (*output isolation*);
  mutating commands scoped to project B must leave project A's rows
  byte-for-byte unchanged while their effect lands on project B
  (*mutation isolation*).
* **Axis 3 — global-aggregation positive assertion.** The cross-project
  ``/docs`` surfaces aggregate **both** projects' data — isolation must not
  over-filter.
* **Axis 4 — per-worktree-DB vs orch-DB boundary (F-00062).** ``orch/config``'s
  ``get_db_url()`` / ``get_orch_db_url()`` env-var resolution keeps the
  per-worktree DB (``IW_CORE_DB_*``) and the orch DB (``IW_CORE_ORCH_DB_*``)
  distinct, with the documented ``_prefer`` fallback.

KNOWN_LEAK allowlist
--------------------
``KNOWN_LEAK`` (below) is keyed by route path / command label. If the matrix
finds a *genuine* isolation leak on ``main`` (a real handler bug, not a
test-harness artefact), the leak is recorded here with a filed high-priority
Incident ID, and the corresponding parametrized case is ``xfail``-ed
(``strict=True`` — if the leak is later fixed the case XPASSes and forces the
allowlist entry to be removed). **A genuine leak is fixed in a separate
Incident — never in this test-only CR.** ``KNOWN_LEAK`` is empty: the matrix
exits 0 on current ``main`` with no genuine leaks found.

Scope note (Axis 1)
-------------------
Axis 1 covers the project-scoped **list / index** routes — the genuine
cross-project aggregation surface where one project's rows could bleed into
another's view. Detail routes keyed by a *second* entity id
(``/project/{pid}/item/{item_id}`` etc.) are not aggregation surfaces: a
cross-project id under the wrong project scope resolves to a 404, never a leak.
"""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from testcontainers.postgres import PostgresContainer  # type: ignore[import-untyped]

from dashboard.app import create_app
from dashboard.dependencies import get_db
from orch.cli.main import cli
from orch.config import get_db_url, get_orch_db_url
from orch.db.models import ProjectDoc
from tests.fixtures.dual_project_seed import SHARED_SEARCH_KEYWORD

if TYPE_CHECKING:
    from collections.abc import Generator

    from click.testing import Result
    from sqlalchemy.orm import Session

    from tests.fixtures.dual_project_seed import TwoProjects

# ---------------------------------------------------------------------------
# KNOWN_LEAK allowlist — keyed by route path template / command label.
# Empty == no genuine isolation leak found on `main`. To add an entry:
#   "<route-or-command>": "I-NNNNN: <one-line rationale>"
# and the corresponding parametrized case is xfail-ed automatically.
# ---------------------------------------------------------------------------
KNOWN_LEAK: dict[str, str] = {}


# ===========================================================================
# Shared fixtures / helpers
# ===========================================================================


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """A TestClient whose ``get_db`` dependency is the testcontainer session.

    Follows the canonical pattern in ``tests/dashboard/test_jobs_filter_ui.py``
    (including popping ``IW_CORE_EXPECTED_INSTANCE_ID`` so the app-startup DB
    identity check runs in bootstrap mode against the per-test clone).
    """
    original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
    app = create_app()
    try:

        def override_get_db() -> Session:
            return db_session

        app.dependency_overrides[get_db] = override_get_db
        with TestClient(app, raise_server_exceptions=True) as test_client:
            yield test_client
    finally:
        if original is not None:
            os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original
        app.dependency_overrides.clear()


def _run_iw(db_session: Session, args: list[str]) -> Result:
    """Invoke the ``iw`` CLI in-process against the test ``db_session``.

    The session is injected via ``ctx.obj['get_session']`` so the command
    never touches ``orch.db.session`` (which would load ``.env`` + the live
    engine). Mirrors the runner pattern in ``tests/integration/test_search.py``.
    """

    @contextmanager
    def get_session() -> Generator[Session, None, None]:
        yield db_session

    return CliRunner().invoke(cli, args, obj={"get_session": get_session})


def _xfail_marks(key: str) -> list[pytest.MarkDecorator]:
    """Return an ``xfail`` mark list when *key* is in the KNOWN_LEAK allowlist."""
    if key in KNOWN_LEAK:
        return [pytest.mark.xfail(reason=KNOWN_LEAK[key], strict=True)]
    return []


# ===========================================================================
# Axis 1 — dashboard-route isolation
# ===========================================================================

# (case id, route template, attribute of proj_b_ids that MUST render).
_AXIS1_ROUTES: list[tuple[str, str, str]] = [
    ("queue", "/project/{project_id}/queue", "work_item_id"),
    ("batches", "/project/{project_id}/batches", "batch_id"),
    ("docs", "/project/{project_id}/docs", "doc_title"),
    ("jobs", "/project/{project_id}/jobs", "batch_id"),
    ("research", "/project/{project_id}/research", "research_title"),
]


def _axis1_params() -> list[Any]:
    return [
        pytest.param(template, present_attr, id=case_id, marks=_xfail_marks(template))
        for case_id, template, present_attr in _AXIS1_ROUTES
    ]


@pytest.mark.parametrize(("route_template", "present_attr"), _axis1_params())
def test_axis1_dashboard_route_isolation(
    route_template: str,
    present_attr: str,
    client: TestClient,
    second_project: TwoProjects,
) -> None:
    """A project-B-scoped dashboard route leaks none of project A's identifiers.

    The route must (a) render project B's own identifier — proving it returned
    real, project-scoped data rather than an empty page — and (b) contain none
    of project A's distinguishing identifiers.
    """
    tp = second_project
    route = route_template.format(project_id=tp.proj_b.id)

    resp = client.get(route)
    assert resp.status_code == 200, f"{route}: expected HTTP 200, got {resp.status_code}"
    body = resp.text

    expected_present = getattr(tp.proj_b_ids, present_attr)
    assert expected_present in body, (
        f"{route}: project B's {present_attr} ({expected_present!r}) is missing — "
        "the route rendered no project-B data, so the isolation check would be vacuous"
    )

    for leaked in tp.proj_a_ids.distinguishing_identifiers():
        assert leaked not in body, (
            f"ISOLATION LEAK: {route} (scoped to project B) leaked project A identifier {leaked!r}"
        )


# ===========================================================================
# Axis 2 — iw-command isolation
# ===========================================================================


def _snapshot_project_docs(db_session: Session, project_id: str) -> list[tuple[Any, ...]]:
    """Return a sorted, comparable snapshot of a project's ProjectDoc rows."""
    docs = db_session.query(ProjectDoc).filter(ProjectDoc.project_id == project_id).all()
    return sorted((d.id, d.title, d.slug, d.content, d.version, d.updated_at) for d in docs)


# (command label, isolation mode) — one parametrized case per project-scoped
# `iw` command. `iw next-id` is deliberately excluded: id_sequences is keyed by
# prefix only (see orch/db/models.py:IdSequence — "Global atomic sequential ID
# allocation per prefix"), so next-id is a global allocator, not a
# project-scoped command, and is out of scope per the Axis-2 rules.
_AXIS2_COMMANDS: list[tuple[str, str]] = [
    ("search", "output"),
    ("item-status", "output"),
    ("doc-update", "mutation"),
]


def _axis2_params() -> list[Any]:
    return [
        pytest.param(command, id=f"{command}-{mode}", marks=_xfail_marks(command))
        for command, mode in _AXIS2_COMMANDS
    ]


@pytest.mark.parametrize("command", _axis2_params())
def test_axis2_iw_command_isolation(
    command: str,
    second_project: TwoProjects,
    db_session: Session,
) -> None:
    """A project-scoped ``iw`` command scoped to project B respects isolation.

    Read commands assert *output* isolation (project A's identifiers absent
    from the project-B-scoped output); mutating commands assert *mutation*
    isolation (project A's rows byte-for-byte unchanged, project B's changed).
    """
    tp = second_project

    if command == "search":
        # Output isolation: `iw search` scoped to project B returns only B's rows.
        result = _run_iw(
            db_session,
            ["--json", "--project", tp.proj_b.id, "search", SHARED_SEARCH_KEYWORD],
        )
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        result_ids = {row["id"] for row in payload["results"]}
        result_projects = {row["project_id"] for row in payload["results"]}
        assert tp.proj_b_ids.work_item_id in result_ids, (
            f"iw search --project {tp.proj_b.id}: project B's work item "
            f"{tp.proj_b_ids.work_item_id} missing — search returned no project-B data"
        )
        assert tp.proj_a_ids.work_item_id not in result_ids, (
            f"OUTPUT-ISOLATION LEAK: iw search --project {tp.proj_b.id} returned "
            f"project A's work item {tp.proj_a_ids.work_item_id}"
        )
        assert result_projects == {tp.proj_b.id}, (
            f"OUTPUT-ISOLATION LEAK: iw search --project {tp.proj_b.id} returned rows "
            f"for projects {result_projects} — expected only {tp.proj_b.id!r}"
        )

    elif command == "item-status":
        # Output isolation: project A's item is unreachable through project B's scope.
        cross = _run_iw(
            db_session,
            ["--project", tp.proj_b.id, "item-status", tp.proj_a_ids.work_item_id, "--json"],
        )
        assert cross.exit_code != 0, (
            f"OUTPUT-ISOLATION LEAK: iw item-status {tp.proj_a_ids.work_item_id} "
            f"--project {tp.proj_b.id} succeeded — project A's item is reachable "
            "from project B's scope"
        )
        assert tp.proj_a_ids.work_item_title not in cross.output, (
            f"OUTPUT-ISOLATION LEAK: iw item-status leaked project A's title "
            f"{tp.proj_a_ids.work_item_title!r} into a project-B-scoped query"
        )
        # In-scope control: project B's own item resolves correctly.
        in_scope = _run_iw(
            db_session,
            ["--project", tp.proj_b.id, "item-status", tp.proj_b_ids.work_item_id, "--json"],
        )
        assert in_scope.exit_code == 0, in_scope.output
        payload = json.loads(in_scope.output)
        assert payload["id"] == tp.proj_b_ids.work_item_id
        assert payload["project_id"] == tp.proj_b.id

    elif command == "doc-update":
        # Mutation isolation: doc-update on B leaves A's docs byte-for-byte unchanged.
        before = _snapshot_project_docs(db_session, tp.proj_a.id)
        assert before, "precondition: project A must have seeded docs to compare"
        new_doc_inner_id = "isolation-doc-update-target"
        result = _run_iw(
            db_session,
            [
                "--project",
                tp.proj_b.id,
                "doc-update",
                new_doc_inner_id,
                "--title",
                "Isolation doc-update probe (project B)",
                "--doc-type",
                "architecture",
                "--tier",
                "semi_automated",
                "--editorial-category",
                "technical",
                "--content",
                "Body written by the cross-project isolation matrix.",
            ],
        )
        assert result.exit_code == 0, result.output
        db_session.flush()
        after = _snapshot_project_docs(db_session, tp.proj_a.id)
        assert after == before, (
            "MUTATION-ISOLATION LEAK: iw doc-update scoped to project B changed "
            f"project A's docs.\nbefore={before}\nafter={after}"
        )
        created = db_session.get(ProjectDoc, f"{tp.proj_b.id}:{new_doc_inner_id}")
        assert created is not None, (
            f"iw doc-update --project {tp.proj_b.id} did not create the project-B doc"
        )
        assert created.title == "Isolation doc-update probe (project B)"
        assert created.project_id == tp.proj_b.id

    else:  # pragma: no cover — guards against an unhandled parametrize case
        raise AssertionError(f"unhandled Axis-2 command: {command!r}")


# ===========================================================================
# Axis 3 — global-aggregation positive assertion
# ===========================================================================


@pytest.mark.parametrize(
    "mode",
    ["aggregation_check-global-docs-page", "aggregation_check-global-docs-search"],
)
def test_axis3_global_aggregation(
    mode: str,
    client: TestClient,
    second_project: TwoProjects,
) -> None:
    """The global ``/docs`` surfaces aggregate BOTH projects (not isolation).

    These are positive assertions: a global view that showed only one project
    would be an over-filtering bug, the mirror image of an isolation leak.
    There is no global ``/jobs`` route — ``jobs_ui.py`` is mounted under
    ``/project/{project_id}``, so jobs are project-scoped only.
    """
    tp = second_project

    if mode.endswith("page"):
        resp = client.get("/docs")
        a_expected, b_expected = tp.proj_a.display_name, tp.proj_b.display_name
    else:
        resp = client.get(f"/api/docs/search?q={SHARED_SEARCH_KEYWORD}")
        a_expected, b_expected = tp.proj_a_ids.doc_title, tp.proj_b_ids.doc_title

    assert resp.status_code == 200, f"{mode}: expected HTTP 200, got {resp.status_code}"
    body = resp.text

    assert a_expected in body, (
        f"AGGREGATION GAP ({mode}): project A's {a_expected!r} is missing from "
        "the global view — isolation is over-filtering"
    )
    assert b_expected in body, (
        f"AGGREGATION GAP ({mode}): project B's {b_expected!r} is missing from "
        "the global view — isolation is over-filtering"
    )


# ===========================================================================
# Axis 4 — per-worktree-DB vs orch-DB boundary (F-00062)
# ===========================================================================
#
# The real F-00062 boundary is the env-var resolution code in orch/config.py,
# not two unrelated SQLAlchemy sessions (which would test PostgreSQL, not IW AI
# Core). These tests point IW_CORE_DB_* at one container and IW_CORE_ORCH_DB_*
# at a second, then exercise get_db_url() / get_orch_db_url() — including the
# documented `_prefer` fallback and the I-00062 agent-context guard.
#
# Env vars are set via monkeypatch.setenv ONLY — never importlib.reload(
# orch.config), per the CLAUDE.md rule: get_db_url()/get_orch_db_url() read
# os.environ fresh on every call, so monkeypatch alone is sufficient.

_BOUNDARY_MARKER_DDL = "CREATE TABLE boundary_marker (value TEXT NOT NULL)"
_WORKTREE_MARKER = "per-worktree-db-row"
_ORCH_MARKER = "orch-db-row"


def _parsed_url(container: PostgresContainer) -> Any:
    """Parsed connection URL for a testcontainer (psycopg2 scheme stripped)."""
    raw = container.get_connection_url().replace("postgresql+psycopg2://", "postgresql://")
    return urlparse(raw)


def _set_db_env(monkeypatch: pytest.MonkeyPatch, prefix: str, container: PostgresContainer) -> None:
    """Point an ``IW_CORE_(ORCH_)DB_*`` env-var group at *container*."""
    parsed = _parsed_url(container)
    monkeypatch.setenv(f"{prefix}_HOST", str(parsed.hostname))
    monkeypatch.setenv(f"{prefix}_PORT", str(parsed.port))
    monkeypatch.setenv(f"{prefix}_NAME", parsed.path.lstrip("/"))
    monkeypatch.setenv(f"{prefix}_USER", str(parsed.username))
    monkeypatch.setenv(f"{prefix}_PASSWORD", str(parsed.password))


@pytest.fixture(scope="module")
def boundary_databases() -> Generator[tuple[PostgresContainer, PostgresContainer], None, None]:
    """Two distinct testcontainer Postgres DBs: a per-worktree DB and an orch DB.

    Each is seeded once with a single distinguishable ``boundary_marker`` row.
    Module-scoped so the (immutable, read-only) containers start once; tests
    never mutate them, so they remain order-independent under pytest-randomly.
    """
    with (
        PostgresContainer("postgres:15-alpine") as worktree_db,
        PostgresContainer("postgres:15-alpine") as orch_db,
    ):
        for container, marker in ((worktree_db, _WORKTREE_MARKER), (orch_db, _ORCH_MARKER)):
            url = container.get_connection_url().replace(
                "postgresql+psycopg2://", "postgresql+psycopg://"
            )
            engine = create_engine(url)
            try:
                with engine.connect() as conn:
                    conn.execute(text(_BOUNDARY_MARKER_DDL))
                    conn.execute(
                        text("INSERT INTO boundary_marker (value) VALUES (:v)"),
                        {"v": marker},
                    )
                    conn.commit()
            finally:
                engine.dispose()
        yield worktree_db, orch_db


def test_axis4_get_db_url_resolves_worktree_get_orch_db_url_resolves_orch(
    boundary_databases: tuple[PostgresContainer, PostgresContainer],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """get_db_url() → per-worktree container; get_orch_db_url() → orch container."""
    worktree_db, orch_db = boundary_databases
    monkeypatch.delenv("IW_CORE_AGENT_CONTEXT", raising=False)
    _set_db_env(monkeypatch, "IW_CORE_DB", worktree_db)
    _set_db_env(monkeypatch, "IW_CORE_ORCH_DB", orch_db)

    db_url = get_db_url()
    orch_url = get_orch_db_url()

    worktree_port = str(_parsed_url(worktree_db).port)
    orch_port = str(_parsed_url(orch_db).port)

    assert f":{worktree_port}/" in db_url, (
        f"get_db_url() ({db_url}) did not resolve to the per-worktree container "
        f"(port {worktree_port})"
    )
    assert f":{orch_port}/" in orch_url, (
        f"get_orch_db_url() ({orch_url}) did not resolve to the orch container (port {orch_port})"
    )
    assert db_url != orch_url, (
        "BOUNDARY LEAK: get_db_url() and get_orch_db_url() resolved to the same URL"
    )


def test_axis4_sessions_see_only_their_own_rows(
    boundary_databases: tuple[PostgresContainer, PostgresContainer],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A session on each resolved URL sees only that database's marker row."""
    worktree_db, orch_db = boundary_databases
    monkeypatch.delenv("IW_CORE_AGENT_CONTEXT", raising=False)
    _set_db_env(monkeypatch, "IW_CORE_DB", worktree_db)
    _set_db_env(monkeypatch, "IW_CORE_ORCH_DB", orch_db)

    worktree_engine = create_engine(get_db_url())
    orch_engine = create_engine(get_orch_db_url())
    try:
        with worktree_engine.connect() as conn:
            worktree_rows = [r[0] for r in conn.execute(text("SELECT value FROM boundary_marker"))]
        with orch_engine.connect() as conn:
            orch_rows = [r[0] for r in conn.execute(text("SELECT value FROM boundary_marker"))]
    finally:
        worktree_engine.dispose()
        orch_engine.dispose()

    assert worktree_rows == [_WORKTREE_MARKER], (
        f"per-worktree session saw {worktree_rows} — expected only {_WORKTREE_MARKER!r}"
    )
    assert orch_rows == [_ORCH_MARKER], (
        f"orch session saw {orch_rows} — expected only {_ORCH_MARKER!r}"
    )
    assert _ORCH_MARKER not in worktree_rows, (
        "BOUNDARY LEAK: the per-worktree session saw the orch DB's row"
    )
    assert _WORKTREE_MARKER not in orch_rows, (
        "BOUNDARY LEAK: the orch session saw the per-worktree DB's row"
    )


def test_axis4_orch_url_prefers_db_when_orch_env_unset(
    boundary_databases: tuple[PostgresContainer, PostgresContainer],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With IW_CORE_ORCH_DB_* unset, get_orch_db_url() falls back to IW_CORE_DB_*."""
    worktree_db, _orch_db = boundary_databases
    monkeypatch.delenv("IW_CORE_AGENT_CONTEXT", raising=False)
    _set_db_env(monkeypatch, "IW_CORE_DB", worktree_db)
    for suffix in ("HOST", "PORT", "NAME", "USER", "PASSWORD"):
        monkeypatch.delenv(f"IW_CORE_ORCH_DB_{suffix}", raising=False)

    worktree_port = str(_parsed_url(worktree_db).port)
    orch_url = get_orch_db_url()

    assert orch_url == get_db_url(), (
        "the `_prefer` fallback failed: get_orch_db_url() did not fall back to "
        "IW_CORE_DB_* when IW_CORE_ORCH_DB_* is unset"
    )
    assert f":{worktree_port}/" in orch_url, (
        f"get_orch_db_url() fallback ({orch_url}) did not resolve to the "
        f"per-worktree container (port {worktree_port})"
    )


def test_axis4_agent_context_orch_port_collision_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The I-00062 guard: in agent context, IW_CORE_DB_PORT == orch port raises."""
    monkeypatch.setenv("IW_CORE_DB_HOST", "127.0.0.1")
    monkeypatch.setenv("IW_CORE_DB_PORT", "5433")
    monkeypatch.setenv("IW_CORE_DB_NAME", "iw_core")
    monkeypatch.setenv("IW_CORE_DB_USER", "iw_core")
    monkeypatch.setenv("IW_CORE_DB_PASSWORD", "iw_core")
    monkeypatch.setenv("IW_CORE_ORCH_DB_PORT", "5433")
    monkeypatch.setenv("IW_CORE_AGENT_CONTEXT", "true")

    with pytest.raises(RuntimeError, match=r"I-00062") as exc:
        get_db_url()
    message = str(exc.value)
    assert message.startswith("I-00062:"), f"unexpected guard message: {message!r}"
    assert "orch DB port" in message, f"guard message lost its explanation: {message!r}"
