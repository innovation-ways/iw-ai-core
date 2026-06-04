"""Allowlist tests for ``orch.chat.tab_service`` (F-00087 extension of F-00086).

Invariant #7 — ALLOWED_RUNTIMES extension is one-line:
    - ``runtime="pi"`` is accepted (F-00087 adds "pi" to the allowlist).
    - ``runtime="opencode"`` still accepted (F-00086 baseline must not regress).
    - Truly unknown runtimes are still rejected.

These tests verify the single-line ``ALLOWED_RUNTIMES`` change in
``tab_service.py`` produced the right runtime acceptance/rejection behaviour.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from orch.chat import tab_service
from orch.db.models import ChatTab

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# F-00087 acceptance case — runtime="pi" is now allowed (invariant #7)
# ---------------------------------------------------------------------------


def test_create_tab_accepts_runtime_pi(
    db_session: Session,
    test_project: Any,
) -> None:
    """tab_service.create_tab with runtime='pi' must succeed (F-00087 one-line change).

    The chat_tabs row must be persisted with runtime='pi' and the correct model.
    """
    tab, soft_cap_exceeded = tab_service.create_tab(
        db_session,
        project_id=test_project.id,
        runtime="pi",
        model="minimax/MiniMax-M2.7",
    )
    db_session.flush()

    assert tab.id is not None
    assert tab.project_id == test_project.id
    assert tab.runtime == "pi"
    assert tab.model == "minimax/MiniMax-M2.7"
    assert tab.status == "active"
    assert soft_cap_exceeded is False


def test_create_tab_pi_persists_to_db(
    db_session: Session,
    test_project: Any,
) -> None:
    """A Pi tab row is written to the database and retrievable by get_tab."""
    tab, _ = tab_service.create_tab(
        db_session,
        project_id=test_project.id,
        runtime="pi",
        model="openai/gpt-5.3-codex",
        title="My Pi Tab",
    )
    db_session.flush()

    fetched = tab_service.get_tab(db_session, str(tab.id))
    assert fetched is not None
    assert fetched.runtime == "pi"
    assert fetched.model == "openai/gpt-5.3-codex"
    assert fetched.title == "My Pi Tab"
    assert fetched.status == "active"


# ---------------------------------------------------------------------------
# F-00086 baseline — runtime="opencode" still accepted (must not regress)
# ---------------------------------------------------------------------------


def test_create_tab_still_accepts_runtime_opencode(
    db_session: Session,
    test_project: Any,
) -> None:
    """runtime='opencode' must still be in the allowlist after the F-00087 change."""
    tab, _ = tab_service.create_tab(
        db_session,
        project_id=test_project.id,
        runtime="opencode",
        model="anthropic/claude-sonnet-4-7",
    )
    db_session.flush()

    assert tab.runtime == "opencode"
    assert tab.status == "active"


# ---------------------------------------------------------------------------
# Allowlist membership verification (static)
# ---------------------------------------------------------------------------


def test_allowed_runtimes_contains_pi() -> None:
    """ALLOWED_RUNTIMES frozenset must contain 'pi' after F-00087."""
    # frozenset({"pi"}) <= X is the subset test — fails if 'pi' is dropped.
    assert frozenset({"pi"}) <= tab_service.ALLOWED_RUNTIMES, (
        f"'pi' not in ALLOWED_RUNTIMES: {tab_service.ALLOWED_RUNTIMES!r}"
    )


def test_allowed_runtimes_contains_opencode() -> None:
    """ALLOWED_RUNTIMES frozenset must still contain 'opencode' (F-00086 baseline)."""
    # Guards the opencode baseline against removal by a later allowlist edit.
    assert frozenset({"opencode"}) <= tab_service.ALLOWED_RUNTIMES, (
        f"'opencode' not in ALLOWED_RUNTIMES: {tab_service.ALLOWED_RUNTIMES!r}"
    )


def test_truly_unknown_runtime_still_rejected(
    db_session: Session,
    test_project: Any,
) -> None:
    """A runtime that is not in ALLOWED_RUNTIMES must still raise ValueError."""
    with pytest.raises(
        ValueError,
        match=r"runtime 'totally_unknown' not in allowlist",
    ):
        tab_service.create_tab(
            db_session,
            project_id=test_project.id,
            runtime="totally_unknown",
            model="x/y",
        )
    # No row written.
    db_session.flush()
    rows = db_session.query(ChatTab).filter(ChatTab.project_id == test_project.id).all()
    assert rows == [], f"unexpected rows after rejected create_tab: {rows!r}"


# ---------------------------------------------------------------------------
# Mixed Pi + OpenCode tabs in same project
# ---------------------------------------------------------------------------


def test_pi_and_opencode_tabs_coexist(
    db_session: Session,
    test_project: Any,
) -> None:
    """Both runtimes can have active tabs in the same project simultaneously."""
    oc_tab, _ = tab_service.create_tab(
        db_session,
        project_id=test_project.id,
        runtime="opencode",
        model="anthropic/claude-sonnet-4-7",
        title="OC Tab",
    )
    pi_tab, _ = tab_service.create_tab(
        db_session,
        project_id=test_project.id,
        runtime="pi",
        model="minimax/MiniMax-M2.7",
        title="Pi Tab",
    )
    db_session.flush()

    tabs = tab_service.list_tabs(db_session, project_id=test_project.id)
    assert len(tabs) == 2

    runtimes = {t.runtime for t in tabs}
    assert runtimes == {"opencode", "pi"}, f"expected both runtimes in tab list, got {runtimes!r}"
