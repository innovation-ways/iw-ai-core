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

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, doc="Primary key identifier."
    )
    cli_tool: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="CLI launcher name used to run this model (for example, claude-code).",
    )
    model: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Provider-specific model identifier passed to the selected CLI tool.",
    )
    cli_label: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Human-friendly label shown for the CLI tool in dashboard selectors.",
    )
    model_label: Mapped[str] = mapped_column(
        Text, nullable=False, doc="Human-friendly label shown for the model in dashboard selectors."
    )
    display_name: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Combined display name presented to users for this runtime option.",
    )
    is_default: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        doc=("Marks the default runtime option used when a project has no model override."),
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
        doc="Controls whether this runtime option is selectable for new daemon runs.",
    )
    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
        doc="Ascending UI order for runtime options in dashboard pickers.",
    )
    context_window_tokens: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment=(
            "Maximum context window size in tokens for this model. "
            "Used to compute the context usage percentage shown in the step table. "
            "NULL = unknown / not yet configured. (CR-00066)"
        ),
        doc="Maximum context window size in tokens for this model; NULL when not yet configured.",
    )
    max_output_tokens: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment=(
            "Maximum output tokens this model can generate in a single response. "
            "Used to compute the EFFECTIVE input budget (context_window - max_output - buffer). "
            "NULL = unknown / not yet configured. (I-00105)"
        ),
        doc="Maximum output tokens this model can generate in one response; NULL when unknown.",
    )

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


# F-00090 — regression classification enum
class RegressionClassification(enum.Enum):
    regression = "regression"
    pre_existing = "pre_existing"
    unknown = "unknown"


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
_regression_classification_col = SAEnum(
    RegressionClassification, name="regression_classification_enum", create_type=False
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
        doc="Unique short identifier for this project (e.g., 'innoforge', 'iw-ai-core').",
    )
    display_name: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Human-readable project name",
        doc="Human-readable project name shown in the dashboard and CLI output.",
    )
    repo_root: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Absolute path to the main clone repo root",
        doc="Absolute filesystem path to the main git clone root for this project.",
    )
    dev_clone: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Absolute path to the development clone (optional)",
        doc=(
            "Absolute filesystem path to an optional secondary development clone; NULL when unused."
        ),
    )
    config: Mapped[Any] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'"),
        comment="Full .iw-orch.json content as JSONB",
        doc="Full contents of .iw-orch.json for this project, stored as JSONB.",
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
        comment="Whether the daemon processes this project",
        doc="Whether the daemon actively processes this project; false pauses all scheduling.",
    )
    oss_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        comment="Whether OSS compliance scanning is enabled for this project",
        doc="Whether OSS compliance scanning is enabled and scheduled for this project.",
    )
    registered_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ,
        nullable=False,
        server_default=func.now(),
        doc="UTC timestamp when this project was first registered with the orchestrator.",
    )
    updated_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ,
        nullable=False,
        server_default=func.now(),
        doc="UTC timestamp when this row was last updated.",
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
        doc="ID prefix used as the primary key (e.g., 'F', 'I', 'CR', 'BATCH', 'DOC', 'CM').",
    )
    next_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("1"),
        comment="Next number to allocate (incremented atomically via FOR UPDATE)",
        doc="Next sequence number to allocate; incremented atomically via SELECT FOR UPDATE.",
    )

    __table_args__ = ({"comment": "Global atomic sequential ID allocation per prefix"},)


