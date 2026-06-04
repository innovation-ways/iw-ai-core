"""Integration test fixtures using testcontainers.

Tests MUST NOT load .env or connect to the live platform database.
All DB configuration comes exclusively from the testcontainer (random port).

Fixture scopes:
- pg_container: session — one PostgreSQL container per pytest run (~2s startup)
- _pgtestdb_setup: session — builds the migrated template DB once via pgtestdbpy
- db_engine: function — clones the template (~10 ms) and yields per-test engine
- db_session: function — each test runs in its own clone that is dropped at teardown
- test_project: function — a Project row inside the db_session transaction
- cli_get_session: function — get_session factory that yields db_session
"""

from __future__ import annotations

import os
import socket
from collections.abc import Callable, Generator
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import pgtestdbpy
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from testcontainers.postgres import PostgresContainer  # type: ignore[import-untyped]

from orch.db.models import (
    Base,
    Project,
)
from orch.db.safe_migrate import _build_alembic_config, _run_alembic_upgrade
from tests.fixtures.dual_project_seed import TwoProjects, seed_two_projects

if TYPE_CHECKING:
    from sqlalchemy import Engine
    from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Ollama reachability — skip RAG/code-QA tests when no local Ollama listener.
#
# Several integration tests under tests/integration/{rag,dashboard}/test_F00077*
# and tests/integration/test_code_{index,qa,module}_*.py go through the live
# code-understanding pipeline (LanceDB + Ollama embeddings/LLM). They mock the
# vector store but not the Ollama transport, so they require a real Ollama
# listener on $OLLAMA_HOST (default 127.0.0.1:11434). Local dev has it; CI
# does not. Without this hook every push fails on ~50 tests with
# "Failed to connect to Ollama". The skip is conditional, so the tests still
# run on a developer machine that has Ollama up.
# ---------------------------------------------------------------------------

_OLLAMA_FILENAME_PATTERNS = (
    "test_code_index_pipeline.py",
    "test_code_module_routes.py",
    "test_code_qa_eval_set.py",
    "test_code_qa_findusages.py",
    "test_code_qa_no_regression.py",
    "test_code_qa_routes.py",
    "test_code_qa_routing.py",
    "test_code_qa_with_conversation.py",
    "test_code_qa_workitem_flow.py",
    "test_F00077_no_regressions.py",
    "test_F00077_stream_disconnect.py",
    "test_F00077_multi_turn_e2e.py",
    "test_reindex_docs_endpoint.py",
    "test_code_qa_sse_wire.py",
)


@lru_cache(maxsize=1)
def _ollama_reachable() -> bool:
    host_env = os.environ.get("OLLAMA_HOST", "127.0.0.1:11434")
    host, _, port_s = host_env.rpartition(":")
    host = host or "127.0.0.1"
    try:
        port = int(port_s) if port_s else 11434
    except ValueError:
        return False
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


def pytest_collection_modifyitems(
    config: pytest.Config,  # noqa: ARG001
    items: list[pytest.Item],
) -> None:
    ollama_skip = (
        None
        if _ollama_reachable()
        else pytest.mark.skip(reason="Ollama not reachable; RAG/code-QA test skipped")
    )

    # Repo-fixture-dependent tests: ai-dev/archive/* is gitignored, so the
    # F-00055 workflow fixture and the e2e_seed regression net only run when
    # a developer has the local archive on disk. CI doesn't.
    project_root = Path(__file__).resolve().parent.parent.parent
    # Check for the actual fixture ``.py`` source, not merely the directory: a
    # leftover ``__pycache__`` (stale bytecode from a deleted source) keeps the
    # directory alive on dev machines, which would defeat a bare ``.is_dir()``
    # guard and run the tests without their fixtures. Mirror the sibling
    # ``has_e2e_fixtures`` glob so local runs match CI (where the dir is absent).
    has_f00055_fixtures = bool(
        list((project_root / "ai-dev/archive/F-00055/e2e_fixtures").glob("*.py"))
    )
    has_e2e_fixtures = bool(list(project_root.glob("ai-dev/*/*/e2e_fixtures/*.py")))
    fixture_skip = pytest.mark.skip(reason="ai-dev/archive/* fixtures not present (CI)")

    # Tests that need to talk to the actual platform's docker-managed DB
    # (`./ai-core.sh db start` etc). The conftest hijacks IW_CORE_DB_PORT
    # to 1 *after* the @skipif evaluates, so the inner subprocess always
    # talks to a blocked port. Skip in non-developer environments.
    docker_compose_skip = pytest.mark.skip(
        reason="ai-core.sh-managed DB unreachable (CI / non-dev environment)"
    )

    for item in items:
        path = str(item.fspath)
        if ollama_skip and any(p in path for p in _OLLAMA_FILENAME_PATTERNS):
            item.add_marker(ollama_skip)
        if "test_f00055_workflow_fixture.py" in path and not has_f00055_fixtures:
            item.add_marker(fixture_skip)
        if "test_e2e_seed.py" in path and not has_e2e_fixtures:
            item.add_marker(fixture_skip)
        if "test_compose_split.py" in path and "test_ai_core_db_start_noops" in item.name:
            item.add_marker(docker_compose_skip)


