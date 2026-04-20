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
    Research = "Research"


class WorkItemStatus(enum.Enum):
    draft = "draft"
    approved = "approved"
    in_progress = "in_progress"
    completed = "completed"
    failed = "failed"
    paused = "paused"
    cancelled = "cancelled"


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
    browser_verification = "browser_verification"


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


class TestRunStatus(enum.Enum):
    pending = "pending"
    running = "running"
    passed = "passed"
    failed = "failed"
    cancelled = "cancelled"
    error = "error"


class DocType(enum.Enum):
    module = "module"
    api = "api"
    architecture = "architecture"
    release_notes = "release_notes"
    error_catalog = "error_catalog"
    webhook_ref = "webhook_ref"
    user_guide = "user_guide"
    product_overview = "product_overview"
    feature_catalog = "feature_catalog"
    research = "research"


class DocTier(enum.Enum):
    fully_automated = "fully_automated"
    semi_automated = "semi_automated"
    human_authored = "human_authored"


class EditorialCategory(enum.Enum):
    technical = "technical"
    functional = "functional"
    guide = "guide"
    compliance = "compliance"
    marketing = "marketing"
    release = "release"


class DocStatus(enum.Enum):
    planned = "planned"
    draft = "draft"
    published = "published"
    archived = "archived"


class JobStatus(enum.Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


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
_test_run_status_col = SAEnum(TestRunStatus, name="test_run_status", create_type=True)

_doc_type_col = SAEnum(DocType, name="doc_type", create_type=False)
_doc_tier_col = SAEnum(DocTier, name="doc_tier", create_type=False)
_editorial_category_col = SAEnum(EditorialCategory, name="editorial_category", create_type=False)
_doc_status_col = SAEnum(DocStatus, name="doc_status", create_type=False)
_job_status_col = SAEnum(JobStatus, name="job_status", create_type=False)


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
    fix_summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment=(
            "Fix agent's 1-3 bullet summary of what changed and why; "
            "NULL for pre-F-00056 cycles or when the agent did not emit a summary"
        ),
    )
    status: Mapped[FixStatus] = mapped_column(
        _fix_status_col, nullable=False, server_default=text("'pending'")
    )
    fix_metadata: Mapped[Any] = mapped_column(
        JSONB,
        nullable=True,
        server_default=text("'{}'"),
        comment="Runtime metadata: pid, timeout_secs, log_file, worktree_path",
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
    archived_at: Mapped[datetime | None] = mapped_column(
        _TIMESTAMPTZ, nullable=True, comment="Timestamp when the batch was archived"
    )

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


class TestRun(Base):
    """Test execution runs launched from the dashboard. Append-only."""

    __tablename__ = "test_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(
        Text, nullable=False, comment="Project that owns this test run"
    )
    category: Mapped[str] = mapped_column(
        Text, nullable=False, comment="Test category key (e.g. 'unit', 'integration', 'e2e')"
    )
    status: Mapped[TestRunStatus] = mapped_column(
        _test_run_status_col, nullable=False, server_default=text("'pending'")
    )
    command: Mapped[str] = mapped_column(Text, nullable=False, comment="Shell command executed")
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(_TIMESTAMPTZ, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(_TIMESTAMPTZ, nullable=True)
    duration_secs: Mapped[float | None] = mapped_column(Float, nullable=True)
    pid: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="OS process ID (for kill support)"
    )
    log_path: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Absolute path to captured stdout/stderr log"
    )
    allure_results_dir: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Path to allure-results directory for this run"
    )
    allure_report_dir: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Path to generated allure-report directory"
    )
    summary: Mapped[Any] = mapped_column(
        JSONB, nullable=True, comment="Parsed Allure widgets/summary.json content"
    )
    triggered_by: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'user'"),
        comment="Who triggered: user, scheduled",
    )
    run_type: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'test'"),
        comment="Discriminator: test or quality",
    )
    created_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ, nullable=False, server_default=func.now()
    )

    __table_args__ = (
        ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        Index("idx_test_runs_project_created", "project_id", "created_at"),
        Index("idx_test_runs_project_status", "project_id", "status"),
        Index("idx_test_runs_run_type", "project_id", "run_type", "created_at"),
        {"comment": "Test execution runs launched from the dashboard. Append-only."},
    )


