"""SQLAlchemy 2.0 ORM models for the IW AI Core platform.

All models use the Mapped[] declarative style (SQLAlchemy 2.0).
All timestamps are UTC with timezone (TIMESTAMPTZ).
ENUMs match the exact values defined in the Database Schema DDL.

NOTE: Do NOT add 'from __future__ import annotations' — SQLAlchemy 2.0
requires annotations to be resolved at import time for mapper configuration.
"""

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    CheckConstraint,
    Connection,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
    PrimaryKeyConstraint,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    event,
    func,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, Mapper, mapped_column, relationship

# ---------------------------------------------------------------------------
# Declarative base
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Global catalogue: agent runtime options (no project_id — global singleton)
# ---------------------------------------------------------------------------


class AgentRuntimeOption(Base):
    """Catalogue of curated (cli_tool, model) pairs the daemon can launch.

    A partial unique index on ``is_default = true`` enforces at most one default row.
    A CHECK constraint prevents disabling the default row.
    """

    __tablename__ = "agent_runtime_options"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cli_tool: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    cli_label: Mapped[str] = mapped_column(Text, nullable=False)
    model_label: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    __table_args__ = (
        UniqueConstraint(
            "cli_tool",
            "model",
            name="uq_agent_runtime_options_cli_model",
        ),
        Index(
            "uq_agent_runtime_options_one_default",
            "is_default",
            unique=True,
            postgresql_where=text("is_default = true"),
        ),
        CheckConstraint(
            "NOT (is_default = true AND enabled = false)",
            name="ck_agent_runtime_options_default_must_be_enabled",
        ),
        {"comment": "Catalogue of curated (cli_tool, model) pairs the daemon can launch."},
    )


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


class EvidencePhase(enum.Enum):
    pre = "pre"
    post = "post"


class StepType(enum.Enum):
    implementation = "implementation"
    code_review = "code_review"
    code_review_fix = "code_review_fix"
    code_review_final = "code_review_final"
    code_review_fix_final = "code_review_fix_final"
    quality_validation = "quality_validation"
    qv_fix = "qv_fix"
    browser_verification = "browser_verification"
    self_assess = "self_assess"


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
    awaiting_merge_approval = "awaiting_merge_approval"
    merging = "merging"
    merged = "merged"
    failed = "failed"
    stalled = "stalled"
    skipped = "skipped"
    merge_failed = "merge_failed"
    migration_invalid = "migration_invalid"
    migration_rolled_back = "migration_rolled_back"
    migration_rebase_failed = "migration_rebase_failed"
    setup_failed = "setup_failed"


TERMINAL_BATCH_ITEM_STATUSES: frozenset[BatchItemStatus] = frozenset(
    {
        BatchItemStatus.merged,
        BatchItemStatus.failed,
        BatchItemStatus.stalled,
        BatchItemStatus.skipped,
        BatchItemStatus.merge_failed,
        BatchItemStatus.migration_invalid,
        BatchItemStatus.migration_rolled_back,
        BatchItemStatus.migration_rebase_failed,
        BatchItemStatus.setup_failed,
    }
)


def is_terminal_batch_item_status(status: BatchItemStatus) -> bool:
    return status in TERMINAL_BATCH_ITEM_STATUSES


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
    code_components = "code_components"
    release_notes = "release_notes"
    error_catalog = "error_catalog"
    webhook_ref = "webhook_ref"
    user_guide = "user_guide"
    product_overview = "product_overview"
    feature_catalog = "feature_catalog"
    research = "research"
    diagram = "diagram"


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
# OSS Compliance Enums
# ---------------------------------------------------------------------------


class OssScanStatus(enum.Enum):
    pending = "pending"
    running = "running"
    complete = "complete"
    error = "error"


class OssScanMode(enum.Enum):
    scan = "scan"


class OssPillColor(enum.Enum):
    green = "green"
    yellow = "yellow"
    red = "red"
    gray = "gray"


class OssFindingSeverity(enum.Enum):
    MUST = "MUST"
    SHOULD = "SHOULD"
    MAY = "MAY"
    INFO = "INFO"


class OssFindingStatus(enum.Enum):
    pass_status = "pass"  # noqa: S105  (enum member value, not a password)
    fail = "fail"
    skip = "skip"
    human_required = "human_required"


class OssToolRunStatus(enum.Enum):
    ok = "ok"
    failed = "failed"
    missing = "missing"
    skipped = "skipped"


class ProjectOssJobKind(enum.Enum):
    scan = "scan"
    install = "install"
    fix = "fix"


class ProjectOssJobStatus(enum.Enum):
    queued = "queued"
    running = "running"
    complete = "complete"
    error = "error"
    cancelled = "cancelled"


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