OSS_ENUMS_SQL = """\
DO $$
BEGIN
    DROP TYPE IF EXISTS ossscan_status CASCADE;
    CREATE TYPE ossscan_status AS ENUM ('pending', 'running', 'complete', 'error');

    DROP TYPE IF EXISTS ossscan_mode CASCADE;
    CREATE TYPE ossscan_mode AS ENUM ('scan', 'make_oss', 'publish');

    DROP TYPE IF EXISTS osspill_color CASCADE;
    CREATE TYPE osspill_color AS ENUM ('green', 'yellow', 'red', 'gray');

    DROP TYPE IF EXISTS ossfinding_severity CASCADE;
    CREATE TYPE ossfinding_severity AS ENUM ('MUST', 'SHOULD', 'MAY', 'INFO');

    DROP TYPE IF EXISTS ossfinding_status CASCADE;
    CREATE TYPE ossfinding_status AS ENUM ('pass_status', 'fail', 'skip', 'human_required');

    DROP TYPE IF EXISTS osstoolrun_status CASCADE;
    CREATE TYPE osstoolrun_status AS ENUM ('ok', 'failed', 'missing', 'skipped');

    DROP TYPE IF EXISTS project_oss_job_kind CASCADE;
    CREATE TYPE project_oss_job_kind AS ENUM ('scan', 'install', 'fix');

    DROP TYPE IF EXISTS project_oss_job_status CASCADE;
    CREATE TYPE project_oss_job_status AS ENUM (
        'queued', 'running', 'complete', 'error', 'cancelled'
    );
END$$;
"""

BATCH_ITEM_STATUS_SQL = """\
DO $$
BEGIN
    DROP TYPE IF EXISTS batch_item_status CASCADE;
    CREATE TYPE batch_item_status AS ENUM (
        'pending',
        'setting_up',
        'executing',
        'completed',
        'awaiting_merge_approval',
        'merging',
        'merged',
        'failed',
        'stalled',
        'skipped',
        'merge_failed',
        'migration_invalid',
        'migration_rolled_back',
        'migration_rebase_failed',
        'setup_failed'
    );
END$$;
"""


@pytest.fixture(scope="session")
def pg_container() -> Generator[PostgresContainer, None, None]:
    """Start a PostgreSQL 15 container for the entire test session.

    The container runs on a random Docker-assigned port — never touches
    the platform database on the port defined in .env.

    ``timeout=120`` is passed to the Docker Engine API client to set the Unix
    socket read timeout. Without this, the default (~60 s) can fire during
    image pulls on slow connections, surfacing as a ``ReadTimeoutError`` on
    the initial ``/v1.54/containers/create`` call and cascading into 200+
    spurious ``ERROR`` results across the integration suite.

    Note: the timeout is passed via ``docker_client_kw`` (not directly to the
    container run call) so it configures ``docker.from_env(timeout=120)`` — the
    socket-level read timeout on the API client, not a container run argument.
    Passing ``timeout`` directly to the container ``run()`` call would raise an
    ``UnexpectedKWargs`` error because ``timeout`` is not a valid ``run()`` kwarg.
    """
    with PostgresContainer("postgres:15-alpine", docker_client_kw={"timeout": 120}) as pg:
        yield pg