class ProjectDoc(Base):
    """Project-level documentation catalog entries."""

    __tablename__ = "project_docs"

    id: Mapped[str] = mapped_column(
        Text,
        primary_key=True,
        comment="Composite PK: '{project_id}:{doc_id}'",
    )
    project_id: Mapped[str] = mapped_column(Text, nullable=False)
    doc_id: Mapped[str] = mapped_column(
        Text, nullable=False, comment="User-defined doc identifier within project"
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    doc_type: Mapped[DocType] = mapped_column(_doc_type_col, nullable=False)
    tier: Mapped[DocTier] = mapped_column(_doc_tier_col, nullable=False)
    editorial_category: Mapped[EditorialCategory] = mapped_column(
        _editorial_category_col, nullable=False
    )
    status: Mapped[DocStatus] = mapped_column(
        _doc_status_col, nullable=False, server_default=text("'planned'")
    )
    audience: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'"),
        comment="JSONB array of audience strings",
    )
    source_paths: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'"),
        comment="JSONB array of source file paths",
    )
    content: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Tier 1: full markdown content"
    )
    content_search: Mapped[str | None] = mapped_column(
        TSVECTOR,
        nullable=True,
        comment="PostgreSQL tsvector for full-text search",
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    generated_at: Mapped[datetime | None] = mapped_column(_TIMESTAMPTZ, nullable=True)
    generated_by: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Generator identifier (e.g., 'skill:iw-doc-generator')"
    )
    html_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    pdf_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    broken_links: Mapped[list[dict[str, str]] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="List of {url, type, status} objects from link validation",
    )
    created_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ, nullable=False, server_default=func.now()
    )

    __table_args__ = (
        ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        UniqueConstraint("project_id", "doc_id", name="uq_project_docs_project_doc"),
        Index("idx_project_docs_project_id", "project_id"),
        Index("idx_project_docs_fts", "content_search", postgresql_using="gin"),
        {"comment": "Project-level documentation catalog entries"},
    )


class ProjectDocVersion(Base):
    """Immutable version snapshots of ProjectDoc content."""

    __tablename__ = "project_doc_versions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    doc_id: Mapped[str] = mapped_column(Text, nullable=False, comment="FK to project_docs.id")
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="Markdown content snapshot")
    generated_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    trigger_reason: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="e.g., 'manual', 'batch-merge:B-00042', 'cli:iw doc-update'"
    )
    created_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ, nullable=False, server_default=func.now()
    )

    __table_args__ = (
        ForeignKeyConstraint(["doc_id"], ["project_docs.id"], ondelete="CASCADE"),
        Index("idx_project_doc_versions_doc_id", "doc_id"),
        {"comment": "Immutable version snapshots of ProjectDoc content"},
    )


class DocGenerationJob(Base):
    """Async AI documentation generation job tracking."""

    __tablename__ = "doc_generation_jobs"

    id: Mapped[str] = mapped_column(
        Text,
        primary_key=True,
        comment="UUID primary key",
    )
    project_id: Mapped[str] = mapped_column(Text, nullable=False)
    doc_id: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="FK to project_docs.id; job survives doc deletion"
    )
    status: Mapped[JobStatus] = mapped_column(
        _job_status_col, nullable=False, server_default=text("'queued'")
    )
    requested_at: Mapped[datetime | None] = mapped_column(_TIMESTAMPTZ, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(_TIMESTAMPTZ, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(_TIMESTAMPTZ, nullable=True)
    agent_output: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Raw agent stdout/result"
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    agent_pid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    skill_used: Mapped[str | None] = mapped_column(Text, nullable=True)
    trigger_reason: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Why the job was created (e.g., 'batch-merge:B-00042:F-00013')"
    )
    lint_warnings: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="List of lint warning objects {rule, message, section}",
    )
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section_guides_snapshot: Mapped[dict[str, str] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Section guides snapshotted at job creation: {section_name: guide_md, ...}.",
    )
    guide_snapshot: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Guide content snapshotted at job creation time for audit purposes.",
    )
    created_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ, nullable=False, server_default=func.now()
    )

    __table_args__ = (
        ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["doc_id"], ["project_docs.id"], ondelete="SET NULL"),
        Index("idx_doc_generation_jobs_project_id", "project_id"),
        Index("idx_doc_generation_jobs_doc_id", "doc_id"),
        Index("idx_doc_generation_jobs_status", "status"),
        {"comment": "Async AI documentation generation job tracking"},
    )