class IdAllocation(Base):
    """Audit log of keyed ID allocations for idempotent iw next-id (CR-00053)."""

    __tablename__ = "id_allocations"

    prefix: Mapped[str] = mapped_column(
        Text,
        primary_key=True,
        comment="ID prefix: 'F' (Feature), 'I' (Issue), 'CR' (ChangeRequest), 'BATCH'",
        doc="ID prefix component of the composite PK (e.g., 'F', 'I', 'CR').",
    )
    number: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        comment="Allocated sequence number",
        doc="Allocated sequence number, forming the numeric part of the composite PK.",
    )
    idempotency_key: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Client-supplied idempotency key (NULL when no key provided)",
        doc=(
            "Client-supplied idempotency key that prevents double-allocation; NULL when not "
            "provided."
        ),
    )
    project_id: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Project that requested this allocation",
        doc="Owning project identifier.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
        comment="UTC timestamp of allocation",
        doc="UTC timestamp when this row was created.",
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

    project_id: Mapped[str] = mapped_column(
        Text, primary_key=True, doc="Owning project identifier (FK to projects.id, composite PK)."
    )
    id: Mapped[str] = mapped_column(
        Text,
        primary_key=True,
        doc="Work item identifier (e.g., 'F-00042', 'CR-00007'), composite PK with project_id.",
    )
    type: Mapped[WorkItemType] = mapped_column(
        _work_item_type_col,
        nullable=False,
        doc=("Kind of work item (WorkItemType enum: Feature/Issue/ChangeRequest/Research)."),
    )
    title: Mapped[str] = mapped_column(
        Text, nullable=False, doc="Short human-readable title of the work item."
    )
    status: Mapped[WorkItemStatus] = mapped_column(
        _work_item_status_col,
        nullable=False,
        server_default=text("'draft'"),
        doc=(
            "Lifecycle status of the work item (WorkItemStatus enum:"
            " draft/approved/in_progress/completed/failed/paused/cancelled)."
        ),
    )
    phase: Mapped[WorkItemPhase] = mapped_column(
        _work_item_phase_col,
        nullable=False,
        server_default=text("'active'"),
        doc=(
            "Coarse lifecycle phase grouping the item for dashboard views"
            " (WorkItemPhase enum: active/work/done)."
        ),
    )
    config: Mapped[Any] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'"),
        comment="Item-level config: fix_cycle_max, browser_verification, etc.",
        doc="Item-level JSONB config overrides (fix_cycle_max, browser_verification, etc.).",
    )
    depends_on: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        server_default=text("'{}'"),
        comment="Array of work item IDs this item depends on",
        doc="Array of work item IDs that must complete before this item can start.",
    )
    blocks: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        server_default=text("'{}'"),
        comment="Array of work item IDs this item blocks",
        doc="Array of work item IDs that cannot start until this item finishes.",
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
        doc=(
            "JSONB array of file-glob patterns this item is expected to touch; drives overlap "
            "gates."
        ),
    )
    manifest_digest: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment=(
            "SHA-256 hex digest of the canonicalized steps array from "
            "workflow-manifest.json at register/approve time. NULL for "
            "pre-I-00102 items. Used by iw approve to detect on-disk "
            "manifest drift and auto-refresh workflow_steps when the "
            "item is still in draft. See I-00102."
        ),
        doc=(
            "SHA-256 hex digest of the workflow-manifest.json steps array captured at"
            " register/approve time; NULL for pre-I-00102 items."
        ),
    )
    design_doc_path: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Relative path to design doc in project repo (active items)",
        doc="Relative path to the design document markdown file in the project repo.",
    )
    # Tier 1
    design_doc_content: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment=(
            "Full markdown of design doc "
            "(Tier 1 — stored on archive for instant dashboard rendering)"
        ),
        doc="Full markdown content of the design doc stored in-DB for instant dashboard rendering.",
    )
    design_doc_search: Mapped[str | None] = mapped_column(
        TSVECTOR,
        nullable=True,
        comment="PostgreSQL tsvector for full-text search across design docs",
        doc=(
            "PostgreSQL tsvector for full-text search over title + design_doc_content;"
            " maintained by a BEFORE INSERT OR UPDATE trigger."
        ),
    )
    functional_doc_path: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Relative path to functional design doc in project repo (active items)",
        doc="Relative path to the functional design document markdown file in the project repo.",
    )
    functional_doc_content: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment=(
            "Full markdown of functional design doc "
            "(Tier 1 — stored on archive for instant dashboard rendering)"
        ),
        doc=(
            "Full markdown content of the functional design doc stored in-DB"
            " for instant dashboard rendering."
        ),
    )
    functional_doc_search: Mapped[str | None] = mapped_column(
        TSVECTOR,
        nullable=True,
        comment="PostgreSQL tsvector for full-text search across functional design docs",
        doc=(
            "PostgreSQL tsvector for full-text search over title + functional_doc_content;"
            " maintained by a BEFORE INSERT OR UPDATE trigger."
        ),
    )
    summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="AI-generated 2-3 line summary for list views and search results",
        doc="AI-generated 2–3 line summary of the work item for list views and search results.",
    )
    # Tier 2
    archive_path: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Relative path to .tar.zst in archive directory (Tier 2)",
        doc="Relative path to the .tar.zst archive file in the Tier 2 archive directory.",
    )
    archive_size_bytes: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        comment="Compressed archive file size in bytes",
        doc="Size in bytes of the compressed Tier 2 archive file.",
    )
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ,
        nullable=False,
        server_default=func.now(),
        doc="UTC timestamp when this row was created.",
    )
    updated_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ,
        nullable=False,
        server_default=func.now(),
        doc="UTC timestamp when this row was last updated.",
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        _TIMESTAMPTZ, nullable=True, doc="UTC timestamp when processing completed."
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        _TIMESTAMPTZ,
        nullable=True,
        comment="When the item was archived (Tier 1 + Tier 2 stored, active files deleted)",
        doc=(
            "UTC timestamp when this item was archived (Tier 1 + Tier 2 stored, active files "
            "removed)."
        ),
    )
    # Files view — aggregate diff (captured at squash merge)
    diff_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Raw unified diff of the squash commit captured at merge time",
        doc="Raw unified diff of the squash commit captured at merge time.",
    )
    diff_summary: Mapped[Any | None] = mapped_column(
        JSONB,
        nullable=True,
        comment=(
            "Parsed file metadata: list of objects with keys path, status "
            "(A/M/D/R), added, removed, is_generated, is_binary, old_path"
        ),
        doc=(
            "JSONB list of per-file diff metadata objects"
            " (path, status A/M/D/R, added, removed, is_generated, is_binary, old_path)."
        ),
    )
    merge_commit_sha: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="SHA of the squash commit on main; enables lazy git diff for completed items",
        doc="SHA of the squash-merge commit on main; NULL until the item is merged.",
    )
    # F-00081 — per-item agent+model override (NULL = inherit project/catalogue default)
    agent_runtime_option_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("agent_runtime_options.id", ondelete="RESTRICT"),
        nullable=True,
        comment="Override pair to use for this item; NULL = inherit. F-00081.",
        doc=(
            "FK to agent_runtime_options.id overriding the agent/model for this item;"
            " NULL inherits the project or catalogue default."
        ),
    )
    # F-00090 — regression-link fields
    introduced_by_work_item_id: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment=(
            "ID of the work item whose merge introduced the regression this Incident "
            "reports. NULL when not yet classified or when the classification is "
            "pre-existing/unknown. Indexed for badge-count rollups on Batches/History "
            "views (F-00090)."
        ),
        doc=(
            "ID of the work item whose merge introduced the regression reported by this Incident;"
            " NULL when unclassified or not applicable."
        ),
    )
    introduced_by_commit_sha: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment=(
            "Optional commit SHA the operator pasted alongside the introducing work item; "
            "used when the operator knows the exact commit (F-00090)."
        ),
        doc="Commit SHA of the specific commit that introduced the regression; NULL when unknown.",
    )
    regression_classification: Mapped[RegressionClassification | None] = mapped_column(
        _regression_classification_col,
        nullable=True,
        comment=(
            "How this Incident relates to a prior merge: regression / pre_existing / unknown. "
            "NULL means not yet classified (F-00090)."
        ),
        doc=(
            "Regression classification for this Incident"
            " (RegressionClassification enum: regression/pre_existing/unknown);"
            " NULL means not yet classified."
        ),
    )
    classified_at: Mapped[datetime | None] = mapped_column(
        _TIMESTAMPTZ,
        nullable=True,
        comment="UTC timestamp when the regression classification was last persisted (F-00090).",
        doc="UTC timestamp when the regression_classification was last recorded.",
    )
    classified_by: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment=(
            "Identity that performed the classification — 'operator:<user>' for UI submissions, "
            "'heuristic:auto' when the operator accepted the heuristic's top suggestion (F-00090)."
        ),
        doc=(
            "Identity string for the classifier"
            " ('operator:<user>' for UI submissions, 'heuristic:auto' for accepted suggestions)."
        ),
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
        Index("ix_work_items_introduced_by_work_item_id", "introduced_by_work_item_id"),
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

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, doc="Primary key identifier."
    )
    project_id: Mapped[str] = mapped_column(Text, nullable=False, doc="Owning project identifier.")
    work_item_id: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc=(
            "FK to work_items.id — the work item this step belongs to (composite FK with "
            "project_id)."
        ),
    )
    step_number: Mapped[int] = mapped_column(
        Integer, nullable=False, doc="1-based ordinal position of this step within the work item."
    )
    step_id: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Step identifier within the item (e.g., 'S01', 'S02')",
        doc="Step identifier string within the work item (e.g., 'S01', 'S02').",
    )
    agent_label: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Agent label for file naming (e.g., 'Backend', 'CodeReview_Backend')",
        doc=(
            "Agent label used for prompt/report file naming (e.g., 'Backend', "
            "'CodeReview_Backend')."
        ),
    )
    opencode_agent: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="OpenCode/Claude agent to invoke (e.g., 'backend-impl', 'code-review-impl')",
        doc="Agent command name passed to the CLI tool (e.g., 'backend-impl', 'code-review-impl').",
    )
    step_type: Mapped[StepType] = mapped_column(
        _step_type_col,
        nullable=False,
        doc=(
            "Classification of this step (StepType enum: implementation/code_review"
            "/code_review_fix/code_review_final/code_review_fix_final"
            "/quality_validation/qv_fix/browser_verification/self_assess)."
        ),
    )
    step_label: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Short human-readable label for the step (e.g., 'ruff lint', 'unit tests')",
        doc="Short human-readable label for display in the dashboard (e.g., 'ruff lint').",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Extended human-readable description of what this step does; NULL when not provided.",
    )
    command: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment=(
            "Shell command for qv-gate steps (e.g., 'make lint'). NULL for "
            "non-gate steps and for items registered before CR-00023."
        ),
        doc=(
            "Shell command executed for quality-validation gate steps (e.g., 'make lint'); NULL "
            "for non-gate steps."
        ),
    )
    gate: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment=(
            "Gate name for qv-gate steps (e.g., 'lint', 'format', 'typecheck'). "
            "NULL for non-gate steps and for items registered before CR-00023."
        ),
        doc=(
            "Gate name for QV steps matching WorkflowStep.gate (e.g., 'lint', 'typecheck'); NULL "
            "for non-gate steps."
        ),
    )
    timeout_secs: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment=(
            "Per-step timeout override in seconds. NULL = use project default. "
            "Sourced from the manifest's 'timeout' field at registration."
        ),
        doc=(
            "Per-step timeout override in seconds sourced from the manifest; NULL uses the "
            "project default."
        ),
    )
    status: Mapped[StepStatus] = mapped_column(
        _step_status_col,
        nullable=False,
        server_default=text("'pending'"),
        doc=(
            "Current execution status of this step"
            " (StepStatus enum: pending/in_progress/completed/failed/needs_fix/skipped)."
        ),
    )
    prompt_file: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Relative path to the prompt file in the project repo",
        doc="Relative path to the agent prompt markdown file in the project repo.",
    )
    report_file: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Relative path to the report file (latest run)",
        doc="Relative path to the agent report file for the latest run.",
    )
    # Tier 1
    report_content: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment=(
            "Full report markdown (Tier 1 — stored on archive for instant dashboard rendering)"
        ),
        doc=(
            "Full markdown content of the step report stored in-DB for instant dashboard rendering."
        ),
    )
    # Timestamps
    started_at: Mapped[datetime | None] = mapped_column(
        _TIMESTAMPTZ, nullable=True, doc="UTC timestamp when processing started."
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        _TIMESTAMPTZ, nullable=True, doc="UTC timestamp when processing completed."
    )
    # F-00081 — per-step agent+model override (NULL = inherit item/project default)
    agent_runtime_option_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("agent_runtime_options.id", ondelete="RESTRICT"),
        nullable=True,
        comment="Override pair to use for this step; NULL = inherit. F-00081.",
        doc=(
            "FK to agent_runtime_options.id overriding the agent/model for this step;"
            " NULL inherits the item or project default."
        ),
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

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, doc="Primary key identifier."
    )
    step_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="FK to workflow_steps.id — the step this run belongs to.",
    )
    run_number: Mapped[int] = mapped_column(
        Integer, nullable=False, doc="1-based retry counter; first attempt is run_number=1."
    )
    status: Mapped[RunStatus] = mapped_column(
        _run_status_col,
        nullable=False,
        server_default=text("'pending'"),
        doc=(
            "Execution status of this run attempt"
            " (RunStatus enum: pending/running/completed/failed/timeout/killed/stalled)."
        ),
    )
    # Process control
    pid: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="OS process ID of the LLM session (for kill -0 and SIGTERM)",
        doc="OS process ID of the LLM agent session; used for kill -0 health checks and SIGTERM.",
    )
    pid_alive: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
        server_default=text("false"),
        comment="Whether the process is currently alive (set by daemon every poll cycle)",
        doc="Whether the agent process is currently alive; updated by the daemon each poll cycle.",
    )
    command: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Exact shell command used to launch (enables one-click restart)",
        doc=(
            "Exact shell command used to launch the agent; enables one-click restart from the "
            "dashboard."
        ),
    )
    worktree_path: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Full path to the git worktree where the agent runs",
        doc="Absolute filesystem path to the git worktree where the agent process runs.",
    )
    cli_tool: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="LLM CLI tool used: 'opencode', 'claude', or 'pi'",
        doc="LLM CLI tool used for this run (e.g., 'opencode', 'claude', 'pi').",
    )
    last_heartbeat: Mapped[datetime | None] = mapped_column(
        _TIMESTAMPTZ,
        nullable=True,
        comment="Last time daemon confirmed PID was alive (for stall detection)",
        doc="UTC timestamp of the last daemon poll cycle that confirmed the agent PID was alive.",
    )
    timeout_secs: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Dynamic timeout for this step type (not a global constant)",
        doc=(
            "Effective timeout in seconds for this run, derived from step type and manifest "
            "override."
        ),
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Human-readable reason for failure, timeout, or kill",
        doc="Human-readable reason for the failure, timeout, or kill event.",
    )
    # Output
    exit_code: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        doc="Process exit code returned by the agent CLI; NULL while running.",
    )
    log_file: Mapped[str | None] = mapped_column(
        Text, nullable=True, doc="Absolute path to the captured stdout/stderr log file on disk."
    )
    log_content: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Captured log content (ANSI-stripped, truncated) for fast DB access",
        doc="ANSI-stripped, truncated log content stored in-DB for fast dashboard access.",
    )
    session_file: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment=(
            "Absolute path to the pi session .jsonl file for this run. "
            "Set by step_monitor on the first poll cycle after step launch. "
            "NULL for claude/opencode runs and pre-CR-00065 rows. (CR-00065)"
        ),
        doc="Absolute path to the pi session .jsonl file; NULL for claude/opencode runs.",
    )
    context_tokens_peak: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment=(
            "All-time peak totalTokens observed during this run (pi runs only). "
            "Set by step_monitor each poll cycle; never decreases (tracks high-water mark "
            "even across compaction resets). NULL for non-pi runs. (CR-00066)"
        ),
        doc=(
            "All-time peak token count seen during this pi run; never decreases; NULL for non-pi "
            "runs."
        ),
    )
    context_tokens_last: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment=(
            "Most recent totalTokens from the pi session JSONL for this run. "
            "May be lower than context_tokens_peak after a compaction event. "
            "NULL for non-pi runs. (CR-00066)"
        ),
        doc=(
            "Most recent token count from the pi session JSONL; may drop after compaction; NULL "
            "for non-pi runs."
        ),
    )
    report_file: Mapped[str | None] = mapped_column(
        Text, nullable=True, doc="Relative path to the agent-produced report file for this run."
    )
    # Files view — per-step diff (captured at step-done)
    diff_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Raw unified diff captured at iw step-done from the worktree",
        doc="Raw unified diff of changes captured at iw step-done from the worktree.",
    )
    diff_summary: Mapped[Any | None] = mapped_column(
        JSONB,
        nullable=True,
        comment=(
            "Parsed file metadata for this step: list of objects with keys path, "
            "status (A/M/D/R), added, removed, is_generated, is_binary, old_path"
        ),
        doc=(
            "JSONB list of per-file diff metadata objects for this step"
            " (path, status A/M/D/R, added, removed, is_generated, is_binary, old_path)."
        ),
    )
    # Timestamps
    started_at: Mapped[datetime | None] = mapped_column(
        _TIMESTAMPTZ, nullable=True, doc="UTC timestamp when processing started."
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        _TIMESTAMPTZ, nullable=True, doc="UTC timestamp when processing completed."
    )
    duration_secs: Mapped[float | None] = mapped_column(
        Float, nullable=True, doc="Wall-clock duration of this run in seconds; NULL while running."
    )
    warned_50pct_at: Mapped[datetime | None] = mapped_column(
        _TIMESTAMPTZ,
        nullable=True,
        comment=(
            "Set by step_monitor when a one-time 50%-of-timeout warning fires "
            "for this run; suppresses duplicate warns across poll cycles (CR-00024)."
        ),
        doc="UTC timestamp when the 50%-of-timeout warning was fired; NULL until triggered.",
    )
    # F-00081 — records which runtime option was used for this run (append-only, never modified)
    agent_runtime_option_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("agent_runtime_options.id", ondelete="RESTRICT"),
        nullable=True,
        comment="The resolved (cli_tool, model) pair used for this run. F-00081.",
        doc=(
            "FK to agent_runtime_options.id recording the resolved agent/model pair used"
            " for this run; append-only, never modified after creation."
        ),
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
        doc=(
            "Snapshot of the prompt text captured at step launch; append-only, NULL for "
            "pre-CR-00056 rows."
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
        doc="Snapshot of the fix-cycle prompt captured at launch; NULL for non-fix-cycle runs.",
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

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, doc="Primary key identifier."
    )
    step_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="FK to workflow_steps.id — the step that triggered this fix cycle.",
    )
    cycle_number: Mapped[int] = mapped_column(
        Integer, nullable=False, doc="1-based fix attempt counter within the step (max 5)."
    )
    trigger_type: Mapped[FixTrigger] = mapped_column(
        _fix_trigger_col,
        nullable=False,
        doc=(
            "What triggered this fix cycle"
            "(FixTrigger enum: "
            "code_review/code_review_final/quality_validation/browser_verification)."
        ),
    )
    trigger_report: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Path to the review/QV report that triggered this fix cycle",
        doc="Path to the review or QV report file that triggered this fix cycle.",
    )
    fix_prompt: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Path to the generated fix prompt",
        doc="Path to the generated fix-cycle prompt file passed to the agent.",
    )
    fix_report: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Path to the fix agent report",
        doc="Path to the report file produced by the fix agent after completing this cycle.",
    )
    fix_summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment=(
            "Fix agent's 1-3 bullet summary of what changed and why; "
            "NULL for pre-F-00056 cycles or when the agent did not emit a summary"
        ),
        doc="Fix agent's 1–3 bullet prose summary of changes made; NULL when not emitted.",
    )
    status: Mapped[FixStatus] = mapped_column(
        _fix_status_col,
        nullable=False,
        server_default=text("'pending'"),
        doc=(
            "Current status of this fix cycle"
            " (FixStatus enum: pending/in_progress/completed/failed/escalated)."
        ),
    )
    fix_metadata: Mapped[Any] = mapped_column(
        JSONB,
        nullable=True,
        server_default=text("'{}'"),
        comment="Runtime metadata: pid, timeout_secs, log_file, worktree_path",
        doc=(
            "JSONB runtime metadata for this fix cycle (pid, timeout_secs, log_file, "
            "worktree_path)."
        ),
    )
    started_at: Mapped[datetime | None] = mapped_column(
        _TIMESTAMPTZ, nullable=True, doc="UTC timestamp when processing started."
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        _TIMESTAMPTZ, nullable=True, doc="UTC timestamp when processing completed."
    )

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

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, doc="Primary key identifier."
    )
    step_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="FK to workflow_steps.id",
        doc="FK to workflow_steps.id — the step this baseline fingerprint belongs to.",
    )
    gate_name: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Gate identifier matching WorkflowStep.gate (e.g. 'lint', 'unit-tests')",
        doc="Gate identifier matching WorkflowStep.gate for which this baseline was captured.",
    )
    base_sha: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Full git SHA the baseline was computed against (40-char)",
        doc="40-character git SHA of the branch base commit the baseline was computed against.",
    )
    fingerprint: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{\"failures\": []}'"),
        comment="Parser-produced canonical failure set",
        doc="JSONB canonical failure set produced by the gate parser at baseline time.",
    )
    computed_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ,
        nullable=False,
        server_default=func.now(),
        doc="UTC timestamp when this baseline fingerprint was computed.",
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
        doc="Primary key identifier.",
    )
    project_id: Mapped[str] = mapped_column(Text, nullable=False, doc="Owning project identifier.")
    work_item_id: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc=(
            "FK to work_items.id — the work item this evidence belongs to (composite FK with "
            "project_id)."
        ),
    )
    phase: Mapped[EvidencePhase] = mapped_column(
        SAEnum(EvidencePhase, name="evidence_phase", create_type=False),
        nullable=False,
        doc="Lifecycle phase when the evidence was captured (EvidencePhase enum: pre/post).",
    )
    filename: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Original filename of the evidence screenshot or snapshot (e.g., 'screen-001.png').",
    )
    content_type: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="MIME content type of the evidence blob (e.g., 'image/png', 'image/jpeg').",
    )
    content: Mapped[bytes] = mapped_column(
        LargeBinary, nullable=False, doc="Raw binary content of the evidence file stored as a BLOB."
    )
    size_bytes: Mapped[int] = mapped_column(
        Integer, nullable=False, doc="Size in bytes of the stored binary content."
    )
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        doc="UTC timestamp when this evidence was captured and stored.",
    )
    step_id: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc=(
            "Step identifier (e.g., 'S03') that produced this evidence; NULL for pre-step "
            "evidences."
        ),
    )