_oss_scan_status_col = SAEnum(OssScanStatus, name="ossscan_status", create_type=True)
_oss_scan_mode_col = SAEnum(OssScanMode, name="ossscan_mode", create_type=True)
_oss_pill_color_col = SAEnum(OssPillColor, name="osspill_color", create_type=True)
_oss_finding_severity_col = SAEnum(OssFindingSeverity, name="ossfinding_severity", create_type=True)
_oss_finding_status_col = SAEnum(OssFindingStatus, name="ossfinding_status", create_type=True)
_oss_tool_run_status_col = SAEnum(OssToolRunStatus, name="osstoolrun_status", create_type=True)
_project_oss_job_kind_col = SAEnum(ProjectOssJobKind, name="project_oss_job_kind", create_type=True)
_project_oss_job_status_col = SAEnum(
    ProjectOssJobStatus, name="project_oss_job_status", create_type=True
)


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
    oss_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        comment="Whether OSS compliance scanning is enabled for this project",
    )
    registered_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ, nullable=False, server_default=func.now()
    )

    oss_scans: Mapped[list["OssScan"]] = relationship(
        "OssScan", back_populates="project", cascade="all, delete-orphan"
    )
    oss_jobs: Mapped[list["ProjectOssJob"]] = relationship(
        "ProjectOssJob", back_populates="project", cascade="all, delete-orphan"
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


class IdAllocation(Base):
    """Audit log of keyed ID allocations for idempotent iw next-id (CR-00053)."""

    __tablename__ = "id_allocations"

    prefix: Mapped[str] = mapped_column(
        Text,
        primary_key=True,
        comment="ID prefix: 'F' (Feature), 'I' (Issue), 'CR' (ChangeRequest), 'BATCH'",
    )
    number: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        comment="Allocated sequence number",
    )
    idempotency_key: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Client-supplied idempotency key (NULL when no key provided)",
    )
    project_id: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Project that requested this allocation",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
        comment="UTC timestamp of allocation",
    )

    __table_args__ = (
        Index(
            "idx_id_allocations_key",
            "prefix",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
        {"comment": "Audit log of keyed ID allocations for idempotent iw next-id (CR-00053)"},
    )


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
    impacted_paths: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'"),
        comment=(
            "Globs declaring files this work item is expected to touch. "
            "Source of truth for the cross-batch launch-time conflict gate "
            "(F-00076) and the workflow-manifest.json:scope.allowed_paths "
            "merge gate. Populated by orch/cli/item_commands.py:register() "
            "from the design doc's 'Impacted Paths' section, with a regex "
            "fallback over design_doc_content when the section is absent."
        ),
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
    functional_doc_path: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Relative path to functional design doc in project repo (active items)",
    )
    functional_doc_content: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment=(
            "Full markdown of functional design doc "
            "(Tier 1 — stored on archive for instant dashboard rendering)"
        ),
    )
    functional_doc_search: Mapped[str | None] = mapped_column(
        TSVECTOR,
        nullable=True,
        comment="PostgreSQL tsvector for full-text search across functional design docs",
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
    # Files view — aggregate diff (captured at squash merge)
    diff_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Raw unified diff of the squash commit captured at merge time",
    )
    diff_summary: Mapped[Any | None] = mapped_column(
        JSONB,
        nullable=True,
        comment=(
            "Parsed file metadata: list of objects with keys path, status "
            "(A/M/D/R), added, removed, is_generated, is_binary, old_path"
        ),
    )
    merge_commit_sha: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="SHA of the squash commit on main; enables lazy git diff for completed items",
    )
    # F-00081 — per-item agent+model override (NULL = inherit project/catalogue default)
    agent_runtime_option_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("agent_runtime_options.id", ondelete="RESTRICT"),
        nullable=True,
        comment="Override pair to use for this item; NULL = inherit. F-00081.",
    )

    __table_args__ = (
        ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        Index("idx_work_items_status", "project_id", "status"),
        Index("idx_work_items_phase", "project_id", "phase"),
        Index("idx_work_items_type", "project_id", "type"),
        Index("idx_work_items_fts", "design_doc_search", postgresql_using="gin"),
        Index(
            "idx_work_items_functional_doc_search",
            "functional_doc_search",
            postgresql_using="gin",
        ),
        Index("idx_work_items_created", "project_id", "created_at"),
        {"comment": "Features, Incidents, and Change Requests across all projects"},
    )


def _sanitize_text_with_nul(text: str | None) -> str | None:
    if text is None:
        return None
    return text.replace("\x00", "")


@event.listens_for(WorkItem, "before_insert")
def _work_item_sanitize_functional_doc_content(
    _mapper: Mapper[Any], _connection: Connection, target: WorkItem
) -> None:
    if hasattr(target, "functional_doc_content") and target.functional_doc_content:
        target.functional_doc_content = _sanitize_text_with_nul(target.functional_doc_content)


