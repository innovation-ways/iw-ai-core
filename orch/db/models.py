"""SQLAlchemy 2.0 ORM models for the IW AI Core platform.

All models use the Mapped[] declarative style (SQLAlchemy 2.0).
All timestamps are UTC with timezone (TIMESTAMPTZ).
ENUMs match the exact values defined in the Database Schema DDL.

NOTE: Do NOT add 'from __future__ import annotations' — SQLAlchemy 2.0
requires annotations to be resolved at import time for mapper configuration.
"""

import enum
from datetime import datetime
from typing import Any

from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# ---------------------------------------------------------------------------
# Declarative base
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Python Enums (mirror the PostgreSQL ENUM types exactly)
# ---------------------------------------------------------------------------


class WorkItemType(enum.Enum):
    Feature = "Feature"
    Issue = "Issue"
    ChangeRequest = "ChangeRequest"


class WorkItemStatus(enum.Enum):
    draft = "draft"
    approved = "approved"
    in_progress = "in_progress"
    completed = "completed"
    failed = "failed"
    paused = "paused"


class WorkItemPhase(enum.Enum):
    active = "active"
    work = "work"
    done = "done"


class StepType(enum.Enum):
    implementation = "implementation"
    code_review = "code_review"
    code_review_fix = "code_review_fix"
    code_review_final = "code_review_final"
    code_review_fix_final = "code_review_fix_final"
    quality_validation = "quality_validation"
    qv_fix = "qv_fix"
    browser_verification = "browser_verification"


class StepStatus(enum.Enum):
    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"
    failed = "failed"
    needs_fix = "needs_fix"
    skipped = "skipped"


class RunStatus(enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    timeout = "timeout"
    killed = "killed"
    stalled = "stalled"


class FixTrigger(enum.Enum):
    code_review = "code_review"
    code_review_final = "code_review_final"
    quality_validation = "quality_validation"


class FixStatus(enum.Enum):
    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"
    failed = "failed"
    escalated = "escalated"


class BatchStatus(enum.Enum):
    planning = "planning"
    approved = "approved"
    executing = "executing"
    paused = "paused"
    completed = "completed"
    completed_with_errors = "completed_with_errors"
    publishing = "publishing"
    published = "published"
    publish_failed = "publish_failed"
    blocked = "blocked"
    archived = "archived"
    cancelled = "cancelled"


class BatchItemStatus(enum.Enum):
    pending = "pending"
    setting_up = "setting_up"
    executing = "executing"
    completed = "completed"
    merging = "merging"
    merged = "merged"
    failed = "failed"
    stalled = "stalled"
    skipped = "skipped"


# ---------------------------------------------------------------------------
# Reusable column type shorthands
# ---------------------------------------------------------------------------

_TIMESTAMPTZ = DateTime(timezone=True)

_work_item_type_col = SAEnum(WorkItemType, name="work_item_type", create_type=True)
_work_item_status_col = SAEnum(WorkItemStatus, name="work_item_status", create_type=True)
_work_item_phase_col = SAEnum(WorkItemPhase, name="work_item_phase", create_type=True)
_step_type_col = SAEnum(StepType, name="step_type", create_type=True)
_step_status_col = SAEnum(StepStatus, name="step_status", create_type=True)
_run_status_col = SAEnum(RunStatus, name="run_status", create_type=True)
_fix_trigger_col = SAEnum(FixTrigger, name="fix_trigger", create_type=True)
_fix_status_col = SAEnum(FixStatus, name="fix_status", create_type=True)
_batch_status_col = SAEnum(BatchStatus, name="batch_status", create_type=True)
_batch_item_status_col = SAEnum(BatchItemStatus, name="batch_item_status", create_type=True)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class Project(Base):
    """Registry of software projects managed by IW AI Core."""

    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(
        Text,
        primary_key=True,
        comment="Unique project identifier (e.g., 'innoforge')",
    )
    display_name: Mapped[str] = mapped_column(
        Text, nullable=False, comment="Human-readable project name"
    )
    repo_root: Mapped[str] = mapped_column(
        Text, nullable=False, comment="Absolute path to the main clone repo root"
    )
    dev_clone: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Absolute path to the development clone (optional)"
    )
    config: Mapped[Any] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'"),
        comment="Full .iw-orch.json content as JSONB",
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
        comment="Whether the daemon processes this project",
    )
    registered_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ, nullable=False, server_default=func.now()
    )

    __table_args__ = ({"comment": "Registry of software projects managed by IW AI Core"},)