def _migrate_template(url: str) -> None:
    """Apply OSS enums + alembic upgrade head + Base.metadata.create_all to the template DB.

    Called once by ``pgtestdbpy.templates()``; the resulting template is then
    cloned per-test by ``db_engine`` below.
    """
    # urlparse normalises the URL; create_engine accepts the postgresql+psycopg form.
    parsed = urlparse(url)
    assert parsed.scheme in {"postgres", "postgresql"}, f"unexpected scheme: {parsed.scheme}"
    sa_url = f"postgresql+psycopg://{parsed.netloc}{parsed.path}"
    template_engine = create_engine(sa_url, pool_pre_ping=True)
    try:
        with template_engine.connect() as conn:
            conn.execute(text(OSS_ENUMS_SQL))
            conn.execute(text(BATCH_ITEM_STATUS_SQL))
            conn.commit()
        cfg = _build_alembic_config(sa_url)
        _run_alembic_upgrade(cfg)
        Base.metadata.create_all(template_engine)
    finally:
        template_engine.dispose()


@pytest.fixture(scope="session")
def _pgtestdb_setup(pg_container: PostgresContainer) -> Generator[tuple, None, None]:
    """Build the template database once via pgtestdbpy.

    Yields ``(config, migrator)``; the per-test ``db_engine`` fixture uses
    these to ``CREATE DATABASE … TEMPLATE …`` a fresh clone (~10 ms) for
    each test. The template is dropped at session teardown.
    """
    raw_url = pg_container.get_connection_url().replace("postgresql+psycopg2://", "postgresql://")
    parsed = urlparse(raw_url)
    host = str(parsed.hostname)
    port = int(parsed.port or 5432)

    config = pgtestdbpy.Config(
        user=str(parsed.username),
        password=str(parsed.password),
        host=host,
        port=port,
        db_name=parsed.path.lstrip("/"),
    )
    migrator = pgtestdbpy.Migrator(
        migrate=_migrate_template,
        db_name="iwcore_template",
        user="iwcore_test",
        password="iwcore_test",  # noqa: S106 — testcontainer-local; not a real secret
        host=host,
        port=port,
    )
    # pgtestdbpy hardcodes `STRATEGY=FILE_COPY` in its CLONE query, but on
    # PostgreSQL 15+ with IW AI Core's schema size that path is ~10x slower
    # than the default `WAL_LOG` strategy (~310 ms vs ~25 ms per clone in
    # the spike measurement). Override the module-level constant before
    # opening the `templates` context manager — `clone` reads it on every
    # call. (See `docs/research/R-00077-pytest-randomly-isolation-strategy.md`
    # appendix for the FILE_COPY-vs-WAL_LOG benchmark on this codebase.)
    pgtestdbpy.QRY_DB_CLONE = (
        'CREATE DATABASE "{db_name}" WITH TEMPLATE "{template}" OWNER "{user}"'
    )

    with pgtestdbpy.templates(config, migrator):
        yield (config, migrator)


@pytest.fixture
def db_engine(
    _pgtestdb_setup: tuple, monkeypatch: pytest.MonkeyPatch
) -> Generator[Engine, None, None]:
    """Per-test PostgreSQL clone (CR-00055 strategy, R-00077 recommendation).

    Each test gets its own ephemeral database cloned from the session-scoped
    template (~10 ms via ``CREATE DATABASE … TEMPLATE …``). The clone's
    connection URL is exported via ``IW_CORE_DB_*`` env vars so any ``iw``
    CLI subprocess spawned by the test connects to THIS clone — closing the
    isolation gap that defeated savepoint mode + per-module TRUNCATE in
    CR-00049 (see ``docs/research/R-00077-pytest-randomly-isolation-strategy.md``).
    """
    config, migrator = _pgtestdb_setup
    with pgtestdbpy.clone(config, migrator) as raw_url:
        parsed = urlparse(raw_url)
        sa_url = f"postgresql+psycopg://{parsed.netloc}{parsed.path}"
        # Subprocesses spawned by tests must inherit the per-test clone's URL —
        # this is the core of the R-00077 recommendation.
        monkeypatch.setenv("IW_CORE_DB_HOST", str(parsed.hostname))
        monkeypatch.setenv("IW_CORE_DB_PORT", str(parsed.port))
        monkeypatch.setenv("IW_CORE_DB_NAME", parsed.path.lstrip("/"))
        monkeypatch.setenv("IW_CORE_DB_USER", str(parsed.username))
        monkeypatch.setenv("IW_CORE_DB_PASSWORD", str(parsed.password or ""))
        # Also patch IW_CORE_ORCH_DB_* so subprocess calls to get_orch_db_url()
        # (which prefers IW_CORE_ORCH_DB_* over IW_CORE_DB_*) also route to the
        # testcontainer clone rather than the live orch DB (port 5433).
        monkeypatch.setenv("IW_CORE_ORCH_DB_HOST", str(parsed.hostname))
        monkeypatch.setenv("IW_CORE_ORCH_DB_PORT", str(parsed.port))
        monkeypatch.setenv("IW_CORE_ORCH_DB_NAME", parsed.path.lstrip("/"))
        monkeypatch.setenv("IW_CORE_ORCH_DB_USER", str(parsed.username))
        monkeypatch.setenv("IW_CORE_ORCH_DB_PASSWORD", str(parsed.password or ""))
        engine = create_engine(sa_url, pool_pre_ping=True)
        try:
            yield engine
        finally:
            engine.dispose()