@event.listens_for(WorkItem, "before_update")
def _work_item_sanitize_functional_doc_content_on_update(
    _mapper: Mapper[Any], _connection: Connection, target: WorkItem
) -> None:
    if hasattr(target, "functional_doc_content") and target.functional_doc_content:
        target.functional_doc_content = _sanitize_text_with_nul(target.functional_doc_content)


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
    command: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment=(
            "Shell command for qv-gate steps (e.g., 'make lint'). NULL for "
            "non-gate steps and for items registered before CR-00023."
        ),
    )
    gate: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment=(
            "Gate name for qv-gate steps (e.g., 'lint', 'format', 'typecheck'). "
            "NULL for non-gate steps and for items registered before CR-00023."
        ),
    )
    timeout_secs: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment=(
            "Per-step timeout override in seconds. NULL = use project default. "
            "Sourced from the manifest's 'timeout' field at registration."
        ),
    )
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
    # F-00081 — per-step agent+model override (NULL = inherit item/project default)
    agent_runtime_option_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("agent_runtime_options.id", ondelete="RESTRICT"),
        nullable=True,
        comment="Override pair to use for this step; NULL = inherit. F-00081.",
    )

    baselines: Mapped[list["QvBaseline"]] = relationship(
        "QvBaseline", back_populates="step", cascade="all, delete-orphan"
    )

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
        comment="LLM CLI tool used: 'opencode', 'claude', or 'pi'",
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
    session_file: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment=(
            "Absolute path to the pi session .jsonl file for this run. "
            "Set by step_monitor on the first poll cycle after step launch. "
            "NULL for claude/opencode runs and pre-CR-00065 rows. (CR-00065)"
        ),
    )
    report_file: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Files view — per-step diff (captured at step-done)
    diff_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Raw unified diff captured at iw step-done from the worktree",
    )
    diff_summary: Mapped[Any | None] = mapped_column(
        JSONB,
        nullable=True,
        comment=(
            "Parsed file metadata for this step: list of objects with keys path, "
            "status (A/M/D/R), added, removed, is_generated, is_binary, old_path"
        ),
    )
    # Timestamps
    started_at: Mapped[datetime | None] = mapped_column(_TIMESTAMPTZ, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(_TIMESTAMPTZ, nullable=True)
    duration_secs: Mapped[float | None] = mapped_column(Float, nullable=True)
    warned_50pct_at: Mapped[datetime | None] = mapped_column(
        _TIMESTAMPTZ,
        nullable=True,
        comment=(
            "Set by step_monitor when a one-time 50%-of-timeout warning fires "
            "for this run; suppresses duplicate warns across poll cycles (CR-00024)."
        ),
    )
    # F-00081 — records which runtime option was used for this run (append-only, never modified)
    agent_runtime_option_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("agent_runtime_options.id", ondelete="RESTRICT"),
        nullable=True,
        comment="The resolved (cli_tool, model) pair used for this run. F-00081.",
    )
    # CR-00056 — prompt snapshots captured at step launch
    prompt_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment=(
            "Snapshot of the prompt content captured at step launch. "
            "Set by the daemon when this StepRun is created. NULL for pre-CR-00056 rows. "
            "Append-only — never updated after creation. (CR-00056)"
        ),
    )
    fix_prompt_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment=(
            "Snapshot of the fix-cycle prompt content for retry runs. "
            "Set by the daemon when a fix-cycle StepRun is created. NULL for "
            "non-fix-cycle runs and pre-CR-00056 rows. Append-only. (CR-00056)"
        ),
    )

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


class QvBaseline(Base):
    """Per-(step, gate, base_sha) failure fingerprint baseline.

    Stored at worktree-setup time so the daemon can subtract pre-existing
    failures from the HEAD run before deciding pass/fail and before
    composing the fix-cycle prompt. This prevents the 2026-04-22 scope
    blowout where pre-existing lint/pytest failures drove fix cycles.
    """

    __tablename__ = "qv_baselines"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    step_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="FK to workflow_steps.id",
    )
    gate_name: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Gate identifier matching WorkflowStep.gate (e.g. 'lint', 'unit-tests')",
    )
    base_sha: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Full git SHA the baseline was computed against (40-char)",
    )
    fingerprint: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{\"failures\": []}'"),
        comment="Parser-produced canonical failure set",
    )
    computed_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ,
        nullable=False,
        server_default=func.now(),
    )

    step: Mapped["WorkflowStep"] = relationship("WorkflowStep", back_populates="baselines")

    __table_args__ = (
        ForeignKeyConstraint(["step_id"], ["workflow_steps.id"], ondelete="CASCADE"),
        UniqueConstraint(
            "step_id",
            "gate_name",
            "base_sha",
            name="uq_qv_baselines_step_gate_sha",
        ),
        Index("idx_qv_baselines_step_id", "step_id"),
        {"comment": "Baseline QV gate fingerprints to prevent fix-cycle scope expansion (F-00061)"},
    )