class IdSequence(Base):
    """Global atomic sequential ID allocation per prefix."""

    __tablename__ = "id_sequences"

    prefix: Mapped[str] = mapped_column(
        Text,
        primary_key=True,
        comment="ID prefix: 'F' (Feature), 'I' (Issue), 'CR' (ChangeRequest), 'BATCH'",
    )
    next_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("1"),
        comment="Next number to allocate (incremented atomically via FOR UPDATE)",
    )

    __table_args__ = ({"comment": "Global atomic sequential ID allocation per prefix"},)


class WorkItem(Base):
    """Features, Incidents, and Change Requests across all projects."""

    __tablename__ = "work_items"

    project_id: Mapped[str] = mapped_column(Text, primary_key=True)
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    type: Mapped[WorkItemType] = mapped_column(_work_item_type_col, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[WorkItemStatus] = mapped_column(
        _work_item_status_col,
        nullable=False,
        server_default=text("'draft'"),
    )
    phase: Mapped[WorkItemPhase] = mapped_column(
        _work_item_phase_col,
        nullable=False,
        server_default=text("'active'"),
    )
    config: Mapped[Any] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'"),
        comment="Item-level config: fix_cycle_max, browser_verification, etc.",
    )
    depends_on: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        server_default=text("'{}'"),
        comment="Array of work item IDs this item depends on",
    )
    blocks: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        server_default=text("'{}'"),
        comment="Array of work item IDs this item blocks",
    )
    design_doc_path: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Relative path to design doc in project repo (active items)",
    )
    # Tier 1
    design_doc_content: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment=(
            "Full markdown of design doc "
            "(Tier 1 — stored on archive for instant dashboard rendering)"
        ),
    )
    design_doc_search: Mapped[str | None] = mapped_column(
        TSVECTOR,
        nullable=True,
        comment="PostgreSQL tsvector for full-text search across design docs",
    )
    summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="AI-generated 2-3 line summary for list views and search results",
    )
    # Tier 2
    archive_path: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Relative path to .tar.zst in archive directory (Tier 2)",
    )
    archive_size_bytes: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, comment="Compressed archive file size in bytes"
    )
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ, nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(_TIMESTAMPTZ, nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(
        _TIMESTAMPTZ,
        nullable=True,
        comment="When the item was archived (Tier 1 + Tier 2 stored, active files deleted)",
    )

    __table_args__ = (
        ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        Index("idx_work_items_status", "project_id", "status"),
        Index("idx_work_items_phase", "project_id", "phase"),
        Index("idx_work_items_type", "project_id", "type"),
        Index("idx_work_items_fts", "design_doc_search", postgresql_using="gin"),
        Index("idx_work_items_created", "project_id", "created_at"),
        {"comment": "Features, Incidents, and Change Requests across all projects"},
    )


class WorkflowStep(Base):
    """Workflow step definitions for each work item."""

    __tablename__ = "workflow_steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(Text, nullable=False)
    work_item_id: Mapped[str] = mapped_column(Text, nullable=False)
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    step_id: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Step identifier within the item (e.g., 'S01', 'S02')",
    )
    agent_label: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Agent label for file naming (e.g., 'Backend', 'CodeReview_Backend')",
    )
    opencode_agent: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="OpenCode/Claude agent to invoke (e.g., 'backend-impl', 'code-review-impl')",
    )
    step_type: Mapped[StepType] = mapped_column(_step_type_col, nullable=False)
    step_label: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Short human-readable label for the step (e.g., 'ruff lint', 'unit tests')",
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[StepStatus] = mapped_column(
        _step_status_col, nullable=False, server_default=text("'pending'")
    )
    prompt_file: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Relative path to the prompt file in the project repo",
    )
    report_file: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Relative path to the report file (latest run)",
    )
    # Tier 1
    report_content: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment=(
            "Full report markdown (Tier 1 — stored on archive for instant dashboard rendering)"
        ),
    )
    # Timestamps
    started_at: Mapped[datetime | None] = mapped_column(_TIMESTAMPTZ, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(_TIMESTAMPTZ, nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "work_item_id"],
            ["work_items.project_id", "work_items.id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("project_id", "work_item_id", "step_number"),
        Index("idx_workflow_steps_item", "project_id", "work_item_id"),
        Index("idx_workflow_steps_status", "project_id", "work_item_id", "status"),
        {"comment": "Workflow step definitions for each work item"},
    )


class StepRun(Base):
    """Execution attempts for workflow steps. Append-only — each retry creates a new row."""

    __tablename__ = "step_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    step_id: Mapped[int] = mapped_column(Integer, nullable=False)
    run_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[RunStatus] = mapped_column(
        _run_status_col, nullable=False, server_default=text("'pending'")
    )
    # Process control
    pid: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="OS process ID of the LLM session (for kill -0 and SIGTERM)",
    )
    pid_alive: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
        server_default=text("false"),
        comment="Whether the process is currently alive (set by daemon every poll cycle)",
    )
    command: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Exact shell command used to launch (enables one-click restart)",
    )
    worktree_path: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Full path to the git worktree where the agent runs",
    )
    cli_tool: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="LLM CLI tool used: 'opencode' or 'claude'",
    )
    last_heartbeat: Mapped[datetime | None] = mapped_column(
        _TIMESTAMPTZ,
        nullable=True,
        comment="Last time daemon confirmed PID was alive (for stall detection)",
    )
    timeout_secs: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Dynamic timeout for this step type (not a global constant)",
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Human-readable reason for failure, timeout, or kill",
    )
    # Output
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    log_file: Mapped[str | None] = mapped_column(Text, nullable=True)
    log_content: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Captured log content (ANSI-stripped, truncated) for fast DB access",
    )
    report_file: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Timestamps
    started_at: Mapped[datetime | None] = mapped_column(_TIMESTAMPTZ, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(_TIMESTAMPTZ, nullable=True)
    duration_secs: Mapped[float | None] = mapped_column(Float, nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(["step_id"], ["workflow_steps.id"], ondelete="CASCADE"),
        UniqueConstraint("step_id", "run_number"),
        Index("idx_step_runs_step", "step_id"),
        Index(
            "idx_step_runs_status",
            "status",
            postgresql_where=text("status IN ('pending', 'running', 'stalled')"),
        ),
        {
            "comment": (
                "Execution attempts for workflow steps. Append-only — each retry creates a new row."
            )
        },
    )


class FixCycle(Base):
    """Fix cycle attempts triggered by code review or QV failures. Append-only."""

    __tablename__ = "fix_cycles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    step_id: Mapped[int] = mapped_column(Integer, nullable=False)
    cycle_number: Mapped[int] = mapped_column(Integer, nullable=False)
    trigger_type: Mapped[FixTrigger] = mapped_column(_fix_trigger_col, nullable=False)
    trigger_report: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Path to the review/QV report that triggered this fix cycle",
    )
    fix_prompt: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Path to the generated fix prompt"
    )
    fix_report: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Path to the fix agent report"
    )
    status: Mapped[FixStatus] = mapped_column(
        _fix_status_col, nullable=False, server_default=text("'pending'")
    )
    started_at: Mapped[datetime | None] = mapped_column(_TIMESTAMPTZ, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(_TIMESTAMPTZ, nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(["step_id"], ["workflow_steps.id"], ondelete="CASCADE"),
        UniqueConstraint("step_id", "cycle_number"),
        Index("idx_fix_cycles_step", "step_id"),
        {"comment": "Fix cycle attempts triggered by code review or QV failures. Append-only."},
    )


class Batch(Base):
    """Groups of work items scheduled for parallel execution."""

    __tablename__ = "batches"

    project_id: Mapped[str] = mapped_column(Text, primary_key=True)
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    status: Mapped[BatchStatus] = mapped_column(
        _batch_status_col, nullable=False, server_default=text("'planning'")
    )
    max_parallel: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("4"),
        comment="Maximum number of items executing simultaneously",
    )
    cli_tool: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'opencode'"))
    auto_publish: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        comment="Whether to auto-push to origin after all items merged",
    )
    plan_path: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Path to the batch execution plan document (legacy)"
    )
    diagram_path: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Path to the diagram file (legacy)"
    )
    execution_plan_md: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Markdown execution plan with dependency analysis and warnings",
    )
    execution_plan_drawio: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Draw.io XML diagram of the execution plan",
    )
    execution_plan_png: Mapped[bytes | None] = mapped_column(
        LargeBinary,
        nullable=True,
        comment="PNG image of the execution plan diagram",
    )
    created_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ, nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(_TIMESTAMPTZ, nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        Index("idx_batches_status", "project_id", "status"),
        {"comment": "Groups of work items scheduled for parallel execution"},
    )