class Batch(Base):
    """Groups of work items scheduled for parallel execution."""

    __tablename__ = "batches"

    project_id: Mapped[str] = mapped_column(
        Text, primary_key=True, doc="Owning project identifier."
    )
    id: Mapped[str] = mapped_column(Text, primary_key=True, doc="Primary key identifier.")
    status: Mapped[BatchStatus] = mapped_column(
        _batch_status_col,
        nullable=False,
        server_default=text("'planning'"),
        doc=(
            "Current batch lifecycle status (BatchStatus enum:"
            " planning/approved/executing/paused/completed/completed_with_errors"
            "/publishing/published/publish_failed/blocked/archived/cancelled)."
        ),
    )
    max_parallel: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("4"),
        comment="Maximum number of items executing simultaneously",
        doc="Maximum number of batch items that may execute concurrently.",
    )
    cli_tool: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'opencode'"),
        comment="LLM CLI tool used: 'opencode', 'claude', or 'pi'",
        doc="LLM CLI tool selected for this batch (e.g., 'opencode', 'claude', 'pi').",
    )
    auto_publish: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        comment="Whether to auto-push to origin after all items merged",
        doc="Whether to automatically push to origin after all items have been merged.",
    )
    auto_merge: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
        comment="Whether to auto-merge each item to main on success; "
        "false → operator must approve each merge",
        doc="Whether to auto-merge each item to main on success; false requires operator approval.",
    )
    plan_path: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Path to the batch execution plan document (legacy)",
        doc="Legacy path to the batch execution plan document; superseded by execution_plan_md.",
    )
    diagram_path: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Path to the diagram file (legacy)",
        doc="Legacy path to the execution plan diagram file; superseded by execution_plan_drawio.",
    )
    execution_plan_md: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Markdown execution plan with dependency analysis and warnings",
        doc="Markdown execution plan with dependency analysis and scheduling warnings.",
    )
    execution_plan_drawio: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Draw.io XML diagram of the execution plan",
        doc="Draw.io XML source for the execution plan dependency diagram.",
    )
    execution_plan_png: Mapped[bytes | None] = mapped_column(
        LargeBinary,
        nullable=True,
        comment="PNG image of the execution plan diagram",
        doc="PNG image of the execution plan diagram stored as a binary blob.",
    )
    created_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ,
        nullable=False,
        server_default=func.now(),
        doc="UTC timestamp when this row was created.",
    )
    updated_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ,
        nullable=False,
        server_default=func.now(),
        doc="UTC timestamp when this row was last updated.",
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        _TIMESTAMPTZ, nullable=True, doc="UTC timestamp when processing completed."
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        _TIMESTAMPTZ,
        nullable=True,
        comment="Timestamp when the batch was archived",
        doc="UTC timestamp when this batch was archived.",
    )

    __table_args__ = (
        ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        Index("idx_batches_status", "project_id", "status"),
        {"comment": "Groups of work items scheduled for parallel execution"},
    )


