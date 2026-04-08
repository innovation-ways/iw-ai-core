"""Initial schema: all tables, ENUMs, indexes, and FTS trigger.

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2026-04-08 00:00:00.000000

"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa

if TYPE_CHECKING:
    from collections.abc import Sequence
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- ENUMs ---
    work_item_type = postgresql.ENUM(
        "Feature", "Issue", "ChangeRequest", name="work_item_type", create_type=False
    )
    work_item_status = postgresql.ENUM(
        "draft",
        "approved",
        "in_progress",
        "completed",
        "failed",
        "paused",
        name="work_item_status",
        create_type=False,
    )
    work_item_phase = postgresql.ENUM(
        "active", "work", "done", name="work_item_phase", create_type=False
    )
    step_type = postgresql.ENUM(
        "implementation",
        "code_review",
        "code_review_fix",
        "code_review_final",
        "code_review_fix_final",
        "quality_validation",
        "qv_fix",
        "browser_verification",
        name="step_type",
        create_type=False,
    )
    step_status = postgresql.ENUM(
        "pending",
        "in_progress",
        "completed",
        "failed",
        "needs_fix",
        "skipped",
        name="step_status",
        create_type=False,
    )
    run_status = postgresql.ENUM(
        "pending",
        "running",
        "completed",
        "failed",
        "timeout",
        "killed",
        "stalled",
        name="run_status",
        create_type=False,
    )
    fix_trigger = postgresql.ENUM(
        "code_review",
        "code_review_final",
        "quality_validation",
        name="fix_trigger",
        create_type=False,
    )
    fix_status = postgresql.ENUM(
        "pending",
        "in_progress",
        "completed",
        "failed",
        "escalated",
        name="fix_status",
        create_type=False,
    )
    batch_status = postgresql.ENUM(
        "planning",
        "approved",
        "executing",
        "paused",
        "completed",
        "completed_with_errors",
        "publishing",
        "published",
        "publish_failed",
        "blocked",
        "archived",
        name="batch_status",
        create_type=False,
    )
    batch_item_status = postgresql.ENUM(
        "pending",
        "setting_up",
        "executing",
        "completed",
        "merged",
        "failed",
        "stalled",
        "skipped",
        name="batch_item_status",
        create_type=False,
    )

    # Create ENUM types in the DB
    for enum_type in [
        work_item_type,
        work_item_status,
        work_item_phase,
        step_type,
        step_status,
        run_status,
        fix_trigger,
        fix_status,
        batch_status,
        batch_item_status,
    ]:
        enum_type.create(op.get_bind(), checkfirst=True)

    # --- projects ---
    op.create_table(
        "projects",
        sa.Column(
            "id", sa.Text(), nullable=False, comment="Unique project identifier (e.g., 'innoforge')"
        ),
        sa.Column("display_name", sa.Text(), nullable=False, comment="Human-readable project name"),
        sa.Column(
            "repo_root",
            sa.Text(),
            nullable=False,
            comment="Absolute path to the main clone repo root",
        ),
        sa.Column(
            "dev_clone",
            sa.Text(),
            nullable=True,
            comment="Absolute path to the development clone (optional)",
        ),
        sa.Column(
            "config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'"),
            comment="Full .iw-orch.json content as JSONB",
        ),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
            comment="Whether the daemon processes this project",
        ),
        sa.Column(
            "registered_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id"),
        comment="Registry of software projects managed by IW AI Core",
    )

    # --- id_sequences ---
    op.create_table(
        "id_sequences",
        sa.Column("project_id", sa.Text(), nullable=False),
        sa.Column(
            "prefix",
            sa.Text(),
            nullable=False,
            comment="ID prefix: 'F' (Feature), 'I' (Issue), 'CR' (ChangeRequest), 'BATCH'",
        ),
        sa.Column(
            "next_number",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
            comment="Next number to allocate (incremented atomically via FOR UPDATE)",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("project_id", "prefix"),
        comment="Atomic sequential ID allocation per project and type",
    )

    # --- work_items ---
    op.create_table(
        "work_items",
        sa.Column("project_id", sa.Text(), nullable=False),
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("type", work_item_type, nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("status", work_item_status, nullable=False, server_default=sa.text("'draft'")),
        sa.Column("phase", work_item_phase, nullable=False, server_default=sa.text("'active'")),
        sa.Column(
            "config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'"),
            comment="Item-level config: fix_cycle_max, browser_verification, etc.",
        ),
        sa.Column(
            "depends_on",
            sa.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'"),
            comment="Array of work item IDs this item depends on",
        ),
        sa.Column(
            "blocks",
            sa.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'"),
            comment="Array of work item IDs this item blocks",
        ),
        sa.Column(
            "design_doc_path",
            sa.Text(),
            nullable=True,
            comment="Relative path to design doc in project repo (active items)",
        ),
        sa.Column(
            "design_doc_content",
            sa.Text(),
            nullable=True,
            comment="Full markdown of design doc (Tier 1 — stored on archive for instant dashboard rendering)",
        ),
        sa.Column(
            "design_doc_search",
            postgresql.TSVECTOR(),
            nullable=True,
            comment="PostgreSQL tsvector for full-text search across design docs",
        ),
        sa.Column(
            "summary",
            sa.Text(),
            nullable=True,
            comment="AI-generated 2-3 line summary for list views and search results",
        ),
        sa.Column(
            "archive_path",
            sa.Text(),
            nullable=True,
            comment="Relative path to .tar.zst in archive directory (Tier 2)",
        ),
        sa.Column(
            "archive_size_bytes",
            sa.BigInteger(),
            nullable=True,
            comment="Compressed archive file size in bytes",
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "archived_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When the item was archived (Tier 1 + Tier 2 stored, active files deleted)",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("project_id", "id"),
        comment="Features, Incidents, and Change Requests across all projects",
    )
    op.create_index("idx_work_items_status", "work_items", ["project_id", "status"])
    op.create_index("idx_work_items_phase", "work_items", ["project_id", "phase"])
    op.create_index("idx_work_items_type", "work_items", ["project_id", "type"])
    op.create_index(
        "idx_work_items_fts", "work_items", ["design_doc_search"], postgresql_using="gin"
    )
    op.create_index(
        "idx_work_items_created", "work_items", ["project_id", sa.text("created_at DESC")]
    )

    # --- FTS function and trigger ---
    op.execute("""\