@pytest.fixture
def _db_test_connection(db_engine: Engine):
    """Open a connection on the per-test clone (no outer transaction needed).

    With per-test template-clone (R-00077), each test has its own database
    that is dropped at teardown — there is no cross-test state to rollback.
    The connection is shared between ``db_session`` and ``db_session_factory``
    so writes through the fixture session are visible to factory-created
    sessions (e.g. background poller threads).
    """
    connection = db_engine.connect()
    yield connection
    connection.close()


@pytest.fixture
def db_session(_db_test_connection) -> Generator[Session, None, None]:
    """Provide a DB session bound to the per-test clone.

    Each test gets a clean database state without needing to truncate tables —
    the entire clone is dropped at teardown.
    """
    session_factory = sessionmaker(bind=_db_test_connection, autocommit=False, autoflush=False)
    session: Session = session_factory()

    yield session

    session.close()


@pytest.fixture
def db_session_factory(_db_test_connection):
    """Return a sessionmaker that produces sessions sharing the test's clone connection.

    Sessions handed out by this factory bind to the same connection as
    db_session, so writes done in the test are visible to code that opens its
    own session via the factory (e.g. background poller threads). The clone
    is dropped at teardown via db_engine's context manager.
    """
    return sessionmaker(bind=_db_test_connection, autocommit=False, autoflush=False)


@pytest.fixture
def test_project(db_session: Session) -> Project:
    """Insert a minimal Project row inside the current test transaction."""
    project = Project(
        id="test-proj",
        display_name="Test Project",
        repo_root="/repos/test",
        config={},
    )
    db_session.add(project)
    db_session.flush()
    return project


@pytest.fixture
def cli_get_session(db_session: Session) -> Callable[[], contextmanager]:  # type: ignore[arg-type]
    """Return a get_session factory that yields the test db_session.

    Inject into CLI commands via ctx.obj['get_session'] so tests never
    touch orch.db.session (which would load .env and the live engine).
    """

    @contextmanager  # type: ignore[arg-type]
    def _get_session() -> Generator[Session, None, None]:
        yield db_session

    return _get_session  # type: ignore[return-value]


@pytest.fixture
def second_project(db_session: Session, test_project: Project) -> TwoProjects:
    """Seed a second project alongside the existing test_project.

    Project A is the existing ``test_project`` row; project B is a fresh
    ``Project`` created here. Both projects are seeded with the full set of
    project-scoped entities (WorkItem, Batch, architecture + research
    ProjectDoc, CodeIndexJob, DocGenerationJob) with guaranteed-distinct
    identifiers so cross-project isolation assertions can safely check that
    project A's identifiers are absent from project B's scoped responses.

    Function-scoped to preserve the per-test template-clone isolation
    guarantee introduced in CR-00055 — it introduces no shared mutable
    state across tests.
    """
    return seed_two_projects(db_session, proj_a=test_project)


@pytest.fixture
def sample_worktree_path(tmp_path) -> Path:
    """Create a real directory that Path.exists() can confirm.

    Used by CLI retry-merge tests to verify the worktree existence check.
    """

    wt = tmp_path / "worktrees" / "F-99999"
    wt.mkdir(parents=True, exist_ok=True)
    # Create a minimal git worktree marker so the path looks real
    (wt / ".git").write_text("gitdir: /real/repo/.git/worktrees/F-99999\n")
    return wt
