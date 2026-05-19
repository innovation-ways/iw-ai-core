# Integration tests for agent_runtime_options (F-00081)
# RED phase: write tests that define expected behavior.
# GREEN phase: add model + migration to make them pass.

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError


@pytest.fixture
def seed_agent_runtime_options(db_session):
    """Insert the runtime option seed rows before each test.

    Uses ON CONFLICT DO NOTHING so this fixture is idempotent whether
    or not the Alembic migration already seeded the table.
    """
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
    for row in seed_rows:
        db_session.execute(
            text("""
                INSERT INTO agent_runtime_options
                (id, cli_tool, model, cli_label, model_label, display_name,
                 is_default, enabled, sort_order)
                VALUES (:id, :cli_tool, :model, :cli_label, :model_label,
                        :display_name, :is_default, :enabled, :sort_order)
                ON CONFLICT (id) DO NOTHING
            """),
            row,
        )
    db_session.commit()
    return


class TestAgentRuntimeOptionsTable:
    """Verify the agent_runtime_options table and its constraints."""

    def test_table_exists(self, db_session) -> None:
        """Table must exist and be queryable."""
        db_session.execute(text("SELECT 1 FROM agent_runtime_options LIMIT 1"))

    def test_all_columns_present(self, db_session) -> None:
        """All required columns exist with correct types."""
        rows = db_session.execute(
            text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'agent_runtime_options'
                ORDER BY ordinal_position
            """)
        ).fetchall()
        col_names = {r[0] for r in rows}
        required = {
            "id",
            "cli_tool",
            "model",
            "cli_label",
            "model_label",
            "display_name",
            "is_default",
            "enabled",
            "sort_order",
        }
        assert required.issubset(col_names), f"Missing columns: {required - col_names}"

    def test_seed_rows_present(self, db_session, seed_agent_runtime_options) -> None:
        """All seed rows are present with correct values.

        CR-00062 added two Pi rows (sort_order=25 and 26) via Alembic
        migration ``6d78323d0954_add_pi_runtime_options``. The fixture
        re-seeds the F-00081 rows with ``ON CONFLICT (id) DO NOTHING``,
        so the table holds the F-00081 + GPT-5.3 Codex + Pi rows after
        migration.
        """
        rows = db_session.execute(
            text("""
                SELECT cli_tool, model, is_default, sort_order
                FROM agent_runtime_options
                ORDER BY sort_order
            """)
        ).fetchall()
        assert len(rows) == 8, f"Expected 8 rows, got {len(rows)}"
        assert rows[0] == ("opencode", "minimax/MiniMax-M2.7", True, 10)
        assert rows[1] == ("opencode", "openai/gpt-5.3-codex", False, 15)
        assert rows[2] == ("opencode", "claude-sonnet-4-6", False, 20)
        assert rows[3] == ("pi", "minimax/MiniMax-M2.7", False, 25)
        assert rows[4] == ("pi", "openai/gpt-5.3-codex", False, 26)
        assert rows[5] == ("opencode", "claude-opus-4-7", False, 30)
        assert rows[6] == ("claude", "claude-sonnet-4-6", False, 40)
        assert rows[7] == ("claude", "claude-opus-4-7", False, 50)

    def test_unique_constraint_on_cli_tool_model(
        self, db_session, seed_agent_runtime_options
    ) -> None:
        """Uniqueness on (cli_tool, model) is enforced."""
        stmt = text("""
            INSERT INTO agent_runtime_options
            (cli_tool, model, cli_label, model_label, display_name,
             is_default, enabled, sort_order)
            VALUES ('opencode', 'minimax/MiniMax-M2.7', 'X', 'X', 'X', false, true, 99)
        """)
        with pytest.raises(IntegrityError):
            db_session.execute(stmt)
        db_session.rollback()

    def test_only_one_default_row(self, db_session, seed_agent_runtime_options) -> None:
        """Partial unique index enforces at most one is_default=true row."""
        stmt = text("""
            INSERT INTO agent_runtime_options
            (cli_tool, model, cli_label, model_label, display_name,
             is_default, enabled, sort_order)
            VALUES ('opencode', 'bogus', 'X', 'X', 'X', true, true, 99)
        """)
        with pytest.raises(IntegrityError):
            db_session.execute(stmt)
        db_session.rollback()

    def test_cannot_disable_default_row(self, db_session, seed_agent_runtime_options) -> None:
        """CHECK constraint rejects enabled=false when is_default=true."""
        stmt = text("UPDATE agent_runtime_options SET enabled=false WHERE is_default=true")
        with pytest.raises(IntegrityError):
            db_session.execute(stmt)
        db_session.rollback()

    def test_can_disable_non_default_row(self, db_session, seed_agent_runtime_options) -> None:
        """Non-default rows can be disabled.

        Seven non-default rows: 5 F-00081 seeds (minus the MiniMax 2.7
        default) + 1 OpenCode GPT-5.3 Codex + 2 Pi rows (CR-00062).
        """
        result = db_session.execute(
            text("""
                UPDATE agent_runtime_options
                SET enabled=false
                WHERE is_default=false
                RETURNING id
            """)
        ).fetchall()
        db_session.commit()
        assert len(result) == 7  # 7 non-default rows


class TestAgentRuntimeOptionFKColumns:
    """Verify the FK columns on work_items, workflow_steps, step_runs."""

    def test_work_items_has_agent_runtime_option_id(self, db_session) -> None:
        """work_items.agent_runtime_option_id column exists and is nullable."""
        col_rows = db_session.execute(
            text("""
                SELECT is_nullable, data_type
                FROM information_schema.columns
                WHERE table_name = 'work_items' AND column_name = 'agent_runtime_option_id'
            """)
        ).fetchone()
        assert col_rows is not None, "work_items.agent_runtime_option_id not found"
        assert col_rows[0] == "YES", "work_items.agent_runtime_option_id must be nullable"

    def test_workflow_steps_has_agent_runtime_option_id(self, db_session) -> None:
        """workflow_steps.agent_runtime_option_id column exists and is nullable."""
        col_rows = db_session.execute(
            text("""
                SELECT is_nullable
                FROM information_schema.columns
                WHERE table_name = 'workflow_steps' AND column_name = 'agent_runtime_option_id'
            """)
        ).fetchone()
        assert col_rows is not None, "workflow_steps.agent_runtime_option_id not found"
        assert col_rows[0] == "YES"

    def test_step_runs_has_agent_runtime_option_id(self, db_session) -> None:
        """step_runs.agent_runtime_option_id column exists and is nullable."""
        col_rows = db_session.execute(
            text("""
                SELECT is_nullable
                FROM information_schema.columns
                WHERE table_name = 'step_runs' AND column_name = 'agent_runtime_option_id'
            """)
        ).fetchone()
        assert col_rows is not None, "step_runs.agent_runtime_option_id not found"
        assert col_rows[0] == "YES"

    def test_fk_referential_integrity_prevents_delete(
        self, db_session, test_project, seed_agent_runtime_options
    ) -> None:
        """Cannot delete an agent_runtime_option row referenced by step_runs.

        ON DELETE RESTRICT means the DB prevents deletion of a row that has
        historical references.
        """
        # Insert a step run that references the default option (id=1)
        default_option = db_session.execute(
            text("SELECT id FROM agent_runtime_options WHERE is_default=true")
        ).scalar_one()

        # Create a work item and step
        db_session.execute(
            text("""
                INSERT INTO work_items (project_id, id, type, title, status, phase)
                VALUES (:project_id, 'WI-001', 'Feature', 'Test', 'in_progress', 'work')
            """),
            {"project_id": test_project.id},
        )
        db_session.execute(
            text("""
                INSERT INTO workflow_steps
                (project_id, work_item_id, step_number, step_id, agent_label, step_type, status)
                VALUES (:project_id, 'WI-001', 1, 'S01', 'backend', 'implementation', 'completed')
            """),
            {"project_id": test_project.id},
        )
        step = db_session.execute(
            text("SELECT id FROM workflow_steps WHERE work_item_id='WI-001'")
        ).scalar_one()

        # Insert a step_run referencing the default option
        db_session.execute(
            text("""
                INSERT INTO step_runs (step_id, run_number, status, agent_runtime_option_id)
                VALUES (:step_id, 1, 'completed', :option_id)
            """),
            {"step_id": step, "option_id": default_option},
        )
        db_session.flush()

        # Attempt to delete the referenced option — must be blocked
        stmt = text("DELETE FROM agent_runtime_options WHERE id=:id")
        with pytest.raises(IntegrityError):
            db_session.execute(stmt, {"id": default_option})
        db_session.rollback()

    def test_item_level_override_stored(
        self, db_session, test_project, seed_agent_runtime_options
    ) -> None:
        """Setting agent_runtime_option_id on a work_item round-trips correctly."""
        db_session.execute(
            text("""
                INSERT INTO work_items
                (project_id, id, type, title, status, phase, agent_runtime_option_id)
                VALUES (:project_id, 'WI-002', 'Feature', 'Test', 'draft', 'active', 1)
            """),
            {"project_id": test_project.id},
        )
        db_session.flush()

        result = db_session.execute(
            text("SELECT agent_runtime_option_id FROM work_items WHERE id='WI-002'")
        ).scalar_one()
        assert result == 1

    def test_step_level_override_stored(
        self, db_session, test_project, seed_agent_runtime_options
    ) -> None:
        """Setting agent_runtime_option_id on a workflow_step round-trips correctly."""
        db_session.execute(
            text("""
                INSERT INTO work_items (project_id, id, type, title, status, phase)
                VALUES (:project_id, 'WI-003', 'Feature', 'Test', 'draft', 'active')
            """),
            {"project_id": test_project.id},
        )
        db_session.execute(
            text("""
                INSERT INTO workflow_steps
                (project_id, work_item_id, step_number, step_id, agent_label,
                 step_type, status, agent_runtime_option_id)
                VALUES (:project_id, 'WI-003', 1, 'S01', 'backend',
                        'implementation', 'pending', 3)
            """),
            {"project_id": test_project.id},
        )
        db_session.flush()

        result = db_session.execute(
            text("SELECT agent_runtime_option_id FROM workflow_steps WHERE work_item_id='WI-003'")
        ).scalar_one()
        assert result == 3

    def test_null_agent_runtime_option_id_allowed(self, db_session, test_project) -> None:
        """Nullable FK allows NULL (no override) — existing rows unaffected."""
        db_session.execute(
            text("""
                INSERT INTO work_items (project_id, id, type, title, status, phase)
                VALUES (:project_id, 'WI-004', 'Feature', 'Test', 'draft', 'active')
            """),
            {"project_id": test_project.id},
        )
        db_session.flush()

        result = db_session.execute(
            text("SELECT agent_runtime_option_id FROM work_items WHERE id='WI-004'")
        ).scalar_one_or_none()
        assert result is None  # NULL, no override