class BatchItem(Base):
    """Work items assigned to a batch with execution group and status tracking."""

    __tablename__ = "batch_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(Text, nullable=False)
    batch_id: Mapped[str] = mapped_column(Text, nullable=False)
    work_item_id: Mapped[str] = mapped_column(Text, nullable=False)
    execution_group: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
        comment="Parallel execution group (0-based). Items in the same group run concurrently.",
    )
    status: Mapped[BatchItemStatus] = mapped_column(
        _batch_item_status_col, nullable=False, server_default=text("'pending'")
    )
    pid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(_TIMESTAMPTZ, nullable=True)
    merged_at: Mapped[datetime | None] = mapped_column(_TIMESTAMPTZ, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    stall_count: Mapped[int | None] = mapped_column(
        Integer, nullable=True, server_default=text("0")
    )
    last_progress: Mapped[str | None] = mapped_column(Text, nullable=True)
    worktree_info: Mapped[Any] = mapped_column(
        JSONB,
        nullable=True,
        server_default=text("'{}'"),
        comment="Worktree metadata: path, branch, created_at",
    )
    merge_info: Mapped[Any] = mapped_column(
        JSONB,
        nullable=True,
        server_default=text("'{}'"),
        comment="Merge metadata: commit_hash, conflict_files, merged_by",
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "batch_id"],
            ["batches.project_id", "batches.id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["project_id", "work_item_id"],
            ["work_items.project_id", "work_items.id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("project_id", "batch_id", "work_item_id"),
        Index("idx_batch_items_status", "project_id", "batch_id", "status"),
        Index("idx_batch_items_work_item", "project_id", "work_item_id"),
        {"comment": "Work items assigned to a batch with execution group and status tracking"},
    )


class MigrationLock(Base):
    """Exclusive lock per project for Alembic migration creation."""

    __tablename__ = "migration_locks"

    project_id: Mapped[str] = mapped_column(Text, primary_key=True)
    current_holder: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Work item ID holding the lock (NULL = unlocked)",
    )
    branch: Mapped[str | None] = mapped_column(Text, nullable=True)
    locked_at: Mapped[datetime | None] = mapped_column(_TIMESTAMPTZ, nullable=True)
    head_revision: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Alembic head revision at lock time (for conflict detection)",
    )

    __table_args__ = (
        ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        {"comment": "Exclusive lock per project for Alembic migration creation"},
    )


