"""Integration tests for resolve_inherited_runtime() (CR-00070 S01).

RED phase: define expected behaviour.
GREEN phase: implement the helper in orch/agent_runtime/resolver.py.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest  # noqa: F401 — needed for pytest fixtures (db_session, test_project)
from sqlalchemy import text

from orch.agent_runtime.resolver import resolve_inherited_runtime, resolve_runtime

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Seed helpers (same pattern as test_agent_runtime_options.py)
# ---------------------------------------------------------------------------


def _seed_runtime_options(db_session: Session) -> dict[int, str]:
    """Seed agent_runtime_options rows; return {id: display_name} map.

    Uses ON CONFLICT DO UPDATE so that rows already present in the
    template DB (from previous tests) are corrected to match the
    expected fixture state.
    """
    # Clear the default flag first (before we re-assign it to id=1), to avoid
    # a CHECK violation when the template already has another is_default row.
    db_session.execute(text("UPDATE agent_runtime_options SET is_default=false"))
    db_session.flush()

    seed_rows = [
        {
            "id": 1,
            "cli_tool": "opencode",
            "model": "minimax/MiniMax-M2.7",
            "cli_label": "OpenCode",
            "model_label": "MiniMax 2.7",
            "display_name": "OpenCode + MiniMax 2.7",
            "is_default": True,
            "enabled": True,
            "sort_order": 10,
        },
        {
            "id": 6,
            "cli_tool": "opencode",
            "model": "openai/gpt-5.3-codex",
            "cli_label": "OpenCode",
            "model_label": "GPT-5.3 Codex",
            "display_name": "OpenCode + GPT-5.3 Codex",
            "is_default": False,
            "enabled": True,
            "sort_order": 15,
        },
        {
            "id": 2,
            "cli_tool": "opencode",
            "model": "claude-sonnet-4-6",
            "cli_label": "OpenCode",
            "model_label": "Claude Sonnet 4.6",
            "display_name": "OpenCode + Claude Sonnet 4.6",
            "is_default": False,
            "enabled": True,
            "sort_order": 20,
        },
        {
            "id": 3,
            "cli_tool": "opencode",
            "model": "claude-opus-4-7",
            "cli_label": "OpenCode",
            "model_label": "Claude Opus 4.7",
            "display_name": "OpenCode + Claude Opus 4.7",
            "is_default": False,
            "enabled": True,
            "sort_order": 30,
        },
        {
            "id": 4,
            "cli_tool": "claude",
            "model": "claude-sonnet-4-6",
            "cli_label": "Claude Code",
            "model_label": "Sonnet 4.6",
            "display_name": "Claude Code + Sonnet 4.6",
            "is_default": False,
            "enabled": True,
            "sort_order": 40,
        },
        {
            "id": 5,
            "cli_tool": "claude",
            "model": "claude-opus-4-7",
            "cli_label": "Claude Code",
            "model_label": "Opus 4.7",
            "display_name": "Claude Code + Opus 4.7",
            "is_default": False,
            "enabled": True,
            "sort_order": 50,
        },
    ]
    display_map: dict[int, str] = {}
    for row in seed_rows:
        display_map[row["id"]] = row["display_name"]
        db_session.execute(
            text("""
                INSERT INTO agent_runtime_options
                (id, cli_tool, model, cli_label, model_label, display_name,
                 is_default, enabled, sort_order)
                VALUES (:id, :cli_tool, :model, :cli_label, :model_label,
                        :display_name, :is_default, :enabled, :sort_order)
                ON CONFLICT (id) DO UPDATE SET
                    cli_tool = EXCLUDED.cli_tool,
                    model = EXCLUDED.model,
                    cli_label = EXCLUDED.cli_label,
                    model_label = EXCLUDED.model_label,
                    display_name = EXCLUDED.display_name,
                    is_default = EXCLUDED.is_default,
                    enabled = EXCLUDED.enabled,
                    sort_order = EXCLUDED.sort_order
            """),
            row,
        )
    db_session.commit()
    return display_map


def _make_project_config(cli_tool: str = "opencode", model: str = "minimax") -> object:
    """Return a minimal project-like object with cli_tool + model attributes."""

    class FakeProject:
        cli_tool: str
        model: str

    p = FakeProject()
    p.cli_tool = cli_tool
    p.model = model
    return p


# ---------------------------------------------------------------------------
# AC2: item-level override — inherited label shows item override (not catalogue default)
# ---------------------------------------------------------------------------


class TestResolveInheritedRuntimeItemOverride:
    """AC2: inherited runtime reflects the item-level override."""

    def test_item_override_returns_that_option(self, db_session: Session, test_project) -> None:
        """With WorkItem.agent_runtime_option_id=3, resolve_inherited_runtime returns id=3."""
        _seed_runtime_options(db_session)

        # Insert a work item with item-level override id=3
        db_session.execute(
            text("""
                INSERT INTO work_items
                (project_id, id, type, title, status, phase, agent_runtime_option_id)
                VALUES (:project_id, 'WI-CR70-ITEM', 'Feature', 'Test', 'in_progress', 'active', 3)
            """),
            {"project_id": test_project.id},
        )
        db_session.flush()

        from orch.db.models import WorkItem

        item = db_session.query(WorkItem).filter_by(id="WI-CR70-ITEM").one()

        result = resolve_inherited_runtime(db_session, item=item, project=None)

        assert result is not None, "Expected a resolved option, got None"
        assert result.id == 3, f"Expected id=3, got {result.id}"
        assert result.display_name == "OpenCode + Claude Opus 4.7"

    def test_item_override_overrides_project_default(
        self, db_session: Session, test_project
    ) -> None:
        """Item override (id=4) must win over project.toml lookup (opencode, minimax)."""
        _seed_runtime_options(db_session)

        db_session.execute(
            text("""
                INSERT INTO work_items
                (project_id, id, type, title, status, phase, agent_runtime_option_id)
                VALUES (:project_id, 'WI-CR70-OVR', 'Feature', 'Test', 'in_progress', 'active', 4)
            """),
            {"project_id": test_project.id},
        )
        db_session.flush()

        from orch.db.models import WorkItem

        item = db_session.query(WorkItem).filter_by(id="WI-CR70-OVR").one()
        project_cfg = _make_project_config(cli_tool="opencode", model="minimax")

        result = resolve_inherited_runtime(db_session, item=item, project=project_cfg)

        assert result is not None
        assert result.id == 4, f"Expected id=4, got {result.id}"
        assert result.cli_tool == "claude"


# ---------------------------------------------------------------------------
# AC1: no item-level override — cascade to projects.toml lookup / catalogue default
# ---------------------------------------------------------------------------


class TestResolveInheritedRuntimeNoItemOverride:
    """AC1: inherited runtime falls through to project.toml or catalogue default."""

    def test_no_item_override_uses_project_lookup(self, db_session: Session, test_project) -> None:
        """With no item override, resolve_inherited_runtime uses project.toml.

        project.toml says opencode, claude-sonnet-4-6 which maps to id=2.
        """
        _seed_runtime_options(db_session)

        db_session.execute(
            text("""
                INSERT INTO work_items
                (project_id, id, type, title, status, phase)
                VALUES (:project_id, 'WI-CR70-NO-OVR', 'Feature', 'Test', 'in_progress', 'active')
            """),
            {"project_id": test_project.id},
        )
        db_session.flush()

        from orch.db.models import WorkItem

        item = db_session.query(WorkItem).filter_by(id="WI-CR70-NO-OVR").one()
        # project.toml says cli_tool=opencode, model=claude-sonnet-4-6 → id=2
        project_cfg = _make_project_config(cli_tool="opencode", model="claude-sonnet-4-6")

        result = resolve_inherited_runtime(db_session, item=item, project=project_cfg)

        assert result is not None
        assert result.id == 2, f"Expected id=2 (opencode+claude-sonnet), got {result.id}"

    def test_no_item_override_uses_catalogue_default_when_project_not_in_catalog(
        self, db_session: Session, test_project
    ) -> None:
        """With no item override and project.toml value not in catalogue, falls to default.

        This test seeds is_default=true row (id=1) AFTER the standard seed rows
        because the migration may have already set a different default row.
        """
        _seed_runtime_options(db_session)
        # Set id=1 as default (it may already be from migration, but be explicit)
        db_session.execute(
            text("UPDATE agent_runtime_options SET is_default=false WHERE is_default=true")
        )
        db_session.execute(text("UPDATE agent_runtime_options SET is_default=true WHERE id=1"))
        db_session.commit()

        db_session.execute(
            text("""
                INSERT INTO work_items
                (project_id, id, type, title, status, phase)
                VALUES (:project_id, 'WI-CR70-DEF', 'Feature', 'Test', 'in_progress', 'active')
            """),
            {"project_id": test_project.id},
        )
        db_session.flush()

        from orch.db.models import WorkItem

        item = db_session.query(WorkItem).filter_by(id="WI-CR70-DEF").one()
        # project.toml says opencode/xyz-not-in-catalogue → should fall back to default
        project_cfg = _make_project_config(cli_tool="opencode", model="some-nonexistent-model")

        result = resolve_inherited_runtime(db_session, item=item, project=project_cfg)

        assert result is not None
        assert result.is_default is True
        assert result.id == 1


# ---------------------------------------------------------------------------
# AC5: graceful fallback — empty catalogue → returns None (no raise)
# ---------------------------------------------------------------------------


class TestResolveInheritedRuntimeEmptyCatalogue:
    """AC5: empty catalogue → None, never raises."""

    def test_empty_catalogue_returns_none(self, db_session: Session, test_project) -> None:
        """With no agent_runtime_options rows, resolve_inherited_runtime returns None."""
        # Ensure no rows exist
        db_session.execute(text("DELETE FROM agent_runtime_options"))
        db_session.commit()

        db_session.execute(
            text("""
                INSERT INTO work_items
                (project_id, id, type, title, status, phase)
                VALUES (:project_id, 'WI-CR70-EMPTY', 'Feature', 'Test', 'in_progress', 'active')
            """),
            {"project_id": test_project.id},
        )
        db_session.flush()

        from orch.db.models import WorkItem

        item = db_session.query(WorkItem).filter_by(id="WI-CR70-EMPTY").one()

        # Must not raise — AC5
        result = resolve_inherited_runtime(db_session, item=item, project=None)

        assert result is None, f"Expected None for empty catalogue, got {result}"

    def test_all_options_disabled_returns_none(self, db_session: Session, test_project) -> None:
        """With all options disabled (impossible in practice due to CHECK constraint on default),
        the function should still handle it gracefully by falling to catalogue default
        (but if default is also disabled, that's a CHECK-violating DB state, not our concern).

        More realistically: a project.toml value that matches no enabled row + no is_default row
        means the RuntimeError from resolve_runtime propagates. But since our helper catches it,
        we should return None.
        """
        _seed_runtime_options(db_session)
        # Disable all non-default rows (keep id=1 as enabled for catalogue default)
        db_session.execute(
            text("UPDATE agent_runtime_options SET is_default=false WHERE is_default=true")
        )
        db_session.execute(text("UPDATE agent_runtime_options SET enabled=false WHERE id != 1"))
        # Make id=1 NOT the default so even it won't resolve
        db_session.execute(text("UPDATE agent_runtime_options SET is_default=true WHERE id=999"))
        # This violates the one-default CHECK, but let's just ensure no enabled row matches
        # project.toml lookup AND no is_default row exists → RuntimeError → caught as None
        db_session.commit()

        db_session.execute(
            text("""
                INSERT INTO work_items
                (project_id, id, type, title, status, phase)
                VALUES (:project_id, 'WI-CR70-DISABLED', 'Feature', 'Test', 'in_progress', 'active')
            """),
            {"project_id": test_project.id},
        )
        db_session.flush()

        from orch.db.models import WorkItem

        item = db_session.query(WorkItem).filter_by(id="WI-CR70-DISABLED").one()
        project_cfg = _make_project_config(cli_tool="opencode", model="claude-sonnet-4-6")

        result = resolve_inherited_runtime(db_session, item=item, project=project_cfg)

        # The only enabled row is id=1 (opencode/minimax) which doesn't match
        # the project.toml lookup (claude-sonnet-4-6), and there's no is_default row
        # → RuntimeError → caught and returned as None
        assert result is None


# ---------------------------------------------------------------------------
# resolve_inherited_runtime is just resolve_runtime with a no-step-override sentinel
# ---------------------------------------------------------------------------


class TestResolveInheritedRuntimeEquivalence:
    """Sanity: resolve_inherited_runtime matches resolve_runtime for no-step-override case."""

    def test_matches_resolve_runtime_for_no_step_override(
        self, db_session: Session, test_project
    ) -> None:
        """With a WorkItem override and no step override, both functions return the same row."""
        _seed_runtime_options(db_session)

        db_session.execute(
            text("""
                INSERT INTO work_items
                (project_id, id, type, title, status, phase, agent_runtime_option_id)
                VALUES (:project_id, 'WI-CR70-EQ', 'Feature', 'Test', 'in_progress', 'active', 5)
            """),
            {"project_id": test_project.id},
        )
        db_session.flush()

        from orch.db.models import WorkItem

        item = db_session.query(WorkItem).filter_by(id="WI-CR70-EQ").one()
        project_cfg = _make_project_config()

        # A no-step-override sentinel (agent_runtime_option_id=None)
        class NoStepOverride:
            agent_runtime_option_id: int | None = None

        step_sentinel = NoStepOverride()

        inherited_result = resolve_inherited_runtime(db_session, item=item, project=project_cfg)
        cascade_result = resolve_runtime(
            db_session, step=step_sentinel, item=item, project=project_cfg
        )

        assert inherited_result is not None
        assert cascade_result is not None
        assert inherited_result.id == cascade_result.id == 5
