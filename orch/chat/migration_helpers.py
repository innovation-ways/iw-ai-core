"""One-time bootstrap of a "Default" chat tab for legacy users (F-00086).

When the AI Assistant ships its first multi-tab UI, projects that had an
ongoing OpenCode chat under the F-00083 single-session model would lose
their session pointer unless something seeds a tab from the existing
runtime state. ``bootstrap_default_tab`` is that seed.

The gate is intentionally **"zero ``chat_tabs`` rows for the project,
active OR closed"** — once any row exists, bootstrap MUST NOT fire.
This preserves the user's intent in two distinct scenarios:

1. The user already used the tab UI and (correctly) has tabs.
2. The user used the tab UI and then closed every tab. Re-firing
   bootstrap would resurrect a prior OpenCode session that the user
   intentionally walked away from.

Both scenarios collapse into "any row at all" so the helper is a
trivial idempotent no-op after first use.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from sqlalchemy.exc import IntegrityError

from orch.chat import tab_service
from orch.db.models import ChatTab

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from orch.chat.runtime_base import ChatRuntime

logger = logging.getLogger(__name__)


def _pick_most_recent_session(
    sessions: list[dict[str, Any]],
    project_repo_root: str | None,
) -> dict[str, Any] | None:
    """Return the most-recent OpenCode session whose CWD matches the project.

    When ``project_repo_root`` is None, all sessions are eligible.
    OpenCode session dicts may name the directory field differently across
    versions — we accept any of ``cwd``, ``directory``, ``workingDir``,
    ``working_dir``. Recency is read from ``created_at`` / ``createdAt`` /
    ``time.created`` (whichever the session blob exposes); sessions with no
    recoverable timestamp sort to the end.
    """
    if project_repo_root is None:
        matches: list[dict[str, Any]] = list(sessions)
    else:
        matches = [s for s in sessions if _session_cwd(s) == project_repo_root]

    if not matches:
        return None

    matches.sort(key=_session_created_at, reverse=True)
    return matches[0]


def _session_cwd(session: dict[str, Any]) -> str | None:
    """Return the working directory from a session blob, or None if absent."""
    for key in ("cwd", "directory", "workingDir", "working_dir"):
        v = session.get(key)
        if isinstance(v, str) and v:
            return v
    return None


def _session_created_at(session: dict[str, Any]) -> float:
    """Return a sort key for session recency; missing values sort last."""
    for key in ("created_at", "createdAt"):
        v = session.get(key)
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str):
            # Best-effort numeric coercion; opaque strings sort last.
            try:
                return float(v)
            except ValueError:
                continue
    time_blob = session.get("time")
    if isinstance(time_blob, dict):
        v = time_blob.get("created")
        if isinstance(v, (int, float)):
            return float(v)
    return float("-inf")


async def bootstrap_default_tab(
    db: Session,
    *,
    project_id: str,
    runtime: ChatRuntime,
    project_repo_root: str | None,
    default_model: str,
) -> ChatTab | None:
    """Seed a single "Default" chat tab for ``project_id`` if appropriate.

    Returns the seeded tab, or ``None`` when no seeding happened.

    Gates:

    1. ``chat_tabs`` for ``project_id`` must have **zero rows** (active OR
       closed). If any row exists, returns None — bootstrap MUST NOT
       resurrect a session the user intentionally closed (invariant #6).
    2. ``runtime.list_sessions()`` must return a session whose CWD matches
       ``project_repo_root``. When ``project_repo_root`` is None we accept
       any session.

    Concurrency-safe: races are guarded by the
    ``uq_chat_tabs_default_per_project`` partial unique index defined in
    S01's migration (``UNIQUE (project_id) WHERE title='Default' AND
    status='active'``). On collision we swallow the ``IntegrityError``,
    rollback the failed insert, and re-fetch the winner's row to return.

    Async: ``runtime.list_sessions()`` is awaited directly so the helper
    can run inside an active event loop (e.g. the dashboard request
    handler). Tests that need to drive the helper from sync code should
    use ``asyncio.run(bootstrap_default_tab(...))``.
    """
    if tab_service.count_tabs(db, project_id=project_id, include_closed=True) > 0:
        return None

    sessions = await runtime.list_sessions()
    picked = _pick_most_recent_session(sessions, project_repo_root)
    if picked is None:
        return None

    session_id = picked.get("id")
    if not isinstance(session_id, str) or not session_id:
        logger.warning(
            "bootstrap_default_tab: matching session has no id; skipping (session=%r)",
            picked,
        )
        return None

    try:
        tab, _soft_cap = tab_service.create_tab(
            db,
            project_id=project_id,
            runtime="opencode",
            model=default_model,
            title="Default",
            opencode_session_id=session_id,
        )
        db.flush()
    except IntegrityError:
        # The race-loser branch: another caller won the partial unique
        # index. Rollback our partial state and read the winner's row.
        db.rollback()
        return (
            db.query(ChatTab)
            .filter(
                ChatTab.project_id == project_id,
                ChatTab.title == "Default",
                ChatTab.status == "active",
            )
            .one_or_none()
        )

    return tab