class WorkItemEvidence(Base):
    """Work item evidence screenshots and snapshots as durable BLOBs.

    Ingested at two lifecycle points:
    - phase='pre': captured when a work item is approved (iw approve)
    - phase='post': captured when a browser_verification step completes (iw step-done)

    The FK to work_items has NO cascade — evidences survive work_item deletion
    so that archived items still display their evidences in the dashboard.
    """

    __tablename__ = "work_item_evidences"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "work_item_id",
            "phase",
            "filename",
            name="uq_evidence_per_file",
        ),
        ForeignKeyConstraint(
            ["project_id", "work_item_id"],
            ["work_items.project_id", "work_items.id"],
            name="fk_evidence_work_item",
        ),
        Index("ix_evidence_project_item_phase", "project_id", "work_item_id", "phase"),
        {"comment": "Work item evidence screenshots and snapshots as durable BLOBs (CR-00020)"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    project_id: Mapped[str] = mapped_column(Text, nullable=False)
    work_item_id: Mapped[str] = mapped_column(Text, nullable=False)
    phase: Mapped[EvidencePhase] = mapped_column(
        SAEnum(EvidencePhase, name="evidence_phase", create_type=False),
        nullable=False,
    )
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    step_id: Mapped[str | None] = mapped_column(Text, nullable=True)


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
    cli_tool: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'opencode'"),
        comment="LLM CLI tool used: 'opencode', 'claude', or 'pi'",
    )
    auto_publish: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        comment="Whether to auto-push to origin after all items merged",
    )
    auto_merge: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
        comment="Whether to auto-merge each item to main on success; "
        "false → operator must approve each merge",
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
    worktree_db_host: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Hostname or IP of the per-worktree Postgres container; "
        "NULL in legacy mode or when the compose stack has not yet been started.",
    )
    worktree_db_port: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Discovered host port for the per-worktree Postgres container; "
        "NULL when the project runs in legacy mode (no iw-config/)",
    )
    worktree_db_name: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Database name of the per-worktree Postgres; NULL in legacy mode.",
    )
    worktree_db_user: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Username for the per-worktree Postgres; NULL in legacy mode.",
    )
    worktree_db_password: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Password for the per-worktree Postgres; NULL in legacy mode.",
    )
    worktree_app_port: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Discovered host port for the per-worktree app server container; "
        "NULL when no app service is declared or in legacy mode",
    )
    worktree_compose_path: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Absolute filesystem path to the rendered docker-compose-<id>.yml; "
        "NULL in legacy mode. Used by the reaper and daemon-restart re-attach logic.",
    )

    # Forward-only relationships to teach the SQLAlchemy unit-of-work that
    # BatchItem inserts must follow Batch and WorkItem inserts. Without these,
    # a session that adds parent + child rows in the same flush emits
    # batch_items INSERTs before work_items / batches INSERTs and raises
    # ForeignKeyViolation — table-level ForeignKeyConstraint alone does not
    # drive ORM mapper-level dependency sorting. Kept forward-only (no
    # back_populates) so Batch / WorkItem instances do not gain a collection
    # attribute that would change query behaviour elsewhere.
    # ``overlaps`` acknowledges that both composite FKs share project_id —
    # silencing the SAWarning is intentional, not a bug to suppress.
    batch: Mapped[Batch] = relationship("Batch", overlaps="work_item")
    work_item: Mapped[WorkItem] = relationship("WorkItem", overlaps="batch")

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


class IwCoreInstance(Base):
    """Orchestration DB identity fingerprint — single-row table.

    The CHECK constraint (id = 1) guarantees exactly one row can ever exist.
    instance_id is a randomly-generated UUID assigned at first deployment;
    every subsequent deployment seeds the same row via ON CONFLICT DO NOTHING.
    See CR-00014.
    """

    __tablename__ = "iw_core_instance"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_iw_core_instance_single_row"),
        {"comment": "Orchestration DB identity fingerprint — see CR-00014"},
    )

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    instance_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
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
    entity_type: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Type of entity_id: work_item, batch, step, doc_job, or NULL",
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


class MergeAutoVerdict(Base):
    """Operator verdicts for auto-merge outcomes per daemon event."""

    __tablename__ = "merge_auto_verdicts"

    project_id: Mapped[str] = mapped_column(Text, nullable=False)
    daemon_event_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    verdict: Mapped[str] = mapped_column(Text, nullable=False)
    verdict_notes: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("''"),
    )
    verdicted_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    verdicted_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ, nullable=False, server_default=func.now()
    )

    __table_args__ = (
        PrimaryKeyConstraint("project_id", "daemon_event_id"),
        ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["daemon_event_id"], ["daemon_events.id"], ondelete="CASCADE"),
        CheckConstraint(
            "verdict IN ('pending','correct','wrong','partial')",
            name="ck_merge_auto_verdicts_verdict",
        ),
        {
            "comment": "Operator verdicts for auto-merge outcomes per daemon event",
        },
    )


class AutoMergeProjectConfig(Base):
    """Per-project operator overrides for auto-merge behavior."""

    __tablename__ = "auto_merge_project_config"

    project_id: Mapped[str] = mapped_column(Text, nullable=False)
    phase: Mapped[int | None] = mapped_column(Integer, nullable=True)
    runtime_option_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ, nullable=False, server_default=func.now()
    )
    updated_by: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        PrimaryKeyConstraint("project_id"),
        ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(
            ["runtime_option_id"], ["agent_runtime_options.id"], ondelete="SET NULL"
        ),
        CheckConstraint(
            "phase IS NULL OR phase IN (0, 1)",
            name="ck_auto_merge_project_config_phase",
        ),
        {
            "comment": "Per-project operator overrides for auto-merge behavior",
        },
    )