class BatchItem(Base):
    """Work items assigned to a batch with execution group and status tracking."""

    __tablename__ = "batch_items"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, doc="Primary key identifier."
    )
    project_id: Mapped[str] = mapped_column(Text, nullable=False, doc="Owning project identifier.")
    batch_id: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="FK to batches.id — the batch this item belongs to (composite FK with project_id).",
    )
    work_item_id: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc=(
            "FK to work_items.id — the work item assigned to this batch slot (composite FK with "
            "project_id)."
        ),
    )
    execution_group: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
        comment="Parallel execution group (0-based). Items in the same group run concurrently.",
        doc=(
            "0-based parallel execution group; items sharing the same group number run "
            "concurrently."
        ),
    )
    status: Mapped[BatchItemStatus] = mapped_column(
        _batch_item_status_col,
        nullable=False,
        server_default=text("'pending'"),
        doc=(
            "Current execution status of this batch item"
            " (BatchItemStatus enum: pending/setting_up/executing/completed"
            "/awaiting_merge_approval/merging/merged/failed/stalled/skipped"
            "/merge_failed/migration_invalid/migration_rolled_back"
            "/migration_rebase_failed/setup_failed)."
        ),
    )
    pid: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        doc="OS process ID of the worktree setup or executor script; NULL when not running.",
    )
    started_at: Mapped[datetime | None] = mapped_column(
        _TIMESTAMPTZ, nullable=True, doc="UTC timestamp when processing started."
    )
    merged_at: Mapped[datetime | None] = mapped_column(
        _TIMESTAMPTZ, nullable=True, doc="UTC timestamp when this item was squash-merged to main."
    )
    notes: Mapped[str | None] = mapped_column(
        Text, nullable=True, doc="Operator or daemon notes about this batch item's execution."
    )
    stall_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        server_default=text("0"),
        doc="Number of consecutive daemon poll cycles this item has been detected as stalled.",
    )
    last_progress: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Last progress message recorded by the daemon for display in the batch status view.",
    )
    worktree_info: Mapped[Any] = mapped_column(
        JSONB,
        nullable=True,
        server_default=text("'{}'"),
        comment="Worktree metadata: path, branch, created_at",
        doc=(
            "JSONB metadata about the git worktree created for this item (path, branch, "
            "created_at)."
        ),
    )
    merge_info: Mapped[Any] = mapped_column(
        JSONB,
        nullable=True,
        server_default=text("'{}'"),
        comment="Merge metadata: commit_hash, conflict_files, merged_by",
        doc="JSONB metadata from the merge operation (commit_hash, conflict_files, merged_by).",
    )
    worktree_db_host: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Hostname or IP of the per-worktree Postgres container; "
        "NULL in legacy mode or when the compose stack has not yet been started.",
        doc=(
            "Hostname or IP of the per-worktree Postgres container;"
            " NULL in legacy mode or before the compose stack starts."
        ),
    )
    worktree_db_port: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Discovered host port for the per-worktree Postgres container; "
        "NULL when the project runs in legacy mode (no iw-config/)",
        doc="Discovered host port for the per-worktree Postgres container; NULL in legacy mode.",
    )
    worktree_db_name: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Database name of the per-worktree Postgres; NULL in legacy mode.",
        doc="Database name used by the per-worktree Postgres container; NULL in legacy mode.",
    )
    worktree_db_user: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Username for the per-worktree Postgres; NULL in legacy mode.",
        doc="Username for connecting to the per-worktree Postgres container; NULL in legacy mode.",
    )
    worktree_db_password: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Password for the per-worktree Postgres; NULL in legacy mode.",
        doc="Password for connecting to the per-worktree Postgres container; NULL in legacy mode.",
    )
    worktree_app_port: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Discovered host port for the per-worktree app server container; "
        "NULL when no app service is declared or in legacy mode",
        doc=(
            "Discovered host port for the per-worktree app server container;"
            " NULL when no app service is declared or in legacy mode."
        ),
    )
    worktree_compose_path: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Absolute filesystem path to the rendered docker-compose-<id>.yml; "
        "NULL in legacy mode. Used by the reaper and daemon-restart re-attach logic.",
        doc=(
            "Absolute path to the rendered docker-compose YAML for this worktree;"
            " NULL in legacy mode."
        ),
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

    project_id: Mapped[str] = mapped_column(
        Text, primary_key=True, doc="Owning project identifier."
    )
    current_holder: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Work item ID holding the lock (NULL = unlocked)",
        doc="Work item ID currently holding the migration lock; NULL means the lock is free.",
    )
    branch: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Git branch name associated with the current lock holder; NULL when unlocked.",
    )
    locked_at: Mapped[datetime | None] = mapped_column(
        _TIMESTAMPTZ,
        nullable=True,
        doc="UTC timestamp when the migration lock was acquired; NULL when unlocked.",
    )
    head_revision: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Alembic head revision at lock time (for conflict detection)",
        doc=(
            "Alembic head revision recorded at lock-acquire time; used for migration conflict "
            "detection."
        ),
    )

    __table_args__ = (
        ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        {"comment": "Exclusive lock per project for Alembic migration creation"},
    )


class BatchOverlapIgnore(Base):
    """Per-batch audit log of operator-ignored file-level overlap pairs.

    Records each (held_item_id, blocking_item_id, file_pattern) triple that the
    operator has chosen to ignore for a given batch. The daemon's overlap
    filter consults this table to exclude ignored pairs so held items can be
    launched. The composite PK enforces per-batch isolation — ignores from
    BATCH-A do not affect BATCH-B even when the same two work items conflict.

    Note: held_item_id and blocking_item_id are work_item.id values (e.g.
    "CR-00072"). They are NOT FKs to work_items because ignore records outlive
    the batch lifecycle and must preserve audit history when archive cleans up.
    """

    __tablename__ = "batch_overlap_ignore"

    project_id: Mapped[str] = mapped_column(
        Text, primary_key=True, doc="Owning project identifier."
    )
    batch_id: Mapped[str] = mapped_column(
        Text,
        primary_key=True,
        doc="FK to batches.id — the batch scope for this ignore record (composite PK).",
    )
    held_item_id: Mapped[str] = mapped_column(
        Text,
        primary_key=True,
        doc=(
            "Work item ID that was held (blocked from launching) due to the overlap (composite PK)."
        ),
    )
    blocking_item_id: Mapped[str] = mapped_column(
        Text,
        primary_key=True,
        doc="Work item ID whose impacted_paths overlapped with held_item_id (composite PK).",
    )
    file_pattern: Mapped[str] = mapped_column(
        Text,
        primary_key=True,
        doc=(
            "Exact file-glob string that caused the overlap, as emitted by scope_overlap "
            "(composite PK)."
        ),
    )

    ignored_by: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Operator identifier; placeholder 'operator' until auth lands",
        doc=(
            "Operator identifier that dismissed the overlap; placeholder 'operator' until auth "
            "lands."
        ),
    )
    ignored_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ,
        nullable=False,
        server_default=func.now(),
        doc="UTC timestamp when the operator dismissed this overlap.",
    )
    reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Optional operator-supplied reason; forward-compat for future CR",
        doc="Optional operator-supplied justification for ignoring this overlap.",
    )

    def __repr__(self) -> str:
        return (
            f"BatchOverlapIgnore("
            f"held={self.held_item_id!r}, blocked_by={self.blocking_item_id!r}, "
            f"file={self.file_pattern!r}, batch={self.batch_id!r})"
        )

    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "batch_id"],
            ["batches.project_id", "batches.id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["project_id", "batch_id", "held_item_id"],
            ["batch_items.project_id", "batch_items.batch_id", "batch_items.work_item_id"],
            ondelete="CASCADE",
        ),
        {
            "comment": (
                "Per-batch audit log of operator-ignored file-level overlap pairs "
                "(CR-00078). Composite PK enforces per-batch isolation. "
                "file_pattern match uses exact string equality with the glob emitted "
                "by scope_overlap.find_blocking_items — no fnmatch normalisation."
            )
        },
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

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, doc="Primary key identifier.")
    instance_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        doc="Stable UUID fingerprint for this orchestration DB instance.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        doc="UTC timestamp when this row was created.",
    )


