"""Minimal daemon stub for E2E browser verification.

The real ``orch.daemon.main`` is not included in the isolated E2E stack
because it's too heavy (git worktrees, LLM agents, merge queues) and
because nothing in the E2E stack is supposed to actually *execute* work
items. But browser_verification steps whose assertions depend on
**daemon-driven state transitions** — notably any V step that reads a
job row after clicking the button that created it — can't be satisfied
without *some* process advancing queued jobs.

This stub polls the E2E DB every 2 s and flips rows through
``queued → running → completed`` on a fixed delay so those V steps can
observe the lifecycle without the full daemon's cost. It handles:

- ``doc_index_jobs`` (introduced for F-00060 hybrid Code Q&A)
- ``code_index_jobs`` (code understanding indexer)

Run with:  ``uv run python scripts/e2e_daemon_stub.py``

Intended to be launched by ``docker-compose.e2e.yml`` alongside the
dashboard + ollama stubs. Environment variables mirror the dashboard
container (``IW_CORE_DB_*``). No external deps beyond the project's
existing psycopg.
"""

from __future__ import annotations

import contextlib
import logging
import os
import signal
import sys
import time
from typing import TYPE_CHECKING, Any

import psycopg

if TYPE_CHECKING:
    import types

logger = logging.getLogger("e2e-daemon-stub")

# How long to hold a job in ``running`` before flipping it to
# ``completed``. Short enough that V steps with a 120 s ceiling pass
# comfortably; long enough that the UI can show the transition.
_RUN_DURATION_SECS = 3.0
_POLL_INTERVAL_SECS = 2.0


def _dsn() -> str:
    """Build a psycopg DSN from IW_CORE_DB_* env vars (same as the daemon)."""
    host = os.environ.get("IW_CORE_DB_HOST", "e2e-db")
    port = os.environ.get("IW_CORE_DB_PORT", "5432")
    name = os.environ.get("IW_CORE_DB_NAME", "iw_e2e")
    user = os.environ.get("IW_CORE_DB_USER", "iw_e2e")
    password = os.environ.get("IW_CORE_DB_PASSWORD", "iw_e2e_dev")
    return f"host={host} port={port} dbname={name} user={user} password={password}"


def _advance_doc_index_jobs(conn: psycopg.Connection) -> int:
    """Advance ``doc_index_jobs`` rows through the lifecycle.

    Returns the count of state transitions this tick.
    """
    transitions = 0
    with conn.cursor() as cur:
        # queued → running: flip everything queued and stamp started_at.
        cur.execute(
            """
            UPDATE doc_index_jobs
               SET status = 'running',
                   started_at = NOW()
             WHERE status = 'queued'
            """,
        )
        transitions += cur.rowcount or 0

        # running → completed: anything that's been running longer than
        # _RUN_DURATION_SECS gets flipped to completed with plausible counters.
        cur.execute(
            """
            UPDATE doc_index_jobs
               SET status = 'completed',
                   completed_at = NOW(),
                   items_discovered = COALESCE(NULLIF(items_discovered, 0), 3),
                   items_indexed = COALESCE(NULLIF(items_indexed, 0), 3),
                   chunks_created = COALESCE(NULLIF(chunks_created, 0), 12)
             WHERE status = 'running'
               AND started_at IS NOT NULL
               AND started_at < NOW() - make_interval(secs => %s)
            """,
            (_RUN_DURATION_SECS,),
        )
        transitions += cur.rowcount or 0
    conn.commit()
    return transitions