class PendingMigrationLog(Base):
    """CR-00017 audit log for daemon-driven migration phases. Append-only."""

    __tablename__ = "pending_migration_log"
    __table_args__ = (
        CheckConstraint(
            "direction IN ('upgrade', 'downgrade')",
            name="ck_pending_migration_log_direction",
        ),
        CheckConstraint(
            "phase IN ('dry_run', 'apply', 'rollback', 'rebase')",
            name="ck_pending_migration_log_phase",
        ),
        Index(
            "ix_pending_migration_log_batch",
            "batch_id",
            text("started_at DESC"),
        ),
        Index(
            "ix_pending_migration_log_revision",
            "revision",
            "phase",
        ),
        {"comment": "CR-00017 audit log for daemon-driven migration phases"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    revision: Mapped[str] = mapped_column(Text, nullable=False)
    old_revision: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Previous down_revision string before the rebase phase rewrote it "
        "(phase='rebase' only)",
    )
    direction: Mapped[str] = mapped_column(Text, nullable=False)
    phase: Mapped[str] = mapped_column(Text, nullable=False)
    batch_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ, nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(_TIMESTAMPTZ, nullable=True)
    success: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    stdout_tail: Mapped[str | None] = mapped_column(Text, nullable=True)
    stderr_tail: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ, nullable=False, server_default=func.now()
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
    public_id: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Human-readable ID (DOC-00001, DOC-00002, ...). Allocated via id_sequences['DOC'].",
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
    report: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment=(
            "Structured post-mortem of the job: outcome, duration_seconds, "
            "skill_used, cli_tool, command_issued, log_size_bytes, log_line_count, "
            "tool_calls, doc_update_invocations, lint_warning_count, diagnosis."
        ),
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
        Index("ix_doc_generation_jobs_public_id", "public_id", unique=True),
        {"comment": "Async AI documentation generation job tracking"},
    )


@event.listens_for(DocGenerationJob, "before_insert")
def _doc_generation_job_allocate_public_id(
    _mapper: Mapper[Any], connection: Connection, target: DocGenerationJob
) -> None:
    """Auto-allocate ``DOC-NNNNN`` public_id from id_sequences if not set."""
    if target.public_id is not None:
        return
    n = connection.execute(
        text(
            "INSERT INTO id_sequences (prefix, next_number) VALUES ('DOC', 2)"
            " ON CONFLICT (prefix) DO UPDATE"
            " SET next_number = id_sequences.next_number + 1"
            " RETURNING next_number - 1"
        )
    ).scalar()
    target.public_id = f"DOC-{int(n or 1):05d}"


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
    public_id: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Human-readable ID (CM-00001, CM-00002, ...). Allocated via id_sequences['CM'].",
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
        Index("ix_code_index_jobs_public_id", "public_id", unique=True),
        {"comment": "Tracks code indexing jobs for a project"},
    )


@event.listens_for(CodeIndexJob, "before_insert")
def _code_index_job_allocate_public_id(
    _mapper: Mapper[Any], connection: Connection, target: CodeIndexJob
) -> None:
    """Auto-allocate ``CM-NNNNN`` public_id from id_sequences if not set."""
    if target.public_id is not None:
        return
    n = connection.execute(
        text(
            """
            INSERT INTO id_sequences (prefix, next_number) VALUES ('CM', 2)
            ON CONFLICT (prefix) DO UPDATE
                SET next_number = id_sequences.next_number + 1
            RETURNING next_number - 1 AS n
            """
        )
    ).scalar()
    target.public_id = f"CM-{int(n or 1):05d}"


class DocIndexJob(Base):
    """Tracks a doc indexing job for a project."""

    __tablename__ = "doc_index_jobs"

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
    items_discovered: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0"), comment="Total items found"
    )
    items_indexed: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0"), comment="Items successfully indexed"
    )
    chunks_created: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0"), comment="Total chunks produced"
    )
    errors: Mapped[Any] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'"), comment="List of error messages"
    )
    triggered_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ,
        nullable=False,
        server_default=func.now(),
        comment="When the job was triggered",
    )
    started_at: Mapped[datetime | None] = mapped_column(
        _TIMESTAMPTZ, nullable=True, comment="When the job started"
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        _TIMESTAMPTZ, nullable=True, comment="When the job finished (success or failure)"
    )
    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Error message if status='failed'"
    )

    __table_args__ = (
        ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        Index("idx_doc_index_jobs_project_id", "project_id"),
        Index("idx_doc_index_jobs_status", "status"),
        {"comment": "Tracks doc indexing jobs for a project"},
    )


class OssScan(Base):
    """OSS compliance scan runs."""

    __tablename__ = "oss_scan"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ, nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(_TIMESTAMPTZ, nullable=True)
    status: Mapped[OssScanStatus] = mapped_column(
        _oss_scan_status_col, nullable=False, default=OssScanStatus.pending
    )
    mode: Mapped[OssScanMode] = mapped_column(
        _oss_scan_mode_col, nullable=False, default=OssScanMode.scan
    )
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    head_sha: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Git HEAD SHA at scan start"
    )
    pill_color: Mapped[OssPillColor | None] = mapped_column(_oss_pill_color_col, nullable=True)
    summary_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True, comment="Counts-by-severity summary"
    )
    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Error message if status='error'"
    )

    project: Mapped["Project"] = relationship("Project", back_populates="oss_scans")
    findings: Mapped[list["OssFinding"]] = relationship(
        "OssFinding", back_populates="scan", cascade="all, delete-orphan"
    )
    tool_runs: Mapped[list["OssToolRun"]] = relationship(
        "OssToolRun", back_populates="scan", cascade="all, delete-orphan"
    )

    __table_args__ = (
        ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        Index("ix_oss_scan_project_started", "project_id", text("started_at DESC")),
        {"comment": "OSS compliance scan runs"},
    )