class DaemonEvent(Base):
    """Audit trail of orchestration events. Append-only. Powers notifications and analytics."""

    __tablename__ = "daemon_events"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, doc="Primary key identifier."
    )
    project_id: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="NULL for system-level events (daemon start/stop, quota warnings)",
        doc="Owning project identifier.",
    )
    event_type: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Event category (see event type catalog)",
        doc="Event category key from the daemon event catalog.",
    )
    entity_id: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Related entity: work item ID, batch ID, or step ID",
        doc="Identifier of the related entity (work item, batch, step, or doc job).",
    )
    entity_type: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Type of entity_id: work_item, batch, step, doc_job, or NULL",
        doc="Entity type for entity_id (work_item, batch, step, doc_job, or NULL).",
    )
    message: Mapped[str | None] = mapped_column(
        Text, nullable=True, doc="Human-readable event summary."
    )
    event_metadata: Mapped[Any] = mapped_column(
        "metadata",
        JSONB,
        nullable=True,
        server_default=text("'{}'"),
        doc="Structured JSON payload with event-specific context fields.",
    )
    created_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ,
        nullable=False,
        server_default=func.now(),
        doc="UTC timestamp when this row was created.",
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

    project_id: Mapped[str] = mapped_column(Text, nullable=False, doc="Owning project identifier.")
    daemon_event_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, doc="FK to daemon_events.id for the reviewed auto-merge event."
    )
    verdict: Mapped[str] = mapped_column(
        Text, nullable=False, doc="Operator verdict (pending, correct, wrong, or partial)."
    )
    verdict_notes: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("''"),
        doc="Operator notes explaining the selected verdict.",
    )
    verdicted_by: Mapped[str | None] = mapped_column(
        Text, nullable=True, doc="Operator identifier that recorded the verdict."
    )
    verdicted_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ,
        nullable=False,
        server_default=func.now(),
        doc="UTC timestamp when the verdict was recorded.",
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

    project_id: Mapped[str] = mapped_column(Text, nullable=False, doc="Owning project identifier.")
    phase: Mapped[int | None] = mapped_column(
        Integer, nullable=True, doc="Auto-merge phase override (0 or 1) for this project."
    )
    runtime_option_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        doc="Optional FK to agent_runtime_options.id overriding the project runtime.",
    )
    updated_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ,
        nullable=False,
        server_default=func.now(),
        doc="UTC timestamp when this row was last updated.",
    )
    updated_by: Mapped[str | None] = mapped_column(
        Text, nullable=True, doc="Operator identifier for the most recent config update."
    )

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

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, doc="Primary key identifier."
    )
    revision: Mapped[str] = mapped_column(
        Text, nullable=False, doc="Alembic revision targeted by this migration phase run."
    )
    old_revision: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Previous down_revision string before the rebase phase rewrote it "
        "(phase='rebase' only)",
        doc="Previous down_revision value before rebase rewriting (phase='rebase' only).",
    )
    direction: Mapped[str] = mapped_column(
        Text, nullable=False, doc="Migration direction enum value (upgrade or downgrade)."
    )
    phase: Mapped[str] = mapped_column(
        Text, nullable=False, doc="Migration pipeline phase (dry_run, apply, rollback, or rebase)."
    )
    batch_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        doc="Optional batch identifier associated with this migration run.",
    )
    started_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ,
        nullable=False,
        server_default=func.now(),
        doc="UTC timestamp when processing started.",
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        _TIMESTAMPTZ, nullable=True, doc="UTC timestamp when processing completed."
    )
    success: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True, doc="True when the migration phase finished successfully."
    )
    stdout_tail: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Trailing portion of the Alembic process stdout captured for diagnosis.",
    )
    stderr_tail: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Trailing portion of the Alembic process stderr captured for diagnosis.",
    )
    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True, doc="Human-readable error message when the migration phase failed."
    )
    created_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ,
        nullable=False,
        server_default=func.now(),
        doc="UTC timestamp when this row was created.",
    )


class TestRun(Base):
    """Test execution runs launched from the dashboard. Append-only."""

    __tablename__ = "test_runs"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, doc="Primary key identifier."
    )
    project_id: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Project that owns this test run",
        doc="Owning project identifier.",
    )
    category: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Test category key (e.g. 'unit', 'integration', 'e2e')",
        doc=(
            "Test suite category key as configured in .iw-orch.json (e.g., 'unit', 'integration', "
            "'e2e')."
        ),
    )
    status: Mapped[TestRunStatus] = mapped_column(
        _test_run_status_col,
        nullable=False,
        server_default=text("'pending'"),
        doc=(
            "Current status of this test run"
            " (TestRunStatus enum: pending/running/passed/failed/cancelled/error)."
        ),
    )
    command: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Shell command executed",
        doc="Shell command that was executed to run this test suite.",
    )
    exit_code: Mapped[int | None] = mapped_column(
        Integer, nullable=True, doc="Process exit code from the test runner; NULL while running."
    )
    started_at: Mapped[datetime | None] = mapped_column(
        _TIMESTAMPTZ, nullable=True, doc="UTC timestamp when processing started."
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        _TIMESTAMPTZ, nullable=True, doc="UTC timestamp when the test run finished (pass or fail)."
    )
    duration_secs: Mapped[float | None] = mapped_column(
        Float, nullable=True, doc="Wall-clock duration of this test run in seconds."
    )
    pid: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="OS process ID (for kill support)",
        doc="OS process ID of the running test subprocess; used for dashboard kill support.",
    )
    log_path: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Absolute path to captured stdout/stderr log",
        doc="Absolute path to the captured stdout/stderr log file for this run.",
    )
    allure_results_dir: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Path to allure-results directory for this run",
        doc="Filesystem path to the allure-results directory produced by this run.",
    )
    allure_report_dir: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Path to generated allure-report directory",
        doc="Filesystem path to the generated Allure HTML report directory.",
    )
    summary: Mapped[Any] = mapped_column(
        JSONB,
        nullable=True,
        comment="Parsed Allure widgets/summary.json content",
        doc="JSONB content of the Allure widgets/summary.json file; NULL before generation.",
    )
    triggered_by: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'user'"),
        comment="Who triggered: user, scheduled",
        doc="What triggered this run: 'user' for dashboard launches, 'scheduled' for cron.",
    )
    run_type: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'test'"),
        comment="Discriminator: test or quality",
        doc="Discriminator for the run kind: 'test' for test suites, 'quality' for quality gates.",
    )
    created_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ,
        nullable=False,
        server_default=func.now(),
        doc="UTC timestamp when this row was created.",
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
        doc="Primary key identifier.",
    )
    project_id: Mapped[str] = mapped_column(Text, nullable=False, doc="Owning project identifier.")
    doc_id: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="User-defined doc identifier within project",
        doc="User-defined document identifier within the project (e.g., 'api', 'architecture').",
    )
    title: Mapped[str] = mapped_column(
        Text, nullable=False, doc="Human-readable document title shown in the docs catalog."
    )
    slug: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="URL-safe slug derived from the title, used in dashboard routes.",
    )
    doc_type: Mapped[DocType] = mapped_column(
        _doc_type_col,
        nullable=False,
        doc=(
            "Document classification (DocType enum:"
            " module/api/architecture/code_components/release_notes/error_catalog"
            "/webhook_ref/user_guide/product_overview/feature_catalog/research/diagram)."
        ),
    )
    tier: Mapped[DocTier] = mapped_column(
        _doc_tier_col,
        nullable=False,
        doc=(
            "Automation tier for this document"
            " (DocTier enum: fully_automated/semi_automated/human_authored)."
        ),
    )
    editorial_category: Mapped[EditorialCategory] = mapped_column(
        _editorial_category_col,
        nullable=False,
        doc=(
            "Editorial category for routing to the correct style guide"
            " (EditorialCategory enum: technical/functional/guide/compliance/marketing/release)."
        ),
    )
    status: Mapped[DocStatus] = mapped_column(
        _doc_status_col,
        nullable=False,
        server_default=text("'planned'"),
        doc=(
            "Publication status of this document (DocStatus enum: "
            "planned/draft/published/archived)."
        ),
    )
    audience: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'"),
        comment="JSONB array of audience strings",
        doc="JSONB array of audience labels for this document (e.g., ['developer', 'ops']).",
    )
    source_paths: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'"),
        comment="JSONB array of source file paths",
        doc="JSONB array of source file paths that feed the doc generator for this document.",
    )
    content: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Tier 1: full markdown content",
        doc="Full markdown content of this document stored in-DB for instant dashboard rendering.",
    )
    content_search: Mapped[str | None] = mapped_column(
        TSVECTOR,
        nullable=True,
        comment="PostgreSQL tsvector for full-text search",
        doc=(
            "PostgreSQL tsvector for full-text search over title + content;"
            " maintained by a BEFORE INSERT OR UPDATE trigger."
        ),
    )
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
        doc="Monotonically increasing version counter incremented on each content update.",
    )
    generated_at: Mapped[datetime | None] = mapped_column(
        _TIMESTAMPTZ,
        nullable=True,
        doc="UTC timestamp of the most recent successful content generation.",
    )
    generated_by: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Generator identifier (e.g., 'skill:iw-doc-generator')",
        doc="Generator identifier that last wrote this document (e.g., 'skill:iw-doc-generator').",
    )
    html_path: Mapped[str | None] = mapped_column(
        Text, nullable=True, doc="Filesystem path to the generated HTML export of this document."
    )
    pdf_path: Mapped[str | None] = mapped_column(
        Text, nullable=True, doc="Filesystem path to the generated PDF export of this document."
    )
    broken_links: Mapped[list[dict[str, str]] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="List of {url, type, status} objects from link validation",
        doc=(
            "JSONB list of broken-link objects ({url, type, status}) from the last link validation."
        ),
    )
    created_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ,
        nullable=False,
        server_default=func.now(),
        doc="UTC timestamp when this row was created.",
    )
    updated_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ,
        nullable=False,
        server_default=func.now(),
        doc="UTC timestamp when this row was last updated.",
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

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, doc="Primary key identifier."
    )
    doc_id: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="FK to project_docs.id",
        doc="FK to project_docs.id — the document this snapshot belongs to.",
    )
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="Version number of this snapshot, matching project_docs.version at capture time.",
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Markdown content snapshot",
        doc="Immutable markdown content snapshot captured at this version.",
    )
    generated_by: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Generator identifier that produced this version (e.g., 'skill:iw-doc-generator').",
    )
    trigger_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="e.g., 'manual', 'batch-merge:B-00042', 'cli:iw doc-update'",
        doc="What caused this version to be created (e.g., 'manual', 'batch-merge:B-00042').",
    )
    created_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ,
        nullable=False,
        server_default=func.now(),
        doc="UTC timestamp when this row was created.",
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
        doc="Primary key identifier.",
    )
    public_id: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Human-readable ID (DOC-00001, DOC-00002, ...). Allocated via id_sequences['DOC'].",
        doc="Human-readable job ID allocated from id_sequences (e.g., 'DOC-00001').",
    )
    project_id: Mapped[str] = mapped_column(Text, nullable=False, doc="Owning project identifier.")
    doc_id: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="FK to project_docs.id; job survives doc deletion",
        doc=(
            "FK to project_docs.id identifying the document to regenerate; SET NULL on doc "
            "deletion."
        ),
    )
    status: Mapped[JobStatus] = mapped_column(
        _job_status_col,
        nullable=False,
        server_default=text("'queued'"),
        doc="Current job status (JobStatus enum: queued/running/completed/failed).",
    )
    requested_at: Mapped[datetime | None] = mapped_column(
        _TIMESTAMPTZ,
        nullable=True,
        doc="UTC timestamp when the regeneration was requested by the operator or trigger.",
    )
    started_at: Mapped[datetime | None] = mapped_column(
        _TIMESTAMPTZ, nullable=True, doc="UTC timestamp when processing started."
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        _TIMESTAMPTZ, nullable=True, doc="UTC timestamp when processing completed."
    )
    agent_output: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Raw agent stdout/result",
        doc="Raw stdout/result captured from the doc-generation agent process.",
    )
    error: Mapped[str | None] = mapped_column(
        Text, nullable=True, doc="Error message when the job failed; NULL on success."
    )
    agent_pid: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        doc="OS process ID of the doc-generation agent; NULL when not running.",
    )
    skill_used: Mapped[str | None] = mapped_column(
        Text, nullable=True, doc="Skill identifier invoked for this job (e.g., 'iw-doc-generator')."
    )
    trigger_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Why the job was created (e.g., 'batch-merge:B-00042:F-00013')",
        doc="Reason this job was created (e.g., 'manual', 'batch-merge:B-00042:F-00013').",
    )
    lint_warnings: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="List of lint warning objects {rule, message, section}",
        doc=(
            "JSONB list of editorial lint warning objects ({rule, message, section}) from "
            "post-generation checks."
        ),
    )
    report: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment=(
            "Structured post-mortem of the job: outcome, duration_seconds, "
            "skill_used, cli_tool, command_issued, log_size_bytes, log_line_count, "
            "tool_calls, doc_update_invocations, lint_warning_count, diagnosis."
        ),
        doc=(
            "JSONB post-mortem report of the job (outcome, timing, tool calls, lint counts, "
            "diagnosis)."
        ),
    )
    duration_seconds: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        doc="Wall-clock duration of the doc-generation agent run in seconds.",
    )
    section_guides_snapshot: Mapped[dict[str, str] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Section guides snapshotted at job creation: {section_name: guide_md, ...}.",
        doc="JSONB snapshot of section guides at job creation time ({section_name: guide_md}).",
    )
    guide_snapshot: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Guide content snapshotted at job creation time for audit purposes.",
        doc=(
            "Snapshot of the doc-type or instance guide markdown captured at job creation for "
            "audit."
        ),
    )
    created_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ,
        nullable=False,
        server_default=func.now(),
        doc="UTC timestamp when this row was created.",
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
        doc=(
            "DocType value this guide applies to (e.g., 'api', 'module'); PK and FK to DocType "
            "enum."
        ),
    )
    guide_md: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Markdown editorial guideline text for this doc type; injected into the agent prompt.",
    )
    updated_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        doc="UTC timestamp when this row was last updated.",
    )

    __table_args__ = {"comment": "Editable editorial guideline per DocType"}