def _advance_code_index_jobs(conn: psycopg.Connection) -> int:
    """Advance ``code_index_jobs`` rows through the lifecycle.

    CodeIndexJob has no ``started_at`` column (only ``triggered_at`` and
    ``completed_at``), so the running→completed flip is gated on
    ``triggered_at`` instead.
    """
    transitions = 0
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE code_index_jobs
               SET status = 'running',
                   updated_at = NOW()
             WHERE status = 'queued'
            """,
        )
        transitions += cur.rowcount or 0

        cur.execute(
            """
            UPDATE code_index_jobs
               SET status = 'completed',
                   completed_at = NOW(),
                   updated_at = NOW(),
                   files_discovered = COALESCE(NULLIF(files_discovered, 0), 42),
                   files_indexed = COALESCE(NULLIF(files_indexed, 0), 42),
                   chunks_created = COALESCE(NULLIF(chunks_created, 0), 100)
             WHERE status = 'running'
               AND triggered_at IS NOT NULL
               AND triggered_at < NOW() - make_interval(secs => %s)
            """,
            (_RUN_DURATION_SECS,),
        )
        transitions += cur.rowcount or 0
    conn.commit()
    return transitions


def _emit_lifecycle_events(conn: psycopg.Connection) -> None:
    """Drop a minimal ``code_map_completed`` DaemonEvent after a doc-index
    run completes so toast subscribers can react. We only emit for the
    most recently-completed job that hasn't already been announced."""
    # Tracking table / column is not guaranteed to exist; keep this cheap
    # and idempotent by using a single NOTIFY-equivalent INSERT whenever
    # something landed this tick. The real daemon does richer tracking.
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, project_id
              FROM doc_index_jobs
             WHERE status = 'completed'
               AND completed_at > NOW() - make_interval(secs => %s)
             ORDER BY completed_at DESC
             LIMIT 1
            """,
            (_POLL_INTERVAL_SECS * 2,),
        )
        row = cur.fetchone()
        if not row:
            return
        job_id, project_id = row
        cur.execute(
            """
            INSERT INTO daemon_events (
                event_type, project_id, entity_id, message, metadata, created_at
            )
            SELECT %s, %s, %s, %s, %s::jsonb, NOW()
             WHERE NOT EXISTS (
                SELECT 1 FROM daemon_events
                 WHERE event_type = %s
                   AND entity_id = %s
            )
            """,
            (
                "code_map_completed",
                project_id,
                job_id,
                f"E2E stub: doc index {job_id} completed",
                "{}",
                "code_map_completed",
                job_id,
            ),
        )
    conn.commit()


def _tick(conn: psycopg.Connection) -> None:
    try:
        doc_moves = _advance_doc_index_jobs(conn)
        code_moves = _advance_code_index_jobs(conn)
        if doc_moves or code_moves:
            logger.info(
                "e2e-daemon-stub: advanced %d doc_index + %d code_index row(s)",
                doc_moves,
                code_moves,
            )
            try:
                _emit_lifecycle_events(conn)
            except psycopg.Error as exc:
                # A missing or renamed column here should not crash the loop.
                logger.warning("e2e-daemon-stub: could not emit lifecycle event: %s", exc)
                conn.rollback()
    except psycopg.Error as exc:
        logger.warning("e2e-daemon-stub: DB error during tick: %s", exc)
        with contextlib.suppress(psycopg.Error):
            conn.rollback()


def _install_signal_handlers(stop_flag: dict[str, bool]) -> None:
    def _handler(signum: int, _frame: types.FrameType | None) -> None:
        logger.info("e2e-daemon-stub: received signal %s, shutting down", signum)
        stop_flag["stop"] = True

    signal.signal(signal.SIGTERM, _handler)
    signal.signal(signal.SIGINT, _handler)


def main() -> int:
    logging.basicConfig(
        level=os.environ.get("E2E_DAEMON_STUB_LOG_LEVEL", "INFO"),
        format="%(asctime)s %(name)s [%(levelname)s] %(message)s",
    )
    stop_flag: dict[str, bool] = {"stop": False}
    _install_signal_handlers(stop_flag)

    dsn = _dsn()
    logger.info("e2e-daemon-stub: starting, poll=%.1fs", _POLL_INTERVAL_SECS)

    # Retry the initial connection so we don't race the DB healthcheck.
    conn: psycopg.Connection[Any] | None = None
    for attempt in range(30):
        if stop_flag["stop"]:
            return 0
        try:
            conn = psycopg.connect(dsn, connect_timeout=2)
            break
        except psycopg.Error as exc:  # noqa: PERF203
            logger.info("e2e-daemon-stub: DB not ready (attempt %d/30): %s", attempt + 1, exc)
            time.sleep(1.0)
    if conn is None:
        logger.error("e2e-daemon-stub: could not connect to DB after 30s; exiting")
        return 1

    try:
        while not stop_flag["stop"]:
            _tick(conn)
            # Sleep in small chunks so SIGTERM is responsive.
            slept = 0.0
            while slept < _POLL_INTERVAL_SECS and not stop_flag["stop"]:
                time.sleep(0.25)
                slept += 0.25
    finally:
        with contextlib.suppress(psycopg.Error):
            conn.close()

    logger.info("e2e-daemon-stub: stopped cleanly")
    return 0


if __name__ == "__main__":
    sys.exit(main())
