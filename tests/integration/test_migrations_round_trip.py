"""Migration round-trip + create_all-vs-alembic drift test.

WHY THIS FILE EXISTS
--------------------
The shared ``db_engine`` fixture in ``tests/integration/conftest.py`` builds
the test schema with ``Base.metadata.create_all()``. That call ignores the
Alembic migration files entirely — every column declared on a ``Mapped[...]``
attribute appears in the test schema regardless of whether a migration adds
it. Consequently, an integration suite that only uses the shared engine can
green-light a state where:

  * the model declares a new column, but
  * the corresponding migration is missing / has the wrong revision id /
    has a broken upgrade or downgrade body, or
  * the migration applies but produces a schema that doesn't match the model.

That class of bug only surfaces when a real DB is brought from base to head
via ``alembic upgrade``. Production already has such a guard (the daemon's
pre-merge dry-run in ``orch.daemon.migration_pipeline``), but it runs at
merge time — twenty-odd workflow steps after the migration was generated.
This test brings the same check forward to ``make test-integration`` so a
broken migration fails the integration gate, not the merge queue.

What this test asserts, in one shot, against a fresh testcontainer:

    1. ``alembic upgrade head`` succeeds from an empty DB. Catches missing
       revision ids, dangling ``down_revision``s, runtime errors in
       ``upgrade()``, and ENUM/CHECK constraint failures.

    2. The schema produced by step 1 is structurally identical to what
       ``Base.metadata.create_all()`` would produce. Catches model/migration
       drift — i.e. the agent added a ``Mapped[...]`` column but forgot to
       add a matching ``op.add_column`` (or vice versa). Compared by table
       name + column name + nullability; types are compared by their PG
       string repr after both sides have been issued against the same DB.

    3. ``alembic downgrade base`` followed by ``alembic upgrade head``
       succeeds. Catches broken ``downgrade()`` bodies (the cheap "reverse
       me" property that operators rely on for Phase-3 rollback in
       ``migration_pipeline.run_rollback``).

The test is module-scoped so the testcontainer comes up once for the whole
file. Each assertion uses a fresh DB (created via ``DROP/CREATE DATABASE``)
so leftover state from one phase can't mask the next.
"""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from shutil import copy2
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text
from testcontainers.postgres import PostgresContainer

from scripts.resolve_pending_migration import resolve_pending_migration

if TYPE_CHECKING:
    from sqlalchemy import Engine

# Path to the alembic script directory, resolved relative to repo root.
# Tests are invoked from the repo root by `make test-integration`.
_SCRIPT_LOCATION = "orch/db/migrations"


@pytest.fixture(scope="module")
def pg_container() -> PostgresContainer:
    """Module-scoped postgres container, separate from the session-scoped
    one in ``conftest.py`` so we can DROP/CREATE databases inside it
    without disturbing other tests."""
    with PostgresContainer("postgres:15-alpine") as pg:
        yield pg


def _connection_url(pg: PostgresContainer, dbname: str) -> str:
    """Return a psycopg-driver URL for ``dbname`` on ``pg``.

    testcontainers hands back a psycopg2 URL by default — the project uses
    psycopg v3, so we rewrite the driver before SQLAlchemy sees it."""
    base = pg.get_connection_url().replace("postgresql+psycopg2://", "postgresql+psycopg://")
    parsed = urlparse(base.replace("postgresql+psycopg://", "postgresql://"))
    return (
        f"postgresql+psycopg://{parsed.username}:{parsed.password}"
        f"@{parsed.hostname}:{parsed.port}/{dbname}"
    )


def _make_fresh_db(pg: PostgresContainer, dbname: str) -> Engine:
    """Drop and recreate ``dbname`` on the container, return an engine.

    DROP/CREATE has to run on a different DB than the one being recreated;
    we use the default ``test`` DB that testcontainers created.
    """
    bootstrap_url = pg.get_connection_url().replace(
        "postgresql+psycopg2://", "postgresql+psycopg://"
    )
    bootstrap = create_engine(bootstrap_url, isolation_level="AUTOCOMMIT")
    with bootstrap.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{dbname}"'))
        conn.execute(text(f'CREATE DATABASE "{dbname}"'))
    bootstrap.dispose()
    return create_engine(_connection_url(pg, dbname), pool_pre_ping=True)


def _alembic_config(engine: Engine) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", _SCRIPT_LOCATION)
    cfg.set_main_option("sqlalchemy.url", engine.url.render_as_string(hide_password=False))
    return cfg


