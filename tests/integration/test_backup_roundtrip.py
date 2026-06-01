"""Real dump → restore round-trip for the backup engine (F-00092 S11, AC3/AC5).

The host has no pg client tools, so the engine's pg_dump / pg_dumpall /
pg_restore invocations are routed (via the injectable ``command_runner``) into
the testcontainers themselves using the testcontainers docker API
(``get_wrapped_container().exec_run`` + ``put_archive``). This is still
"testcontainers only" — no raw ``docker`` CLI, no live 5433 DB.

Flow:
1. Seed a SOURCE testcontainer (role ``iw_orch``) with a known schema + rows
   (iw_core_instance + 2 projects / 1 batch / 5 work items) and a stub
   ``alembic_version``.
2. ``create_backup`` against it → assert all three artifacts exist, the manifest
   row counts match the seeded data, the manifest records the real PG server
   version, and the globals file actually contains the ``iw_orch`` role.
3. Restore the set into a SECOND fresh container whose superuser is ``postgres``
   (so ``iw_orch`` does NOT pre-exist) → globals first, then the dump. Assert:
   the ``iw_orch`` role now exists (created from globals — AC3), the restore
   ran without ownership/auth errors, identity reads back in bootstrap mode,
   and the row counts equal the source (AC5).
"""

from __future__ import annotations

import io
import tarfile
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from testcontainers.postgres import PostgresContainer  # type: ignore[import-untyped]

from orch.backup.engine import create_backup
from orch.backup.restore import RestoreTarget, restore
from orch.db.models import (
    FTS_FUNCTION_SQL,
    FTS_TRIGGER_SQL,
    Base,
    Batch,
    DbBackupType,
    IwCoreInstance,
    Project,
    WorkItem,
    WorkItemType,
)
from tests.integration.conftest import BATCH_ITEM_STATUS_SQL, OSS_ENUMS_SQL

SOURCE_COUNTS = {"projects": 2, "batches": 1, "work_items": 5}


# ---------------------------------------------------------------------------
# testcontainers docker-exec helpers (testcontainers API only — no docker CLI)
# ---------------------------------------------------------------------------


def _exec(container: PostgresContainer, cmd: list[str], *, demux: bool = False) -> Any:
    res = container.get_wrapped_container().exec_run(cmd, demux=demux)
    return res.exit_code, res.output


def _put_file(container: PostgresContainer, container_dir: str, name: str, data: bytes) -> None:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        info = tarfile.TarInfo(name=name)
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    buf.seek(0)
    container.get_wrapped_container().put_archive(container_dir, buf.read())


def _sa_url(container: PostgresContainer, *, user: str, password: str, db: str) -> str:
    host = container.get_container_host_ip()
    port = container.get_exposed_port(5432)
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{db}"


# ---------------------------------------------------------------------------
# Source schema + seed
# ---------------------------------------------------------------------------


def _setup_source_schema(url: str) -> uuid.UUID:
    engine = create_engine(url)
    instance_id = uuid.UUID("22222222-2222-2222-2222-222222222222")
    try:
        with engine.connect() as conn:
            conn.execute(text(OSS_ENUMS_SQL))
            conn.execute(text(BATCH_ITEM_STATUS_SQL))
            conn.commit()
        Base.metadata.create_all(engine)
        with engine.connect() as conn:
            conn.execute(text(FTS_FUNCTION_SQL))
            conn.execute(text(FTS_TRIGGER_SQL))
            # Stub alembic_version so the engine's metadata introspection works.
            conn.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) PRIMARY KEY)"))
            conn.execute(text("INSERT INTO alembic_version VALUES ('roundtrip_head')"))
            conn.commit()
        with Session(engine) as session:
            session.add(IwCoreInstance(id=1, instance_id=instance_id))
            session.add(Project(id="p1", display_name="Project One", repo_root="/repos/p1"))
            session.add(Project(id="p2", display_name="Project Two", repo_root="/repos/p2"))
            session.flush()
            session.add(Batch(project_id="p1", id="B-0001"))
            session.flush()
            for n in range(1, 6):
                session.add(
                    WorkItem(
                        project_id="p1",
                        id=f"F-{n:05d}",
                        type=WorkItemType.Feature,
                        title=f"Work item {n}",
                    )
                )
            session.commit()
    finally:
        engine.dispose()
    return instance_id


# ---------------------------------------------------------------------------
# command runners that drive the real pg tools inside the containers
# ---------------------------------------------------------------------------


def _make_backup_runner(source: PostgresContainer) -> Any:
    def runner(
        argv: list[str], *, output_path: Path | None = None, _env: dict[str, str] | None = None
    ) -> None:
        tool = argv[0]
        if "pg_dumpall" in tool:
            code, out = _exec(
                source,
                ["pg_dumpall", "--globals-only", "-U", "iw_orch", "-h", "127.0.0.1", "-p", "5432"],
                demux=True,
            )
            stdout, stderr = out
            if code != 0:
                raise RuntimeError(f"pg_dumpall failed ({code}): {stderr!r}")
            assert output_path is not None
            output_path.write_bytes(stdout or b"")
        elif "pg_restore" in tool and "--list" in argv:
            archive = Path(argv[-1])
            _put_file(source, "/tmp", "verify.dump", archive.read_bytes())  # noqa: S108
            code, _ = _exec(source, ["pg_restore", "--list", "/tmp/verify.dump"])  # noqa: S108
            if code != 0:
                raise RuntimeError(f"pg_restore --list integrity check failed ({code})")
        elif "pg_dump" in tool:
            code, out = _exec(
                source,
                [
                    "pg_dump",
                    "-Fc",
                    "-U",
                    "iw_orch",
                    "-h",
                    "127.0.0.1",
                    "-p",
                    "5432",
                    "-d",
                    "iw_orch",
                ],
                demux=True,
            )
            stdout, stderr = out
            if code != 0:
                raise RuntimeError(f"pg_dump failed ({code}): {stderr!r}")
            assert output_path is not None
            output_path.write_bytes(stdout or b"")
        else:
            raise AssertionError(f"unexpected backup command: {argv}")

    return runner