class DaemonEvent(Base):
    """Audit trail of orchestration events. Append-only. Powers notifications and analytics."""

    __tablename__ = "daemon_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="NULL for system-level events (daemon start/stop, quota warnings)",
    )
    event_type: Mapped[str] = mapped_column(
        Text, nullable=False, comment="Event category (see event type catalog)"
    )
    entity_id: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Related entity: work item ID, batch ID, or step ID",
    )
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_metadata: Mapped[Any] = mapped_column(
        "metadata", JSONB, nullable=True, server_default=text("'{}'")
    )
    created_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ, nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("idx_daemon_events_recent", "created_at"),
        Index("idx_daemon_events_project", "project_id", "created_at"),
        Index("idx_daemon_events_type", "event_type", "created_at"),
        {
            "comment": (
                "Audit trail of orchestration events. "
                "Append-only. Powers notifications and analytics."
            )
        },
    )


# ---------------------------------------------------------------------------
# FTS trigger SQL — used by Alembic migration and integration test fixtures
# ---------------------------------------------------------------------------

FTS_FUNCTION_SQL = """\
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
"""

FTS_TRIGGER_SQL = """\
CREATE TRIGGER trg_work_items_fts
    BEFORE INSERT OR UPDATE OF title, design_doc_content
    ON work_items
    FOR EACH ROW
    EXECUTE FUNCTION work_items_fts_update();
"""

DROP_FTS_TRIGGER_SQL = "DROP TRIGGER IF EXISTS trg_work_items_fts ON work_items;"
DROP_FTS_FUNCTION_SQL = "DROP FUNCTION IF EXISTS work_items_fts_update();"