def _set_db_env(monkeypatch: pytest.MonkeyPatch, engine: Engine) -> None:
    """Point ``IW_CORE_DB_*`` at ``engine`` so ``orch.db.migrations.env``
    resolves the right DB URL when alembic runs.

    The migration env reads ``orch.config.get_db_url()`` if no explicit
    ``sqlalchemy.url`` is set in the config. We set it explicitly via
    ``_alembic_config``, but env vars are also patched defensively so any
    sub-import that calls ``get_db_url()`` directly (e.g. for engine
    construction inside a migration) still hits the testcontainer."""
    parsed = urlparse(
        engine.url.render_as_string(hide_password=False).replace(
            "postgresql+psycopg://", "postgresql://"
        )
    )
    monkeypatch.setenv("IW_CORE_DB_HOST", str(parsed.hostname))
    monkeypatch.setenv("IW_CORE_DB_PORT", str(parsed.port))
    monkeypatch.setenv("IW_CORE_DB_NAME", parsed.path.lstrip("/"))
    monkeypatch.setenv("IW_CORE_DB_USER", str(parsed.username))
    monkeypatch.setenv("IW_CORE_DB_PASSWORD", str(parsed.password))


def _column_signature(engine: Engine) -> dict[tuple[str, str], dict[str, object]]:
    """Return ``{(table, column): {nullable, type_str}}`` for every column
    in the ``public`` schema of ``engine``.

    Type comparison uses PostgreSQL's own string rendering (via
    ``information_schema.columns.data_type``) so SQLAlchemy/Alembic
    serialization differences don't trigger false drift hits."""
    insp = inspect(engine)
    sig: dict[tuple[str, str], dict[str, object]] = {}
    with engine.connect() as conn:
        for table in insp.get_table_names(schema="public"):
            if table == "alembic_version":
                continue
            rows = conn.execute(
                text(
                    "SELECT column_name, is_nullable, data_type "
                    "FROM information_schema.columns "
                    "WHERE table_schema = 'public' AND table_name = :t"
                ),
                {"t": table},
            ).fetchall()
            for col_name, is_nullable, data_type in rows:
                sig[(table, col_name)] = {
                    "nullable": is_nullable == "YES",
                    "data_type": data_type,
                }
    return sig