CREATE OR REPLACE FUNCTION work_items_fts_update() RETURNS trigger AS $$
BEGIN
    IF NEW.design_doc_content IS NOT NULL THEN
        NEW.design_doc_search := to_tsvector('english', NEW.title || ' ' || NEW.design_doc_content);
    ELSE
        NEW.design_doc_search := to_tsvector('english', NEW.title);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
""")
    op.execute("""\
CREATE TRIGGER trg_work_items_fts
    BEFORE INSERT OR UPDATE OF title, design_doc_content
    ON work_items
    FOR EACH ROW
    EXECUTE FUNCTION work_items_fts_update();
""")

    # --- workflow_steps ---
    op.create_table(
        "workflow_steps",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Text(), nullable=False),
        sa.Column("work_item_id", sa.Text(), nullable=False),
        sa.Column("step_number", sa.Integer(), nullable=False),
        sa.Column(
            "step_id",
            sa.Text(),
            nullable=False,
            comment="Step identifier within the item (e.g., 'S01', 'S02')",
        ),
        sa.Column(
            "agent_label",
            sa.Text(),
            nullable=False,
            comment="Agent label for file naming (e.g., 'Backend', 'CodeReview_Backend')",
        ),
        sa.Column(
            "opencode_agent",
            sa.Text(),
            nullable=True,
            comment="OpenCode/Claude agent to invoke (e.g., 'backend-impl', 'code-review-impl')",
        ),
        sa.Column("step_type", step_type, nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", step_status, nullable=False, server_default=sa.text("'pending'")),
        sa.Column(
            "prompt_file",
            sa.Text(),
            nullable=True,
            comment="Relative path to the prompt file in the project repo",
        ),
        sa.Column(
            "report_file",
            sa.Text(),
            nullable=True,
            comment="Relative path to the report file (latest run)",
        ),
        sa.Column(
            "report_content",
            sa.Text(),
            nullable=True,
            comment="Full report markdown (Tier 1 — stored on archive for instant dashboard rendering)",
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["project_id", "work_item_id"],
            ["work_items.project_id", "work_items.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "work_item_id", "step_number"),
        comment="Workflow step definitions for each work item",
    )
    op.create_index("idx_workflow_steps_item", "workflow_steps", ["project_id", "work_item_id"])
    op.create_index(
        "idx_workflow_steps_status", "workflow_steps", ["project_id", "work_item_id", "status"]
    )

    # --- step_runs ---
    op.create_table(
        "step_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("step_id", sa.Integer(), nullable=False),
        sa.Column("run_number", sa.Integer(), nullable=False),
        sa.Column("status", run_status, nullable=False, server_default=sa.text("'pending'")),
        sa.Column(
            "pid",
            sa.Integer(),
            nullable=True,
            comment="OS process ID of the LLM session (for kill -0 and SIGTERM)",
        ),
        sa.Column(
            "pid_alive",
            sa.Boolean(),
            nullable=True,
            server_default=sa.text("false"),
            comment="Whether the process is currently alive (set by daemon every poll cycle)",
        ),
        sa.Column(
            "command",
            sa.Text(),
            nullable=True,
            comment="Exact shell command used to launch (enables one-click restart)",
        ),
        sa.Column(
            "worktree_path",
            sa.Text(),
            nullable=True,
            comment="Full path to the git worktree where the agent runs",
        ),
        sa.Column(
            "cli_tool",
            sa.Text(),
            nullable=True,
            comment="LLM CLI tool used: 'opencode' or 'claude'",
        ),
        sa.Column(
            "last_heartbeat",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Last time daemon confirmed PID was alive (for stall detection)",
        ),
        sa.Column(
            "timeout_secs",
            sa.Integer(),
            nullable=True,
            comment="Dynamic timeout for this step type (not a global constant)",
        ),
        sa.Column(
            "error_message",
            sa.Text(),
            nullable=True,
            comment="Human-readable reason for failure, timeout, or kill",
        ),
        sa.Column("exit_code", sa.Integer(), nullable=True),
        sa.Column("log_file", sa.Text(), nullable=True),
        sa.Column("report_file", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_secs", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["step_id"], ["workflow_steps.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("step_id", "run_number"),
        comment="Execution attempts for workflow steps. Append-only — each retry creates a new row.",
    )
    op.create_index("idx_step_runs_step", "step_runs", ["step_id"])
    op.create_index(
        "idx_step_runs_status",
        "step_runs",
        ["status"],
        postgresql_where=sa.text("status IN ('pending', 'running', 'stalled')"),
    )

    # --- fix_cycles ---
    op.create_table(
        "fix_cycles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("step_id", sa.Integer(), nullable=False),
        sa.Column("cycle_number", sa.Integer(), nullable=False),
        sa.Column("trigger_type", fix_trigger, nullable=False),
        sa.Column(
            "trigger_report",
            sa.Text(),
            nullable=True,
            comment="Path to the review/QV report that triggered this fix cycle",
        ),
        sa.Column(
            "fix_prompt", sa.Text(), nullable=True, comment="Path to the generated fix prompt"
        ),
        sa.Column("fix_report", sa.Text(), nullable=True, comment="Path to the fix agent report"),
        sa.Column("status", fix_status, nullable=False, server_default=sa.text("'pending'")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["step_id"], ["workflow_steps.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("step_id", "cycle_number"),
        comment="Fix cycle attempts triggered by code review or QV failures. Append-only.",
    )
    op.create_index("idx_fix_cycles_step", "fix_cycles", ["step_id"])

    # --- batches ---
    op.create_table(
        "batches",
        sa.Column("project_id", sa.Text(), nullable=False),
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("status", batch_status, nullable=False, server_default=sa.text("'planning'")),
        sa.Column(
            "max_parallel",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("4"),
            comment="Maximum number of items executing simultaneously",
        ),
        sa.Column("cli_tool", sa.Text(), nullable=False, server_default=sa.text("'opencode'")),
        sa.Column(
            "auto_publish",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="Whether to auto-push to origin after all items merged",
        ),
        sa.Column(
            "plan_path",
            sa.Text(),
            nullable=True,
            comment="Path to the batch execution plan document",
        ),
        sa.Column("diagram_path", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("project_id", "id"),
        comment="Groups of work items scheduled for parallel execution",
    )
    op.create_index("idx_batches_status", "batches", ["project_id", "status"])

    # --- batch_items ---
    op.create_table(
        "batch_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Text(), nullable=False),
        sa.Column("batch_id", sa.Text(), nullable=False),
        sa.Column("work_item_id", sa.Text(), nullable=False),
        sa.Column(
            "execution_group",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
            comment="Parallel execution group (0-based). Items in the same group run concurrently.",
        ),
        sa.Column("status", batch_item_status, nullable=False, server_default=sa.text("'pending'")),
        sa.Column("pid", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("merged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("stall_count", sa.Integer(), nullable=True, server_default=sa.text("0")),
        sa.Column("last_progress", sa.Text(), nullable=True),
        sa.Column(
            "worktree_info",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default=sa.text("'{}'"),
            comment="Worktree metadata: path, branch, created_at",
        ),
        sa.Column(
            "merge_info",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default=sa.text("'{}'"),
            comment="Merge metadata: commit_hash, conflict_files, merged_by",
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "batch_id"],
            ["batches.project_id", "batches.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "work_item_id"],
            ["work_items.project_id", "work_items.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "batch_id", "work_item_id"),
        comment="Work items assigned to a batch with execution group and status tracking",
    )
    op.create_index("idx_batch_items_status", "batch_items", ["project_id", "batch_id", "status"])
    op.create_index("idx_batch_items_work_item", "batch_items", ["project_id", "work_item_id"])

    # --- migration_locks ---
    op.create_table(
        "migration_locks",
        sa.Column("project_id", sa.Text(), nullable=False),
        sa.Column(
            "current_holder",
            sa.Text(),
            nullable=True,
            comment="Work item ID holding the lock (NULL = unlocked)",
        ),
        sa.Column("branch", sa.Text(), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "head_revision",
            sa.Text(),
            nullable=True,
            comment="Alembic head revision at lock time (for conflict detection)",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("project_id"),
        comment="Exclusive lock per project for Alembic migration creation",
    )

    # --- daemon_events ---
    op.create_table(
        "daemon_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "project_id",
            sa.Text(),
            nullable=True,
            comment="NULL for system-level events (daemon start/stop, quota warnings)",
        ),
        sa.Column(
            "event_type",
            sa.Text(),
            nullable=False,
            comment="Event category (see event type catalog)",
        ),
        sa.Column(
            "entity_id",
            sa.Text(),
            nullable=True,
            comment="Related entity: work item ID, batch ID, or step ID",
        ),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id"),
        comment="Audit trail of orchestration events. Append-only. Powers notifications and analytics.",
    )
    op.create_index("idx_daemon_events_recent", "daemon_events", [sa.text("created_at DESC")])
    op.create_index(
        "idx_daemon_events_project",
        "daemon_events",
        ["project_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "idx_daemon_events_type",
        "daemon_events",
        ["event_type", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    # Drop indexes and tables in reverse dependency order
    op.drop_index("idx_daemon_events_type", table_name="daemon_events")
    op.drop_index("idx_daemon_events_project", table_name="daemon_events")
    op.drop_index("idx_daemon_events_recent", table_name="daemon_events")
    op.drop_table("daemon_events")

    op.drop_table("migration_locks")

    op.drop_index("idx_batch_items_work_item", table_name="batch_items")
    op.drop_index("idx_batch_items_status", table_name="batch_items")
    op.drop_table("batch_items")

    op.drop_index("idx_batches_status", table_name="batches")
    op.drop_table("batches")

    op.drop_index("idx_fix_cycles_step", table_name="fix_cycles")
    op.drop_table("fix_cycles")

    op.drop_index("idx_step_runs_status", table_name="step_runs")
    op.drop_index("idx_step_runs_step", table_name="step_runs")
    op.drop_table("step_runs")

    op.drop_index("idx_workflow_steps_status", table_name="workflow_steps")
    op.drop_index("idx_workflow_steps_item", table_name="workflow_steps")
    op.drop_table("workflow_steps")

    # Drop FTS trigger and function
    op.execute("DROP TRIGGER IF EXISTS trg_work_items_fts ON work_items;")
    op.execute("DROP FUNCTION IF EXISTS work_items_fts_update();")

    op.drop_index("idx_work_items_created", table_name="work_items")
    op.drop_index("idx_work_items_fts", table_name="work_items")
    op.drop_index("idx_work_items_type", table_name="work_items")
    op.drop_index("idx_work_items_phase", table_name="work_items")
    op.drop_index("idx_work_items_status", table_name="work_items")
    op.drop_table("work_items")

    op.drop_table("id_sequences")
    op.drop_table("projects")

    # Drop ENUM types
    for enum_name in [
        "batch_item_status",
        "batch_status",
        "fix_status",
        "fix_trigger",
        "run_status",
        "step_status",
        "step_type",
        "work_item_phase",
        "work_item_status",
        "work_item_type",
    ]:
        op.execute(f"DROP TYPE IF EXISTS {enum_name};")