def _make_restore_runner(target: PostgresContainer) -> Any:
    def runner(argv: list[str]) -> None:
        tool = argv[0]
        if "psql" in tool:
            globals_path = Path(argv[argv.index("-f") + 1])
            _put_file(target, "/tmp", "globals.sql", globals_path.read_bytes())  # noqa: S108
            code, out = _exec(
                target,
                [
                    "psql",
                    "-U",
                    "postgres",
                    "-h",
                    "127.0.0.1",
                    "-d",
                    "postgres",
                    "-v",
                    "ON_ERROR_STOP=1",
                    "-f",
                    "/tmp/globals.sql",
                ],  # noqa: S108
            )
            if code != 0:
                raise RuntimeError(f"applying globals failed ({code}): {out!r}")
        elif "pg_restore" in tool:
            archive = Path(argv[-1])
            _put_file(target, "/tmp", "iw_orch.dump", archive.read_bytes())  # noqa: S108
            code, out = _exec(
                target,
                [
                    "pg_restore",
                    "--clean",
                    "--if-exists",
                    "-U",
                    "postgres",
                    "-h",
                    "127.0.0.1",
                    "-d",
                    "iw_orch",
                    "/tmp/iw_orch.dump",
                ],  # noqa: S108
            )
            if code != 0:
                raise RuntimeError(f"pg_restore failed ({code}): {out!r}")
        else:
            raise AssertionError(f"unexpected restore command: {argv}")

    return runner


# ---------------------------------------------------------------------------
# The round-trip test
# ---------------------------------------------------------------------------


def test_backup_restore_round_trip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Identity must read back as "bootstrap" (no expected id pinned).
    monkeypatch.delenv("IW_CORE_EXPECTED_INSTANCE_ID", raising=False)

    backup_dir = tmp_path / "backups"

    with (
        PostgresContainer(
            "postgres:15-alpine",
            username="iw_orch",
            password="orchpw",  # noqa: S106
            dbname="iw_orch",
        ).with_env("POSTGRES_HOST_AUTH_METHOD", "trust") as source,
        PostgresContainer(
            "postgres:15-alpine",
            username="postgres",
            password="postgrespw",  # noqa: S106
            dbname="postgres",
        ).with_env("POSTGRES_HOST_AUTH_METHOD", "trust") as target,
    ):
        src_url = _sa_url(source, user="iw_orch", password="orchpw", db="iw_orch")  # noqa: S106
        source_instance_id = _setup_source_schema(src_url)

        config = SimpleNamespace(
            backup_dir=str(backup_dir),
            db_url=src_url,
            db_host=source.get_container_host_ip(),
            db_port=int(source.get_exposed_port(5432)),
            db_name="iw_orch",
            db_user="iw_orch",
            db_password="orchpw",  # noqa: S106
        )

        # --- 2. create the backup against the source -----------------------
        result = create_backup(
            config,
            backup_type=DbBackupType.manual,
            label="round-trip",
            command_runner=_make_backup_runner(source),
            which_func=lambda name: f"/usr/bin/{name}",
        )

        assert result.archive_path.exists()
        assert result.globals_path.exists()
        assert result.manifest_path.exists()
        assert result.manifest["row_counts"] == SOURCE_COUNTS
        assert result.manifest["postgres_server_version"].startswith("15")
        assert result.manifest["instance_id"] == str(source_instance_id)
        # Globals genuinely captured the role + its password (AC3 precondition).
        globals_sql = result.globals_path.read_text()
        assert "iw_orch" in globals_sql
        assert "ROLE" in globals_sql.upper()

        # --- 3. restore into the fresh target ------------------------------
        # The dump's objects are owned by iw_orch; pg_restore needs the target DB
        # to exist before it runs (restore() does not createdb).
        code, out = _exec(
            target,
            ["psql", "-U", "postgres", "-h", "127.0.0.1", "-c", "CREATE DATABASE iw_orch"],
        )
        assert code == 0, f"failed to create target db: {out!r}"

        # The iw_orch role must NOT exist in the target before globals are applied.
        target_admin_url = _sa_url(
            target,
            user="postgres",
            password="postgrespw",  # noqa: S106
            db="postgres",
        )
        admin_engine = create_engine(target_admin_url)
        try:
            with admin_engine.connect() as conn:
                pre = conn.execute(
                    text("SELECT 1 FROM pg_roles WHERE rolname = 'iw_orch'")
                ).scalar()
            assert pre is None, "iw_orch role should not pre-exist in the fresh target"

            restore_result = restore(
                config,
                backup_set=result.backup_dir,
                target=RestoreTarget(
                    host=target.get_container_host_ip(),
                    port=int(target.get_exposed_port(5432)),
                    db_name="iw_orch",
                    user="postgres",
                    password="postgrespw",  # noqa: S106
                ),
                command_runner=_make_restore_runner(target),
            )

            # AC3: the role now exists, created from the globals file.
            with admin_engine.connect() as conn:
                post = conn.execute(
                    text("SELECT 1 FROM pg_roles WHERE rolname = 'iw_orch'")
                ).scalar()
            assert post == 1, "iw_orch role should exist after applying globals"
        finally:
            admin_engine.dispose()

        # AC5: row counts match the source and identity reads back (bootstrap).
        assert restore_result.row_counts == SOURCE_COUNTS
        assert restore_result.identity_mode == "bootstrap"
        assert restore_result.target.db_name == "iw_orch"