class DocInstanceGuide(Base):
    """Instance-level guide override for a specific ProjectDoc."""

    __tablename__ = "doc_instance_guides"

    doc_id: Mapped[str] = mapped_column(
        Text,
        primary_key=True,
        comment="FK to project_docs.id",
        doc="FK to project_docs.id — the specific document this guide overrides; PK.",
    )
    guide_md: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc=(
            "Markdown editorial guideline text overriding the type-level default for this document."
        ),
    )
    updated_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        doc="UTC timestamp when this row was last updated.",
    )

    __table_args__ = (
        ForeignKeyConstraint(["doc_id"], ["project_docs.id"], ondelete="CASCADE"),
        {"comment": "Instance-level guide override for a specific ProjectDoc"},
    )


class DocSectionGuide(Base):
    """Per-section editorial guidelines, keyed by (doc_id, section_name)."""

    __tablename__ = "doc_section_guides"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, doc="Primary key identifier."
    )
    doc_id: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="FK to project_docs.id (composite: project_id:doc_id).",
        doc="FK to project_docs.id — the document this section guide belongs to.",
    )
    section_name: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="H2 heading text, or 'Document' if no H2 headings exist.",
        doc="H2 heading name of the section this guide covers, or 'Document' for whole-doc guides.",
    )
    guide_md: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Markdown editorial guidelines for this specific section.",
        doc="Markdown editorial guidelines for this section; injected into the agent prompt.",
    )
    updated_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="Timestamp of last guide edit.",
        doc="UTC timestamp when this row was last updated.",
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
        doc="Primary key identifier.",
    )
    public_id: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Human-readable ID (CM-00001, CM-00002, ...). Allocated via id_sequences['CM'].",
        doc="Human-readable job ID allocated from id_sequences (e.g., 'CM-00001').",
    )
    project_id: Mapped[str] = mapped_column(
        Text, nullable=False, comment="FK to projects(id)", doc="Owning project identifier."
    )
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'queued'"),
        comment="queued|running|completed|failed|cancelled",
        doc="Current job status (one of: queued, running, completed, failed, cancelled).",
    )
    provider: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'local'"),
        comment="Index provider: local (only value in v1)",
        doc="Code index provider used for this job (currently always 'local' for LanceDB).",
    )
    llm_model: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="LLM model name; None = use tier default",
        doc="LLM model name override for code summarisation; NULL uses the index tier default.",
    )
    embed_model: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Embedding model name; None = use tier default",
        doc="Embedding model name override; NULL uses the index tier default.",
    )
    index_tier: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="fast|balanced|quality",
        doc="Index quality tier controlling speed vs. accuracy trade-off (fast/balanced/quality).",
    )
    files_discovered: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
        comment="Total files found",
        doc="Total number of source files discovered during this indexing job.",
    )
    files_indexed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
        comment="Files successfully indexed",
        doc="Number of source files successfully indexed into LanceDB.",
    )
    chunks_created: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
        comment="Total chunks produced",
        doc="Total number of code chunks produced and stored in LanceDB.",
    )
    languages_detected: Mapped[Any] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'"),
        comment="List of detected language names",
        doc="JSONB array of programming language names detected in the indexed files.",
    )
    errors: Mapped[Any] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'"),
        comment="List of error messages",
        doc="JSONB array of error message strings collected during indexing.",
    )
    doc_id: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="FK to project_docs(id); nullable, SET NULL on delete",
        doc=(
            "FK to project_docs.id for the associated code-understanding doc; SET NULL on doc "
            "deletion."
        ),
    )
    triggered_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ,
        nullable=False,
        server_default=func.now(),
        comment="When the job was triggered",
        doc="UTC timestamp when this indexing job was enqueued.",
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        _TIMESTAMPTZ,
        nullable=True,
        comment="When the job finished (success or failure)",
        doc="UTC timestamp when processing completed.",
    )
    created_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ,
        nullable=False,
        server_default=func.now(),
        doc="UTC timestamp when this row was created.",
    )
    updated_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ,
        nullable=False,
        server_default=func.now(),
        doc="UTC timestamp when this row was last updated.",
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
        doc="Primary key identifier.",
    )
    project_id: Mapped[str] = mapped_column(
        Text, nullable=False, comment="FK to projects(id)", doc="Owning project identifier."
    )
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'queued'"),
        comment="queued|running|completed|failed|cancelled",
        doc="Current lifecycle status.",
    )
    provider: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'local'"),
        comment="Index provider: local (only value in v1)",
        doc="Doc index provider (currently always 'local' for LanceDB).",
    )
    llm_model: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="LLM model name; None = use tier default",
        doc="LLM model name override for doc summarisation; NULL uses the index tier default.",
    )
    embed_model: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Embedding model name; None = use tier default",
        doc="Embedding model name override for doc indexing; NULL uses the index tier default.",
    )
    index_tier: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="fast|balanced|quality",
        doc="Index quality tier controlling speed vs. accuracy trade-off (fast/balanced/quality).",
    )
    items_discovered: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
        comment="Total items found",
        doc="Total number of project doc items discovered for indexing.",
    )
    items_indexed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
        comment="Items successfully indexed",
        doc="Number of project doc items successfully indexed into LanceDB.",
    )
    chunks_created: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
        comment="Total chunks produced",
        doc="Total number of doc chunks produced and stored in LanceDB.",
    )
    errors: Mapped[Any] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'"),
        comment="List of error messages",
        doc="JSONB array of error message strings collected during doc indexing.",
    )
    triggered_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ,
        nullable=False,
        server_default=func.now(),
        comment="When the job was triggered",
        doc="UTC timestamp when this doc indexing job was enqueued.",
    )
    started_at: Mapped[datetime | None] = mapped_column(
        _TIMESTAMPTZ,
        nullable=True,
        comment="When the job started",
        doc="UTC timestamp when processing started.",
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        _TIMESTAMPTZ,
        nullable=True,
        comment="When the job finished (success or failure)",
        doc="UTC timestamp when processing completed.",
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Error message if status='failed'",
        doc="Human-readable error message when status='failed'; NULL on success.",
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

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, doc="Primary key identifier."
    )
    project_id: Mapped[str] = mapped_column(Text, nullable=False, doc="Owning project identifier.")
    started_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ,
        nullable=False,
        server_default=func.now(),
        doc="UTC timestamp when processing started.",
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        _TIMESTAMPTZ, nullable=True, doc="UTC timestamp when processing completed."
    )
    status: Mapped[OssScanStatus] = mapped_column(
        _oss_scan_status_col,
        nullable=False,
        default=OssScanStatus.pending,
        doc="Current lifecycle status.",
    )
    mode: Mapped[OssScanMode] = mapped_column(
        _oss_scan_mode_col,
        nullable=False,
        default=OssScanMode.scan,
        doc="Scan operation mode (OssScanMode enum: scan); reserved for future install/fix modes.",
    )
    exit_code: Mapped[int | None] = mapped_column(
        Integer, nullable=True, doc="Exit code from the OSS scan tool process; NULL while running."
    )
    head_sha: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Git HEAD SHA at scan start",
        doc="Git HEAD SHA recorded at the start of the scan; NULL when not captured.",
    )
    pill_color: Mapped[OssPillColor | None] = mapped_column(
        _oss_pill_color_col,
        nullable=True,
        doc=(
            "Dashboard badge colour summarising the scan result (OssPillColor enum: "
            "green/yellow/red/gray)."
        ),
    )
    summary_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Counts-by-severity summary",
        doc=(
            "JSONB counts-by-severity summary produced after the scan completes; NULL while "
            "pending."
        ),
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Error message if status='error'",
        doc="Human-readable error detail when status='error'; NULL on success.",
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

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, doc="Primary key identifier."
    )
    scan_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, doc="FK to oss_scan.id — the scan that produced this finding."
    )
    check_id: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Check identifier (e.g., OSS-LIC-01)",
        doc="OSS policy check identifier (e.g., 'OSS-LIC-01', 'OSS-SEC-02').",
    )
    severity: Mapped[OssFindingSeverity] = mapped_column(
        _oss_finding_severity_col,
        nullable=False,
        doc="Finding severity level (OssFindingSeverity enum: MUST/SHOULD/MAY/INFO).",
    )
    status: Mapped[OssFindingStatus] = mapped_column(
        _oss_finding_status_col,
        nullable=False,
        doc="Finding result status (OssFindingStatus enum: pass/fail/skip/human_required).",
    )
    domain: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="license, secrets, etc.",
        doc="Compliance domain this finding covers (e.g., 'license', 'secrets', 'sast').",
    )
    summary: Mapped[str] = mapped_column(
        Text, nullable=False, doc="One-line human-readable summary of this OSS finding."
    )
    detail: Mapped[str | None] = mapped_column(
        Text, nullable=True, doc="Extended detail explaining the finding; NULL when not applicable."
    )
    remediation: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Recommended remediation steps for this finding; NULL when none defined.",
    )
    auto_fix_available: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        doc="Whether an automated fix script exists for this finding.",
    )
    auto_apply_safe: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        doc="Whether the automated fix is safe to apply without human review.",
    )
    osps_control: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="OSPS control reference",
        doc=(
            "OSPS (Open Source Project Security) control reference identifier; NULL when not "
            "mapped."
        ),
    )
    tool: Mapped[str | None] = mapped_column(
        Text, nullable=True, doc="Name of the tool that produced this finding (e.g., 'gitleaks')."
    )
    evidence_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        doc="JSONB evidence payload with tool-specific raw output details for this finding.",
    )
    rationale: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Per-check rationale paragraph",
        doc="Prose rationale paragraph explaining why this check passed or failed.",
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

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, doc="Primary key identifier."
    )
    scan_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, doc="FK to oss_scan.id — the scan this tool run belongs to."
    )
    tool: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Name of the OSS tool that was executed (e.g., 'gitleaks', 'trivy').",
    )
    version: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Version string of the tool that was executed; NULL when not captured.",
    )
    status: Mapped[OssToolRunStatus] = mapped_column(
        _oss_tool_run_status_col,
        nullable=False,
        doc="Execution result of this tool run (OssToolRunStatus enum: ok/failed/missing/skipped).",
    )
    started_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ, nullable=False, doc="UTC timestamp when processing started."
    )
    runtime_ms: Mapped[int | None] = mapped_column(
        Integer, nullable=True, doc="Wall-clock execution time of this tool run in milliseconds."
    )
    exit_code: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        doc="Exit code returned by the tool process; NULL when not applicable.",
    )
    output_summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="First 2KB of stdout/stderr",
        doc="First 2 KB of the tool's combined stdout/stderr captured for quick diagnosis.",
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

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, doc="Primary key identifier."
    )
    finding_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        doc="FK to oss_finding.id — the parent finding this detail row belongs to.",
    )
    ordinal: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Stable order from the source SARIF",
        doc="0-based ordinal from the source SARIF result list; used for stable pagination order.",
    )
    file_path: Mapped[str] = mapped_column(
        Text, nullable=False, doc="Repository-relative file path where this finding was detected."
    )
    line_number: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        doc="1-based line number of the finding in the file; NULL when not applicable.",
    )
    rule_id: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Tool rule identifier that triggered this finding (e.g., 'generic-api-key').",
    )
    snippet_masked: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Secret value with middle bytes redacted",
        doc=(
            "Secret value snippet with middle bytes redacted for safe display; NULL for "
            "non-secret findings."
        ),
    )
    created_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ,
        nullable=False,
        server_default=func.now(),
        doc="UTC timestamp when this row was created.",
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

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, doc="Primary key identifier."
    )
    public_id: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Human-readable ID (O-00001, O-00002, ...). Allocated via id_sequences['O'].",
        doc=(
            "Human-readable identifier allocated from id_sequences['O'] "
            "(e.g., 'O-00001'); unique across all OSS jobs."
        ),
    )
    project_id: Mapped[str] = mapped_column(Text, nullable=False, doc="Owning project identifier.")
    kind: Mapped[ProjectOssJobKind] = mapped_column(
        _project_oss_job_kind_col,
        nullable=False,
        doc="Job type (ProjectOssJobKind enum: scan/install/fix).",
    )
    status: Mapped[ProjectOssJobStatus] = mapped_column(
        _project_oss_job_status_col,
        nullable=False,
        server_default=text("'queued'"),
        doc="Current lifecycle status.",
    )
    created_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ,
        nullable=False,
        server_default=func.now(),
        doc="UTC timestamp when this row was created.",
    )
    started_at: Mapped[datetime | None] = mapped_column(
        _TIMESTAMPTZ, nullable=True, doc="UTC timestamp when processing started."
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        _TIMESTAMPTZ, nullable=True, doc="UTC timestamp when processing completed."
    )
    exit_code: Mapped[int | None] = mapped_column(
        Integer, nullable=True, doc="Exit code from the OSS job process; NULL while running."
    )
    scan_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        comment="FK to oss_scan.id when kind=scan; NULL otherwise",
        doc="FK to oss_scan.id — the scan produced by this job when kind='scan'; NULL otherwise.",
    )
    stdout_tail: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Last 16KB of combined stdout/stderr",
        doc="Last 16 KB of combined stdout/stderr from the job process for quick diagnosis.",
    )
    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True, doc="Human-readable error detail when status='error'; NULL on success."
    )
    base_sha: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Git HEAD SHA when the job was fired",
        doc="Git HEAD SHA recorded when the job was enqueued; NULL when not captured.",
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

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, doc="Primary key identifier."
    )  # always 1
    model: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="claude-sonnet-4-6",
        doc="Model identifier used for keep-alive LLM calls (e.g., 'claude-sonnet-4-6').",
    )
    window_duration_hours: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=5,
        doc="Width of the keep-alive scheduling window in hours (default 5).",
    )
    updated_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        doc="UTC timestamp when this row was last updated.",
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

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, doc="Primary key identifier."
    )
    time_hhmm: Mapped[str] = mapped_column(
        String(5), nullable=False, doc="Scheduled keep-alive time in 'HH:MM' 24-hour format."
    )  # "HH:MM"
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, doc="Whether this time slot is active and will fire."
    )
    created_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ,
        nullable=False,
        server_default=func.now(),
        doc="UTC timestamp when this row was created.",
    )

    config_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("keep_alive_config.id", ondelete="CASCADE"),
        nullable=False,
        default=1,
        doc="FK to keep_alive_config.id — always 1 (singleton global config).",
    )
    config: Mapped["KeepAliveConfig"] = relationship("KeepAliveConfig", back_populates="slots")
    runs: Mapped[list["KeepAliveRun"]] = relationship(
        "KeepAliveRun", back_populates="slot", passive_deletes=True
    )