class DocTypeGuide(Base):
    """Editable editorial guideline per DocType (type-level default)."""

    __tablename__ = "doc_type_guides"

    doc_type: Mapped[str] = mapped_column(
        Text,
        primary_key=True,
        comment="DocType value (e.g. 'api', 'module')",
    )
    guide_md: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = {"comment": "Editable editorial guideline per DocType"}


class DocInstanceGuide(Base):
    """Instance-level guide override for a specific ProjectDoc."""

    __tablename__ = "doc_instance_guides"

    doc_id: Mapped[str] = mapped_column(
        Text,
        primary_key=True,
        comment="FK to project_docs.id",
    )
    guide_md: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        ForeignKeyConstraint(["doc_id"], ["project_docs.id"], ondelete="CASCADE"),
        {"comment": "Instance-level guide override for a specific ProjectDoc"},
    )


class DocSectionGuide(Base):
    """Per-section editorial guidelines, keyed by (doc_id, section_name)."""

    __tablename__ = "doc_section_guides"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    doc_id: Mapped[str] = mapped_column(
        Text, nullable=False, comment="FK to project_docs.id (composite: project_id:doc_id)."
    )
    section_name: Mapped[str] = mapped_column(
        Text, nullable=False, comment="H2 heading text, or 'Document' if no H2 headings exist."
    )
    guide_md: Mapped[str] = mapped_column(
        Text, nullable=False, comment="Markdown editorial guidelines for this specific section."
    )
    updated_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="Timestamp of last guide edit.",
    )

    __table_args__ = (
        ForeignKeyConstraint(["doc_id"], ["project_docs.id"], ondelete="CASCADE"),
        UniqueConstraint("doc_id", "section_name", name="uq_doc_section_guides_doc_section"),
        Index("idx_doc_section_guides_doc_id", "doc_id"),
        {"comment": "Per-section editorial guidelines keyed by (doc_id, section_name)."},
    )


class CodeIndexJob(Base):
    """Tracks a code indexing job for a project."""

    __tablename__ = "code_index_jobs"

    id: Mapped[str] = mapped_column(
        Text,
        primary_key=True,
        server_default=text("gen_random_uuid()::text"),
        comment="UUID as text, generated by PostgreSQL",
    )
    project_id: Mapped[str] = mapped_column(Text, nullable=False, comment="FK to projects(id)")
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'queued'"),
        comment="queued|running|completed|failed|cancelled",
    )
    provider: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'local'"),
        comment="Index provider: local (only value in v1)",
    )
    llm_model: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="LLM model name; None = use tier default"
    )
    embed_model: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Embedding model name; None = use tier default"
    )
    index_tier: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="fast|balanced|quality"
    )
    files_discovered: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0"), comment="Total files found"
    )
    files_indexed: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0"), comment="Files successfully indexed"
    )
    chunks_created: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0"), comment="Total chunks produced"
    )
    languages_detected: Mapped[Any] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'"),
        comment="List of detected language names",
    )
    errors: Mapped[Any] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'"), comment="List of error messages"
    )
    doc_id: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="FK to project_docs(id); nullable, SET NULL on delete"
    )
    triggered_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ,
        nullable=False,
        server_default=func.now(),
        comment="When the job was triggered",
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        _TIMESTAMPTZ, nullable=True, comment="When the job finished (success or failure)"
    )
    created_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ, nullable=False, server_default=func.now()
    )

    __table_args__ = (
        ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["doc_id"], ["project_docs.id"], ondelete="SET NULL"),
        Index("idx_code_index_jobs_project_id", "project_id"),
        Index("idx_code_index_jobs_status", "status"),
        {"comment": "Tracks code indexing jobs for a project"},
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

PROJECT_DOCS_FTS_FUNCTION_SQL = """\
CREATE OR REPLACE FUNCTION update_project_docs_fts() RETURNS trigger AS $$
BEGIN
    NEW.content_search := to_tsvector(
        'english',
        coalesce(NEW.title, '') || ' ' || coalesce(NEW.content, '')
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

PROJECT_DOCS_FTS_TRIGGER_SQL = """\
CREATE TRIGGER trg_project_docs_fts
    BEFORE INSERT OR UPDATE OF title, content
    ON project_docs
    FOR EACH ROW
    EXECUTE FUNCTION update_project_docs_fts();
"""

DROP_PROJECT_DOCS_FTS_TRIGGER_SQL = "DROP TRIGGER IF EXISTS trg_project_docs_fts ON project_docs;"
DROP_PROJECT_DOCS_FTS_FUNCTION_SQL = "DROP FUNCTION IF EXISTS update_project_docs_fts();"