class OssFinding(Base):
    """Individual OSS compliance findings."""

    __tablename__ = "oss_finding"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    scan_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    check_id: Mapped[str] = mapped_column(
        Text, nullable=False, comment="Check identifier (e.g., OSS-LIC-01)"
    )
    severity: Mapped[OssFindingSeverity] = mapped_column(_oss_finding_severity_col, nullable=False)
    status: Mapped[OssFindingStatus] = mapped_column(_oss_finding_status_col, nullable=False)
    domain: Mapped[str] = mapped_column(Text, nullable=False, comment="license, secrets, etc.")
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    remediation: Mapped[str | None] = mapped_column(Text, nullable=True)
    auto_fix_available: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    auto_apply_safe: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    osps_control: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="OSPS control reference"
    )
    tool: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    rationale: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Per-check rationale paragraph",
    )

    scan: Mapped["OssScan"] = relationship("OssScan", back_populates="findings")
    details: Mapped[list["OssFindingDetail"]] = relationship(
        "OssFindingDetail",
        back_populates="finding",
        cascade="all, delete-orphan",
        order_by="OssFindingDetail.ordinal",
    )

    __table_args__ = (
        ForeignKeyConstraint(["scan_id"], ["oss_scan.id"], ondelete="CASCADE"),
        Index("ix_oss_finding_scan", "scan_id"),
        Index("ix_oss_finding_scan_sev_stat", "scan_id", "severity", "status"),
        {"comment": "Individual OSS compliance findings"},
    )


class OssToolRun(Base):
    """Tier-1 tool execution records within an OSS scan."""

    __tablename__ = "oss_tool_run"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    scan_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    tool: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[OssToolRunStatus] = mapped_column(_oss_tool_run_status_col, nullable=False)
    started_at: Mapped[datetime] = mapped_column(_TIMESTAMPTZ, nullable=False)
    runtime_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_summary: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="First 2KB of stdout/stderr"
    )

    scan: Mapped["OssScan"] = relationship("OssScan", back_populates="tool_runs")

    __table_args__ = (
        ForeignKeyConstraint(["scan_id"], ["oss_scan.id"], ondelete="CASCADE"),
        Index("ix_oss_tool_run_scan", "scan_id"),
        {"comment": "Tier-1 tool execution records within an OSS scan"},
    )


class OssFindingDetail(Base):
    """Per-result rows for a multi-result OSS finding (e.g. each gitleaks hit).

    Lets the UI render a paginated table of file/line/rule/snippet without
    bloating ``OssFinding.evidence_json`` when one finding aggregates thousands
    of underlying matches.
    """

    __tablename__ = "oss_finding_detail"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    finding_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    ordinal: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Stable order from the source SARIF"
    )
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    line_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rule_id: Mapped[str] = mapped_column(Text, nullable=False)
    snippet_masked: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Secret value with middle bytes redacted"
    )
    created_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ, nullable=False, server_default=func.now()
    )

    finding: Mapped["OssFinding"] = relationship("OssFinding", back_populates="details")

    __table_args__ = (
        ForeignKeyConstraint(["finding_id"], ["oss_finding.id"], ondelete="CASCADE"),
        Index("ix_oss_finding_detail_finding", "finding_id"),
        {"comment": "Per-result rows for a multi-result OSS finding"},
    )


class ProjectOssJob(Base):
    """Async OSS scan/install/fix job tracking."""

    __tablename__ = "project_oss_job"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Human-readable ID (O-00001, O-00002, ...). Allocated via id_sequences['O'].",
    )
    project_id: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[ProjectOssJobKind] = mapped_column(_project_oss_job_kind_col, nullable=False)
    status: Mapped[ProjectOssJobStatus] = mapped_column(
        _project_oss_job_status_col, nullable=False, server_default=text("'queued'")
    )
    created_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ, nullable=False, server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(_TIMESTAMPTZ, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(_TIMESTAMPTZ, nullable=True)
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scan_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        comment="FK to oss_scan.id when kind=scan; NULL otherwise",
    )
    stdout_tail: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Last 16KB of combined stdout/stderr"
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    base_sha: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Git HEAD SHA when the job was fired",
    )

    project: Mapped["Project"] = relationship("Project", back_populates="oss_jobs")
    scan: Mapped["OssScan | None"] = relationship(
        "OssScan", foreign_keys=[scan_id], back_populates=None
    )

    __table_args__ = (
        ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["scan_id"], ["oss_scan.id"], ondelete="SET NULL"),
        Index("ix_project_oss_job_project_created", "project_id", text("created_at DESC")),
        Index("ix_project_oss_job_status", "status"),
        Index("ix_project_oss_job_public_id", "public_id", unique=True),
        {"comment": "Async OSS scan/install/fix job tracking"},
    )


@event.listens_for(ProjectOssJob, "before_insert")
def _project_oss_job_allocate_public_id(
    _mapper: Mapper[Any], connection: Connection, target: ProjectOssJob
) -> None:
    """Auto-allocate ``O-NNNNN`` public_id from id_sequences if not set.

    Uses an atomic UPSERT with RETURNING — equivalent to the
    ``allocate_next_id(..., 'O')`` semantics but works at the connection
    level inside an INSERT flush.
    """
    if target.public_id is not None:
        return
    n = connection.execute(
        text(
            """
            INSERT INTO id_sequences (prefix, next_number) VALUES ('O', 2)
            ON CONFLICT (prefix) DO UPDATE
                SET next_number = id_sequences.next_number + 1
            RETURNING next_number - 1 AS n
            """
        )
    ).scalar()
    target.public_id = f"O-{int(n):05d}"


