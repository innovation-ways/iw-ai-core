"""CRUD + soft-cap + soft-delete + reopen for ``chat_tabs`` (F-00086).

Module-level functions operating on a SQLAlchemy ``Session`` parameter.
The runtime allowlist is enforced here (matches CR-00062's ``cli_tool``
pattern, so adding the ``pi`` runtime in F-B is a one-line change to
``ALLOWED_RUNTIMES`` and an entry in the runtime registry — no migration).

Invariants this module enforces (cross-referenced from
``ai-dev/active/F-00086/F-00086_Feature_Design.md`` §Invariants):

* **#3 runtime allowlist** — ``create_tab`` raises ``ValueError`` when
  ``runtime`` is not in :data:`ALLOWED_RUNTIMES`.
* **#4 soft cap** — ``create_tab`` returns ``(tab, soft_cap_exceeded)``;
  the flag is True iff the active-tab count for ``project_id`` exceeded
  10 after the insert.
* **#5 soft-delete preserves session id** — ``close_tab`` does NOT clear
  ``opencode_session_id``; ``reopen_tab`` restores ``status='active'``.
* **#8 empty-body PATCH** — ``update_tab(...)`` with no fields supplied
  is a no-op and does NOT bump ``updated_at``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import func, select

from orch.db.models import ChatTab

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

# F-B will widen this to ``frozenset({"opencode", "pi"})``; the migration
# is unchanged because ``chat_tabs.runtime`` is plain TEXT.
ALLOWED_RUNTIMES: frozenset[str] = frozenset({"opencode"})

# Soft-cap threshold for active tabs per project (invariant #4). The cap
# is advisory — exceeding it returns the warning flag but the tab is
# always persisted.
SOFT_CAP_ACTIVE_TABS: int = 10


def _utcnow() -> datetime:
    return datetime.now(UTC)


def create_tab(
    db: Session,
    *,
    project_id: str,
    runtime: str = "opencode",
    model: str,
    title: str = "New chat",
    agent: str | None = None,  # noqa: ARG001 — reserved for runtime selectors
    opencode_session_id: str | None = None,
) -> tuple[ChatTab, bool]:
    """Persist a new ``chat_tabs`` row.

    Returns ``(tab, soft_cap_exceeded)``. The flag is True when the
    active-tab count after this insert exceeds :data:`SOFT_CAP_ACTIVE_TABS`.
    The row is always written; the cap is advisory.

    Raises ``ValueError`` when ``runtime`` is not in :data:`ALLOWED_RUNTIMES`
    (invariant #3). No DB write is attempted in that case.
    """
    if runtime not in ALLOWED_RUNTIMES:
        raise ValueError(f"runtime '{runtime}' not in allowlist {set(ALLOWED_RUNTIMES)!r}")

    tab = ChatTab(
        project_id=project_id,
        runtime=runtime,
        model=model,
        title=title,
        opencode_session_id=opencode_session_id,
        status="active",
    )
    db.add(tab)
    db.flush()

    # Post-insert active count, scoped to the same project. The cap is
    # advisory — exceeding it sets the warning flag; the new tab is kept.
    active_count: int = db.execute(
        select(func.count())
        .select_from(ChatTab)
        .where(ChatTab.project_id == project_id, ChatTab.status == "active")
    ).scalar_one()
    soft_cap_exceeded = active_count > SOFT_CAP_ACTIVE_TABS

    return tab, soft_cap_exceeded


def list_tabs(
    db: Session,
    *,
    project_id: str,
    include_closed: bool = False,
) -> list[ChatTab]:
    """Return active tabs ordered by ``last_active_at DESC``.

    When ``include_closed=True`` closed tabs follow the active ones (also
    ordered by ``last_active_at DESC``).
    """
    stmt = select(ChatTab).where(ChatTab.project_id == project_id)
    if not include_closed:
        stmt = stmt.where(ChatTab.status == "active")
    stmt = stmt.order_by(ChatTab.status.asc(), ChatTab.last_active_at.desc())
    return list(db.execute(stmt).scalars().all())


def get_tab(db: Session, tab_id: str) -> ChatTab | None:
    return db.get(ChatTab, tab_id)


def update_tab(
    db: Session,
    tab_id: str,
    *,
    title: str | None = None,
    model: str | None = None,
) -> ChatTab:
    """Patch ``title`` and/or ``model``.

    Empty patch (both args None) is a no-op and does NOT bump
    ``updated_at`` (invariant #8). Caller is responsible for handling
    ``tab_id`` not found via the returned exception.
    """
    tab = db.get(ChatTab, tab_id)
    if tab is None:
        raise LookupError(f"chat_tab '{tab_id}' not found")

    if title is None and model is None:
        return tab

    if title is not None:
        tab.title = title
    if model is not None:
        tab.model = model
    tab.updated_at = _utcnow()
    db.flush()
    return tab


def close_tab(db: Session, tab_id: str) -> ChatTab:
    """Soft-delete: set ``status='closed'`` + ``closed_at=now()``.

    Idempotent: if the tab is already closed, returns it unchanged (the
    original ``closed_at`` is preserved so callers can audit when the
    close first happened). The ``opencode_session_id`` is intentionally
    NOT cleared so ``reopen_tab`` can resurrect the full history
    (invariant #5).
    """
    tab = db.get(ChatTab, tab_id)
    if tab is None:
        raise LookupError(f"chat_tab '{tab_id}' not found")
    if tab.status == "closed":
        return tab
    tab.status = "closed"
    tab.closed_at = _utcnow()
    tab.updated_at = _utcnow()
    db.flush()
    return tab


def reopen_tab(db: Session, tab_id: str) -> ChatTab:
    """Un-soft-delete: set ``status='active'`` + clear ``closed_at``.

    Idempotent: if the tab is already active, returns it unchanged.
    """
    tab = db.get(ChatTab, tab_id)
    if tab is None:
        raise LookupError(f"chat_tab '{tab_id}' not found")
    if tab.status == "active":
        return tab
    tab.status = "active"
    tab.closed_at = None
    tab.updated_at = _utcnow()
    tab.last_active_at = _utcnow()
    db.flush()
    return tab


def recent_closed_tabs(
    db: Session,
    *,
    project_id: str,
    limit: int = 10,
) -> list[ChatTab]:
    """Closed tabs for ``project_id`` ordered by ``closed_at DESC``."""
    stmt = (
        select(ChatTab)
        .where(ChatTab.project_id == project_id, ChatTab.status == "closed")
        .order_by(ChatTab.closed_at.desc())
        .limit(limit)
    )
    return list(db.execute(stmt).scalars().all())


def touch_last_active(db: Session, tab_id: str) -> None:
    """Bump ``last_active_at`` to ``now()``.

    Used by ``RelayManager`` / prompt endpoints to keep the tab strip
    ordering fresh. Silently a no-op when the tab does not exist
    (callers are e.g. background pumps that should not crash on a tab
    that was just closed).
    """
    tab = db.get(ChatTab, tab_id)
    if tab is None:
        return
    tab.last_active_at = _utcnow()
    db.flush()


def count_tabs(db: Session, *, project_id: str, include_closed: bool = True) -> int:
    """Count tabs for ``project_id``.

    ``include_closed=True`` (the default) counts active **and** closed
    rows — used by ``bootstrap_default_tab`` to enforce the
    "zero rows" intent-preservation gate (invariant #6).
    """
    stmt = select(func.count()).select_from(ChatTab).where(ChatTab.project_id == project_id)
    if not include_closed:
        stmt = stmt.where(ChatTab.status == "active")
    return db.execute(stmt).scalar_one()