class KeepAliveRun(Base):
    """Execution log for keep-alive firings."""

    __tablename__ = "keep_alive_runs"
    __table_args__ = {"comment": "Execution log for keep-alive firings"}

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, doc="Primary key identifier."
    )
    slot_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("keep_alive_slots.id", ondelete="SET NULL"),
        nullable=True,
        doc=(
            "FK to keep_alive_slots.id — the slot that triggered this run; NULL if slot was "
            "deleted."
        ),
    )
    slot_time: Mapped[str] = mapped_column(
        String(5),
        nullable=False,
        comment="Snapshot of 'HH:MM' at fire time",
        doc="Snapshot of the slot's 'HH:MM' time captured when the run was fired.",
    )
    fired_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ,
        nullable=False,
        server_default=func.now(),
        doc="UTC timestamp when the keep-alive run was triggered.",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="success|failed|retried_success|retried_failed",
        doc="Current lifecycle status.",
    )
    error: Mapped[str | None] = mapped_column(
        Text, nullable=True, doc="Error detail when the keep-alive run failed; NULL on success."
    )

    # I-00112 — CLI output capture for diagnostic audit of silent no-op fires.
    # All nullable so existing rows survive the migration with NULL (no backfill).
    stdout: Mapped[str | None] = mapped_column(
        Text, nullable=True, doc="Captured standard output from the keep-alive CLI invocation."
    )
    stderr: Mapped[str | None] = mapped_column(
        Text, nullable=True, doc="Captured standard error from the keep-alive CLI invocation."
    )
    elapsed_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        doc="Wall-clock duration of the keep-alive invocation in milliseconds.",
    )
    returncode: Mapped[int | None] = mapped_column(
        Integer, nullable=True, doc="Process return code from the keep-alive CLI invocation."
    )

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
        doc="Primary key identifier.",
    )
    project_id: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="FK to projects(id); app-layer enforcement of project scoping",
        doc="Owning project identifier.",
    )
    session_id: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Browser session cookie (iw_chat_session) — scoped to (project_id, session_id)",
        doc=(
            "Browser session cookie value (iw_chat_session) that owns this conversation, "
            "scoped together with project_id."
        ),
    )
    module_path: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Snapshot of module_path from the first turn; NULL for architecture-level chats",
        doc=(
            "Snapshot of the module path from the first turn; NULL for architecture-level chats "
            "that are not anchored to a specific module."
        ),
    )
    context_level: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'architecture'"),
        comment="architecture | module — snapshot from first turn",
        doc="Chat context level snapshotted from the first turn: 'architecture' or 'module'.",
    )
    title: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="First user question, truncated to 80 chars; NULL until first message persists",
        doc=(
            "Conversation title derived from the first user question, truncated to 80 chars; "
            "NULL until the first message is persisted."
        ),
    )
    rolling_summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Compact prose summary produced by ChatSummarizationJob; prepended to LLM history",
        doc=(
            "Running LLM-generated summary of the conversation so far, produced by "
            "ChatSummarizationJob and prepended to the LLM context on each new turn."
        ),
    )
    summary_through_message_id: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="FK to chat_messages.id — last message included in rolling_summary",
        doc=(
            "FK to chat_messages.id — the last message included in rolling_summary; "
            "NULL until the first summarisation job completes."
        ),
    )
    created_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ,
        nullable=False,
        server_default=func.now(),
        comment="When the conversation row was created",
        doc="UTC timestamp when this row was created.",
    )
    last_active_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ,
        nullable=False,
        server_default=func.now(),
        comment="Updated on every new assistant message",
        doc=(
            "UTC timestamp updated on every new assistant message; used to sort recent "
            "conversations."
        ),
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        _TIMESTAMPTZ,
        nullable=True,
        comment="Soft-delete timestamp; NULL means active",
        doc="UTC soft-delete timestamp set when the conversation is archived; NULL means active.",
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
        doc="Primary key identifier.",
    )
    conversation_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("chat_conversations.id", ondelete="CASCADE"),
        nullable=False,
        comment="FK to chat_conversations.id",
        doc="FK to chat_conversations.id — the conversation this message belongs to.",
    )
    role: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="chat_message_role ENUM: user | assistant | system",
        doc="Message author role: 'user', 'assistant', or 'system'.",
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Message text; no upper bound — caller validates size",
        doc="Full text content of the message; size validated by the caller before insert.",
    )
    token_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
        comment="Token count via tiktoken (or len(content)//4 heuristic); set at insert, never updated",  # noqa: E501,
        doc=(
            "Estimated token count set at insert time via tiktoken "
            "(or len(content)//4 heuristic); never updated."
        ),
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
        doc=(
            "JSONB bag for per-message metadata (DB column name: 'metadata'); "
            "may carry {'error': true} when the stream was disconnected mid-response."
        ),
    )
    created_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ,
        nullable=False,
        server_default=func.now(),
        comment="When the message row was inserted",
        doc="UTC timestamp when this row was created.",
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
        doc="Primary key identifier.",
    )
    conversation_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("chat_conversations.id", ondelete="CASCADE"),
        nullable=False,
        comment="FK to chat_conversations.id",
        doc=(
            "FK to chat_conversations.id — the conversation whose rolling_summary this job updates."
        ),
    )
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'queued'"),
        comment="queued | running | completed | failed | cancelled",
        doc="Current lifecycle status.",
    )
    messages_summarized: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
        comment="Number of messages summarised into rolling_summary",
        doc="Count of messages summarised into rolling_summary by this job run.",
    )
    summary_through_message_id: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="FK to chat_messages.id — last message included in the summary",
        doc=(
            "FK to chat_messages.id — the last message included in the rolling summary "
            "produced by this job."
        ),
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Error detail when status=failed",
        doc="Human-readable error detail when status='failed'; NULL on success.",
    )
    triggered_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ,
        nullable=False,
        server_default=func.now(),
        comment="When the job was enqueued (hard budget overflow detected)",
        doc=(
            "UTC timestamp when the job was enqueued, typically after a hard token-budget overflow."
        ),
    )
    started_at: Mapped[datetime | None] = mapped_column(
        _TIMESTAMPTZ,
        nullable=True,
        comment="When the daemon picked up the job",
        doc="UTC timestamp when processing started.",
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        _TIMESTAMPTZ,
        nullable=True,
        comment="When the job finished (success or failure)",
        doc="UTC timestamp when processing completed.",
    )
    created_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ,
        nullable=False,
        server_default=func.now(),
        doc="UTC timestamp when this row was created.",
    )
    updated_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ,
        nullable=False,
        server_default=func.now(),
        doc="UTC timestamp when this row was last updated.",
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
        doc="Primary key identifier.",
    )
    title: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'New chat'"),
        comment="Tab title shown in the strip; user-editable",
        doc="User-editable tab title displayed in the chat strip (default 'New chat').",
    )
    runtime: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'opencode'"),
        comment="Chat runtime: 'opencode' today; 'pi' added by F-B",
        doc=(
            "Chat backend runtime identifier (e.g., 'opencode'); allowlist enforced in tab_service."
        ),
    )
    model: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Model identifier scoped to runtime (e.g., 'anthropic/claude-sonnet-4-7')",
        doc="Model identifier scoped to the chosen runtime (e.g., 'anthropic/claude-sonnet-4-7').",
    )
    project_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        comment="FK to projects.id; deleting a project cascades to its tabs",
        doc="Owning project identifier.",
    )
    opencode_session_id: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="OpenCode session id; populated after first session create",
        doc=(
            "OpenCode session identifier populated after the first session is created; "
            "NULL until then, preserved on close for reopen support."
        ),
    )
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'active'"),
        comment="Tab status: 'active' or 'closed' (soft-delete)",
        doc="Current lifecycle status.",
    )
    created_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ,
        nullable=False,
        server_default=func.now(),
        doc="UTC timestamp when this row was created.",
    )
    updated_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ,
        nullable=False,
        server_default=func.now(),
        doc="UTC timestamp when this row was last updated.",
    )
    last_active_at: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ,
        nullable=False,
        server_default=func.now(),
        doc=(
            "UTC timestamp of the most recent interaction with this tab; drives the strip sort "
            "order."
        ),
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        _TIMESTAMPTZ,
        nullable=True,
        comment="When the tab was soft-deleted; NULL when active",
        doc=(
            "UTC soft-delete timestamp set when the tab is closed (status='closed'); NULL when "
            "active."
        ),
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