# ---------------------------------------------------------------------------
# Keep-Alive Scheduler models
# ---------------------------------------------------------------------------


class KeepAliveConfig(Base):
    """Singleton global configuration for the Keep-Alive Scheduler (id=1 always)."""

    __tablename__ = "keep_alive_config"
    __table_args__ = {"comment": "Singleton global config for the Keep-Alive Scheduler"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # always 1
    model: Mapped[str] = mapped_column(String(100), nullable=False, default="claude-sonnet-4-6")
    window_duration_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    updated_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    slots: Mapped[list["KeepAliveSlot"]] = relationship(
        "KeepAliveSlot", back_populates="config", passive_deletes=True
    )


class KeepAliveSlot(Base):
    """One row per scheduled keep-alive time slot."""

    __tablename__ = "keep_alive_slots"
    __table_args__ = (
        UniqueConstraint("time_hhmm", name="uq_keep_alive_slots_time"),
        {"comment": "Scheduled keep-alive time slots"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    time_hhmm: Mapped[str] = mapped_column(String(5), nullable=False)  # "HH:MM"
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ, nullable=False, server_default=func.now()
    )

    config_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("keep_alive_config.id", ondelete="CASCADE"),
        nullable=False,
        default=1,
    )
    config: Mapped["KeepAliveConfig"] = relationship("KeepAliveConfig", back_populates="slots")
    runs: Mapped[list["KeepAliveRun"]] = relationship(
        "KeepAliveRun", back_populates="slot", passive_deletes=True
    )


class KeepAliveRun(Base):
    """Execution log for keep-alive firings."""

    __tablename__ = "keep_alive_runs"
    __table_args__ = {"comment": "Execution log for keep-alive firings"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    slot_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("keep_alive_slots.id", ondelete="SET NULL"),
        nullable=True,
    )
    slot_time: Mapped[str] = mapped_column(
        String(5), nullable=False, comment="Snapshot of 'HH:MM' at fire time"
    )
    fired_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ, nullable=False, server_default=func.now()
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="success|failed|retried_success|retried_failed",
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    slot: Mapped["KeepAliveSlot | None"] = relationship("KeepAliveSlot", back_populates="runs")


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

FUNCTIONAL_DOC_FTS_FUNCTION_SQL = """\
CREATE OR REPLACE FUNCTION work_items_functional_doc_search_update() RETURNS trigger AS $$
BEGIN
    NEW.functional_doc_search := to_tsvector(
        'english',
        COALESCE(NEW.title, '') || ' ' || COALESCE(NEW.functional_doc_content, '')
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

FUNCTIONAL_DOC_FTS_TRIGGER_SQL = """\
CREATE TRIGGER work_items_functional_doc_search_trg
    BEFORE INSERT OR UPDATE OF title, functional_doc_content
    ON work_items
    FOR EACH ROW
    EXECUTE FUNCTION work_items_functional_doc_search_update();
"""

DROP_FUNCTIONAL_DOC_FTS_TRIGGER_SQL = (
    "DROP TRIGGER IF EXISTS work_items_functional_doc_search_trg ON work_items;"
)
DROP_FUNCTIONAL_DOC_FTS_FUNCTION_SQL = (
    "DROP FUNCTION IF EXISTS work_items_functional_doc_search_update();"
)


# ---------------------------------------------------------------------------
# Chat models (F-00077 — Code chat conversation memory with persistence)
# ---------------------------------------------------------------------------


class ChatConversation(Base):
    """Persists a chat conversation session scoped to (project_id, session_id)."""

    __tablename__ = "chat_conversations"

    id: Mapped[str] = mapped_column(
        Text,
        primary_key=True,
        server_default=text("gen_random_uuid()::text"),
        comment="UUID as text, generated by PostgreSQL",
    )
    project_id: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="FK to projects(id); app-layer enforcement of project scoping",
    )
    session_id: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Browser session cookie (iw_chat_session) — scoped to (project_id, session_id)",
    )
    module_path: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Snapshot of module_path from the first turn; NULL for architecture-level chats",
    )
    context_level: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'architecture'"),
        comment="architecture | module — snapshot from first turn",
    )
    title: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="First user question, truncated to 80 chars; NULL until first message persists",
    )
    rolling_summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Compact prose summary produced by ChatSummarizationJob; prepended to LLM history",
    )
    summary_through_message_id: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="FK to chat_messages.id — last message included in rolling_summary",
    )
    created_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ,
        nullable=False,
        server_default=func.now(),
        comment="When the conversation row was created",
    )
    last_active_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ,
        nullable=False,
        server_default=func.now(),
        comment="Updated on every new assistant message",
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        _TIMESTAMPTZ,
        nullable=True,
        comment="Soft-delete timestamp; NULL means active",
    )

    __table_args__ = (
        Index(
            "idx_chat_conversations_project_session_recent",
            "project_id",
            "session_id",
            "last_active_at",
            postgresql_where=text("archived_at IS NULL"),
        ),
        {"comment": "Chat conversation sessions scoped to (project_id, session_id)"},
    )


class ChatMessage(Base):
    """Append-only turn inside a ChatConversation.

    Invariant 1: UPDATE is forbidden except for same-transaction metadata.error=true
    flag set immediately after insert (stream-disconnected case).
    """

    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(
        Text,
        primary_key=True,
        server_default=text("gen_random_uuid()::text"),
        comment="UUID as text, generated by PostgreSQL",
    )
    conversation_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("chat_conversations.id", ondelete="CASCADE"),
        nullable=False,
        comment="FK to chat_conversations.id",
    )
    role: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="chat_message_role ENUM: user | assistant | system",
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Message text; no upper bound — caller validates size",
    )
    token_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
        comment="Token count via tiktoken (or len(content)//4 heuristic); set at insert, never updated",  # noqa: E501
    )
    message_metadata: Mapped[Any] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        comment=(
            "JSONB metadata. Key: metadata (DDL column name) — Python attr: message_metadata "
            "(SQLAlchemy reserves 'metadata' on DeclarativeBase). "
            "Append-only: direct UPDATE forbidden EXCEPT to set metadata.error=true "
            "within the same transaction as the INSERT (stream-disconnected case)."
        ),
    )
    created_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ,
        nullable=False,
        server_default=func.now(),
        comment="When the message row was inserted",
    )

    __table_args__ = (
        Index("idx_chat_messages_conversation_created", "conversation_id", "created_at"),
        {"comment": "Append-only chat message turns."},
    )


class ChatSummarizationJob(Base):
    """Background job that produces a rolling_summary for a ChatConversation.

    Modeled on CodeIndexJob; single-purpose job table per project convention.
    """

    __tablename__ = "chat_summarization_jobs"

    id: Mapped[str] = mapped_column(
        Text,
        primary_key=True,
        server_default=text("gen_random_uuid()::text"),
        comment="UUID as text, generated by PostgreSQL",
    )
    conversation_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("chat_conversations.id", ondelete="CASCADE"),
        nullable=False,
        comment="FK to chat_conversations.id",
    )
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'queued'"),
        comment="queued | running | completed | failed | cancelled",
    )
    messages_summarized: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
        comment="Number of messages summarised into rolling_summary",
    )
    summary_through_message_id: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="FK to chat_messages.id — last message included in the summary",
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Error detail when status=failed",
    )
    triggered_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ,
        nullable=False,
        server_default=func.now(),
        comment="When the job was enqueued (hard budget overflow detected)",
    )
    started_at: Mapped[datetime | None] = mapped_column(
        _TIMESTAMPTZ,
        nullable=True,
        comment="When the daemon picked up the job",
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        _TIMESTAMPTZ,
        nullable=True,
        comment="When the job finished (success or failure)",
    )
    created_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ,
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ,
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        Index("idx_chat_summarization_jobs_status", "status", "triggered_at"),
        Index(
            "uq_chat_summarization_jobs_one_in_flight",
            "conversation_id",
            unique=True,
            postgresql_where=text("status IN ('queued', 'running')"),
        ),
        {"comment": "Background summarisation jobs for ChatConversation rolling_summary"},
    )


# ---------------------------------------------------------------------------
# Chat Assistant tabs (F-00086 — Multi-tab AI Assistant on OpenCode)
# ---------------------------------------------------------------------------


class ChatTab(Base):
    """A single user-facing AI Assistant tab bound to one runtime session.

    Each row represents one tab in the multi-tab chat panel. The runtime
    column shape is intentionally a plain Text with allowlist enforced in
    ``orch/chat/tab_service.py`` (matches CR-00062's ``cli_tool`` pattern,
    avoiding a PostgreSQL ENUM that would require a migration to extend).

    Soft-delete semantics: closing a tab sets ``status='closed'`` and
    ``closed_at=now()``; the ``opencode_session_id`` is preserved so that
    ``reopen_tab`` can restore the full message history.

    The partial unique index ``uq_chat_tabs_default_per_project`` exists
    only to guard the bootstrap_default_tab race window — see F-00086
    Boundary row "Bootstrap called twice concurrently".
    """

    __tablename__ = "chat_tabs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    title: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'New chat'"),
        comment="Tab title shown in the strip; user-editable",
    )
    runtime: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'opencode'"),
        comment="Chat runtime: 'opencode' today; 'pi' added by F-B",
    )
    model: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Model identifier scoped to runtime (e.g., 'anthropic/claude-sonnet-4-7')",
    )
    project_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        comment="FK to projects.id; deleting a project cascades to its tabs",
    )
    opencode_session_id: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="OpenCode session id; populated after first session create",
    )
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'active'"),
        comment="Tab status: 'active' or 'closed' (soft-delete)",
    )
    created_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ,
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ,
        nullable=False,
        server_default=func.now(),
    )
    last_active_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ,
        nullable=False,
        server_default=func.now(),
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        _TIMESTAMPTZ,
        nullable=True,
        comment="When the tab was soft-deleted; NULL when active",
    )

    __table_args__ = (
        Index(
            "ix_chat_tabs_status_last_active",
            "status",
            text("last_active_at DESC"),
        ),
        Index("ix_chat_tabs_project_status", "project_id", "status"),
        Index(
            "uq_chat_tabs_default_per_project",
            "project_id",
            unique=True,
            postgresql_where=text("title = 'Default' AND status = 'active'"),
        ),
        {"comment": "Multi-tab AI Assistant chat tabs (F-00086)"},
    )