def test_alembic_upgrade_head_succeeds_from_empty(
    pg_container: PostgresContainer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``alembic upgrade head`` on a fresh DB must apply every revision in
    the script directory without errors.

    Catches: missing revision id, broken ``down_revision`` chain, runtime
    failures in ``op.execute()`` / DDL, and ENUM/CHECK constraint
    violations against existing data (none here, but the DDL itself is
    exercised)."""
    engine = _make_fresh_db(pg_container, "rt_upgrade")
    _set_db_env(monkeypatch, engine)
    cfg = _alembic_config(engine)
    command.upgrade(cfg, "head")

    with engine.connect() as conn:
        head = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
    assert head, "alembic_version table is empty after upgrade head"


def test_alembic_schema_matches_create_all(
    pg_container: PostgresContainer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The schema produced by ``alembic upgrade head`` must match the one
    produced by ``Base.metadata.create_all()``.

    Asserts table set equality plus, for every shared table, identical
    column names with matching nullability and PG ``data_type``. This is
    the model/migration drift check — if S01 adds a ``Mapped[...]`` column
    but the migration is missing the matching ``op.add_column``, this test
    fails with a clear list of the columns that are present in one schema
    but not the other.

    Type-level drift (e.g. ``TEXT`` vs ``VARCHAR(255)``) is also caught —
    PostgreSQL reports the canonical ``data_type`` so the comparison is
    stable across SQLAlchemy / Alembic minor versions."""
    # Build the alembic schema in a fresh DB.
    alembic_engine = _make_fresh_db(pg_container, "rt_alembic")
    _set_db_env(monkeypatch, alembic_engine)
    command.upgrade(_alembic_config(alembic_engine), "head")
    alembic_sig = _column_signature(alembic_engine)

    # Build the create_all() schema in a separate fresh DB so they don't
    # contaminate each other.
    create_all_engine = _make_fresh_db(pg_container, "rt_create_all")
    # Local import: orch.db.models registers ENUM types at import time,
    # which mutate the metadata of any engine created above. Importing
    # here keeps the scope narrow.
    from orch.db.models import Base  # noqa: PLC0415

    Base.metadata.create_all(create_all_engine)
    create_all_sig = _column_signature(create_all_engine)

    alembic_keys = set(alembic_sig.keys())
    create_all_keys = set(create_all_sig.keys())

    only_in_alembic = sorted(alembic_keys - create_all_keys)
    only_in_create_all = sorted(create_all_keys - alembic_keys)

    assert not only_in_create_all, (
        "Models declare columns that no Alembic migration creates "
        "(missing op.add_column?):\n  " + "\n  ".join(f"{t}.{c}" for t, c in only_in_create_all)
    )
    assert not only_in_alembic, (
        "Alembic creates columns the models don't declare "
        "(stale migration or removed Mapped[]):\n  "
        + "\n  ".join(f"{t}.{c}" for t, c in only_in_alembic)
    )

    # Per-column nullability + type drift.
    drift: list[str] = []
    for key in sorted(alembic_keys & create_all_keys):
        a = alembic_sig[key]
        c = create_all_sig[key]
        if a["nullable"] != c["nullable"] or a["data_type"] != c["data_type"]:
            drift.append(
                f"  {key[0]}.{key[1]}: "
                f"alembic={{nullable={a['nullable']}, type={a['data_type']!r}}} "
                f"create_all={{nullable={c['nullable']}, type={c['data_type']!r}}}"
            )
    assert not drift, "Column drift between alembic and create_all:\n" + "\n".join(drift)


def test_alembic_downgrade_base_then_upgrade_head(
    pg_container: PostgresContainer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Round-trip: upgrade head → downgrade base → upgrade head must succeed.

    Catches broken ``downgrade()`` bodies. Phase-3 rollback in
    ``orch/daemon/migration_pipeline.run_rollback`` issues
    ``alembic downgrade -1`` after a failed Phase-2 apply; if any
    migration's downgrade is broken, the rollback freezes the merge queue
    and an operator has to clean up by hand. This test makes the most
    recently added migration's downgrade exercised before merge."""
    engine = _make_fresh_db(pg_container, "rt_round_trip")
    _set_db_env(monkeypatch, engine)
    cfg = _alembic_config(engine)

    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")

    # All non-alembic_version tables should be gone after downgrade base.
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT tablename FROM pg_tables "
                "WHERE schemaname = 'public' AND tablename != 'alembic_version'"
            )
        ).fetchall()
    leftovers = sorted(r[0] for r in rows)
    assert not leftovers, f"downgrade base left tables behind (broken downgrade()?): {leftovers}"

    # And we must be able to come back up cleanly.
    command.upgrade(cfg, "head")
    with engine.connect() as conn:
        head = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
    assert head, "alembic_version is empty after second upgrade head"


def _copy_versions_dir(dst: Path) -> Path:
    src = Path("orch/db/migrations/versions")
    dst.mkdir(parents=True, exist_ok=True)
    for f in src.glob("*.py"):
        copy2(f, dst / f.name)

    migrations_dst = dst.parent
    migrations_src = Path("orch/db/migrations")
    copy2(migrations_src / "env.py", migrations_dst / "env.py")
    copy2(migrations_src / "script.py.mako", migrations_dst / "script.py.mako")
    return dst


def _find_head_revision(versions_dir: Path) -> str:
    cfg = Config()
    cfg.set_main_option("script_location", str(versions_dir.parent))
    script_dir = ScriptDirectory.from_config(cfg)
    return script_dir.get_current_head()


def test_resolver_produces_valid_chain_against_real_versions_dir(tmp_path: Path) -> None:
    scratch = _copy_versions_dir(tmp_path / "versions")
    expected_head = _find_head_revision(scratch)
    assert expected_head is not None

    synthetic = scratch / "0000000000ff_pending.py"
    synthetic.write_text(
        'revision = "0000000000ff"\n'
        'down_revision = "PENDING"\n\n'
        "def upgrade() -> None:\n"
        "    pass\n\n"
        "def downgrade() -> None:\n"
        "    pass\n",
        encoding="utf-8",
    )

    rewrites = resolve_pending_migration(scratch)

    for f in scratch.glob("*.py"):
        content = f.read_text(encoding="utf-8")
        assert 'down_revision = "PENDING"' not in content

    assert len(rewrites) == 1
    assert rewrites[0][0] == "0000000000ff"
    assert rewrites[0][1] == expected_head


def test_ac4_resolver_is_noop_on_clean_versions_dir(tmp_path: Path) -> None:
    scratch = _copy_versions_dir(tmp_path / "versions")

    before = {p.name: sha256(p.read_bytes()).hexdigest() for p in sorted(scratch.glob("*.py"))}

    rewrites = resolve_pending_migration(scratch)

    after = {p.name: sha256(p.read_bytes()).hexdigest() for p in sorted(scratch.glob("*.py"))}

    assert rewrites == []
    assert before == after