class TestHealthSnapshot(Base):
    """Time-series snapshots of test-health metrics for a project.

    One row per (project_id, metric, ts) — stores numeric values from
    the four headline test-health signals: mutation_score, coverage_pct,
    flaky_test_count, and assertion_baseline_size. The ``meta`` JSONB
    column carries per-run context (commit SHA, run ID, raw counts) so the
    dashboard can display a tooltip without a second query.

    CR-00086.
    """

    __tablename__ = "test_health_snapshots"
    __table_args__ = (
        ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        Index(
            "ix_test_health_snapshots_project_metric_ts",
            "project_id",
            "metric",
            text("ts DESC"),
        ),
        {"comment": "Time-series test-health metric snapshots (CR-00086)"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="Auto-incrementing primary key",
        doc="Primary key identifier.",
    )
    project_id: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="FK to projects.id; cascades on project deletion",
        doc="Owning project identifier.",
    )
    ts: Mapped[datetime] = mapped_column(
        _TIMESTAMPTZ,
        nullable=False,
        server_default=func.now(),
        comment="UTC timestamp of this snapshot (truncated to minute for idempotency)",
        doc="UTC timestamp of this snapshot, truncated to the minute for idempotent upserts.",
    )
    metric: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment=(
            "Metric name: 'mutation_score', 'coverage_pct', "
            "'flaky_test_count', or 'assertion_baseline_size'"
        ),
        doc=(
            "Name of the captured test-health metric: 'mutation_score', 'coverage_pct', "
            "'flaky_test_count', or 'assertion_baseline_size'."
        ),
    )
    value: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Numeric value of the metric at snapshot time",
        doc="Numeric value of the metric at this snapshot timestamp.",
    )
    meta: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'"),
        comment=(
            "Run metadata: commit_sha, run_id, source_path, raw_counts, etc. "
            "Empty object when no additional context is available."
        ),
        doc=(
            "JSONB bag of per-run context (commit_sha, run_id, source_path, raw_counts, etc.) "
            "for dashboard tooltips; empty object when no additional context is available."
        ),
    )

    project: Mapped["Project"] = relationship("Project")
