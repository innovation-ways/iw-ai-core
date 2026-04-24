"""Work item detail page and htmx tab fragment routes."""

from __future__ import annotations

import mimetypes
from dataclasses import dataclass, field
from datetime import UTC
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from sqlalchemy import select

from dashboard.dependencies import get_db
from dashboard.utils.markdown import render_markdown
from orch.daemon.execution_report import assemble_execution_report
from orch.db.models import (
    BatchItem,
    BatchItemStatus,
    EvidencePhase,
    FixCycle,
    Project,
    StepRun,
    WorkflowStep,
    WorkItem,
    WorkItemEvidence,
)

if TYPE_CHECKING:
    from datetime import datetime

    from fastapi.templating import Jinja2Templates
    from sqlalchemy.orm import Session


router = APIRouter(prefix="/project/{project_id}")


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------


@dataclass
class StepDetail:
    """Full step info for the item overview tab."""

    step_id: str
    agent_label: str
    step_type: str
    status: str
    duration_secs: float | None
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None
    run_count: int
    step_label: str | None = None
    description: str | None = None
    report_content: str | None = None
    is_synthetic: bool = False
    fix_cycle_count: int = 0


@dataclass
class ReportSection:
    """A rendered report for a single step, used in the reports tab."""

    step_id: str
    agent_label: str
    step_type: str
    status: str
    run_count: int
    report_html: str


@dataclass
class RunLog:
    """A single step_run entry for the logs tab."""

    run_number: int
    status: str
    duration_secs: float | None
    is_running: bool
    log_content: str | None
    log_modified: str | None = None


@dataclass
class LogSection:
    """All runs for a single workflow step, for the logs tab."""

    step_id: str
    agent_label: str
    status: str
    db_step_id: int | None
    runs: list[RunLog]
    static_content: str | None = None


@dataclass
class ArtifactNode:
    """One node in the artifact file tree."""

    name: str  # filename or directory name
    abs_path: str  # absolute path on disk (for reading)
    rel_path: str  # path relative to artifact root (used in /artifact-raw URL param)
    is_dir: bool
    size_bytes: int  # 0 for directories
    file_type: str  # "markdown" | "image" | "text" | "binary" | "directory"
    children: list[ArtifactNode] = field(default_factory=list)


def _detect_file_type(name: str) -> str:
    """Map a filename to a viewer content type."""
    name_lower = name.lower()
    if name_lower.endswith(".md"):
        return "markdown"
    image_exts = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")
    if any(name_lower.endswith(e) for e in image_exts):
        return "image"
    text_exts = (
        ".txt",
        ".log",
        ".json",
        ".yaml",
        ".yml",
        ".sh",
        ".py",
        ".toml",
        ".cfg",
        ".ini",
        ".sql",
        ".html",
        ".css",
        ".js",
        ".ts",
        ".xml",
        ".env",
    )
    if any(name_lower.endswith(e) for e in text_exts):
        return "text"
    return "binary"


def _resolve_artifact_root(
    item: WorkItem, project: Project, worktree_path: str | None
) -> Path | None:
    """Return the first existing candidate path for the artifact directory.

    Worktree is preferred; falls back to repo_root. Returns None if neither
    exists or if item.design_doc_path is None.
    """
    if item.design_doc_path is None:
        return None
    rel_dir = Path(item.design_doc_path).parent
    candidates: list[Path] = []
    if worktree_path:
        candidates.append(Path(worktree_path) / rel_dir)
    candidates.append(Path(project.repo_root) / rel_dir)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _build_artifact_tree(directory: Path, root: Path) -> list[ArtifactNode]:
    """Recursively build the artifact tree starting at *directory*.

    *root* is used to compute rel_path for each node.
    Sort order: directories first (alphabetical), then files (alphabetical).
    """
    nodes: list[ArtifactNode] = []
    try:
        entries = list(directory.iterdir())
    except OSError:
        return nodes
    dirs = sorted([e for e in entries if e.is_dir()], key=lambda e: e.name.lower())
    files = sorted([e for e in entries if e.is_file()], key=lambda e: e.name.lower())
    for entry in dirs + files:
        rel = str(entry.relative_to(root))
        if entry.is_dir():
            children = _build_artifact_tree(entry, root)
            nodes.append(
                ArtifactNode(
                    name=entry.name,
                    abs_path=str(entry),
                    rel_path=rel,
                    is_dir=True,
                    size_bytes=0,
                    file_type="directory",
                    children=children,
                )
            )
        else:
            nodes.append(
                ArtifactNode(
                    name=entry.name,
                    abs_path=str(entry),
                    rel_path=rel,
                    is_dir=False,
                    size_bytes=entry.stat().st_size,
                    file_type=_detect_file_type(entry.name),
                )
            )
    return nodes


def _list_artifact_tree(
    _project_id: str, item: WorkItem, project: Project, worktree_path: str | None = None
) -> list[ArtifactNode]:
    """Build the artifact tree for *item*, preferring worktree paths."""
    root = _resolve_artifact_root(item, project, worktree_path)
    if root is None:
        return []
    return _build_artifact_tree(root, root)


@dataclass
class EvidenceFile:
    """A single screenshot/snapshot in the evidences browser."""

    filename: str
    phase: str  # "pre" or "post"
    abs_path: str  # populated from FS only when not in DB
    size_bytes: int
    content: bytes | None = None  # populated from DB
    content_type: str | None = None  # populated from DB


@dataclass
class ItemMetrics:
    """Computed metrics for the item detail header."""

    total_duration_secs: float | None
    fix_cycles_count: int
    steps_completed: int
    steps_total: int


@dataclass
class FixCycleDetail:
    """A single fix cycle record for the fix-cycles tab."""

    id: int
    db_step_id: int
    step_id: str
    agent_label: str
    cycle_number: int
    trigger_type: str
    status: str
    started_at: datetime | None
    completed_at: datetime | None
    duration_secs: float | None
    log_content: str | None
    log_modified: str | None
    is_running: bool


# ---------------------------------------------------------------------------
# Duration aggregation helpers
# ---------------------------------------------------------------------------


def _aggregate_step_spans(
    db: Session, step_db_ids: list[int]
) -> dict[int, tuple[datetime | None, datetime | None]]:
    """Aggregate step spans from append-only step_runs and fix_cycles tables.

    I-00034: WorkflowStep.started_at/completed_at reflect only the LAST iteration
    (daemon resets them on retry/fix-cycle). Aggregate from append-only step_runs ∪ fix_cycles.
    Returns dict mapping step_id -> (earliest_started, latest_completed).
    Only steps with at least one completed row are included.
    """
    from sqlalchemy import func

    spans: dict[int, tuple[datetime | None, datetime | None]] = {}

    from sqlalchemy import case

    run_rows = db.execute(
        select(
            StepRun.step_id,
            func.min(StepRun.started_at).label("earliest"),
            case(
                (func.count(StepRun.completed_at) < func.count(StepRun.id), None),
                else_=func.max(StepRun.completed_at),
            ).label("latest"),
        )
        .where(StepRun.step_id.in_(step_db_ids))
        .group_by(StepRun.step_id)
    ).all()
    for row in run_rows:
        spans[row.step_id] = (row.earliest, row.latest)

    cycle_rows = db.execute(
        select(
            FixCycle.step_id,
            func.min(FixCycle.started_at).label("earliest"),
            case(
                (func.count(FixCycle.completed_at) < func.count(FixCycle.id), None),
                else_=func.max(FixCycle.completed_at),
            ).label("latest"),
        )
        .where(FixCycle.step_id.in_(step_db_ids))
        .group_by(FixCycle.step_id)
    ).all()
    for row in cycle_rows:
        existing = spans.get(row.step_id)
        if existing is None:
            spans[row.step_id] = (row.earliest, row.latest)
        else:
            earliest_candidates = [v for v in (existing[0], row.earliest) if v is not None]
            earliest = min(earliest_candidates) if earliest_candidates else None
            # If either side still has an incomplete aggregate (None from the CASE
            # above), the step is not fully finished — the combined latest is None.
            if existing[1] is None or row.latest is None:
                latest = None
            else:
                latest = max(existing[1], row.latest)
            spans[row.step_id] = (earliest, latest)

    return spans


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


def _get_project_or_404(project_id: str, db: Session) -> Project:
    project = db.scalar(select(Project).where(Project.id == project_id))
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id!r} not found")
    return project


def _get_item_or_404(project_id: str, item_id: str, db: Session) -> WorkItem:
    item = db.scalar(
        select(WorkItem).where(
            WorkItem.project_id == project_id,
            WorkItem.id == item_id,
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail=f"Work item {item_id!r} not found")
    return item


def _read_report_file(report_file: str | None, repo_root: str | None) -> str | None:
    """Read report markdown from disk when DB content is not available."""
    if report_file is None or repo_root is None:
        return None
    path = Path(repo_root) / report_file
    if not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _get_steps(
    project_id: str, item_id: str, db: Session, project: Project | None = None
) -> list[StepDetail]:
    from sqlalchemy import func

    bi = _get_batch_item(project_id, item_id, db)
    repo_root = project.repo_root if project else None
    workflow_steps = list(
        db.scalars(
            select(WorkflowStep)
            .where(
                WorkflowStep.project_id == project_id,
                WorkflowStep.work_item_id == item_id,
            )
            .order_by(WorkflowStep.step_number)
        ).all()
    )
    step_db_ids = [s.id for s in workflow_steps]
    fix_cycle_counts: dict[int, int] = {}
    if step_db_ids:
        rows = db.execute(
            select(FixCycle.step_id, func.count(FixCycle.id).label("cnt"))
            .where(FixCycle.step_id.in_(step_db_ids))
            .group_by(FixCycle.step_id)
        ).all()
        fix_cycle_counts = {row.step_id: row.cnt for row in rows}

    step_spans = _aggregate_step_spans(db, step_db_ids)

    last_run_map: dict[int, StepRun] = {}
    run_count_map: dict[int, int] = {}
    if step_db_ids:
        last_run_sub = (
            select(
                StepRun.step_id,
                StepRun.id.label("run_id"),
                StepRun.error_message,
                func.row_number()
                .over(
                    partition_by=StepRun.step_id,
                    order_by=StepRun.run_number.desc(),
                )
                .label("rn"),
                func.count(StepRun.id).over(partition_by=StepRun.step_id).label("rc"),
            )
            .where(StepRun.step_id.in_(step_db_ids))
            .subquery()
        )
        bulk_rows = db.execute(
            select(
                last_run_sub.c.step_id,
                last_run_sub.c.run_id,
                last_run_sub.c.error_message,
                last_run_sub.c.rc,
            ).where(last_run_sub.c.rn == 1)
        ).all()
        for row in bulk_rows:
            run = StepRun(
                id=row.run_id,
                step_id=row.step_id,
                error_message=row.error_message,
                run_number=0,
                status=None,
            )
            last_run_map[row.step_id] = run
            run_count_map[row.step_id] = row.rc

    result: list[StepDetail] = [_synthetic_setup_step(bi)]
    for step in workflow_steps:
        last_run = last_run_map.get(step.id)
        error_msg = last_run.error_message if last_run else None
        run_count = run_count_map.get(step.id, 0)

        earliest_started_at, latest_completed_at = step_spans.get(step.id, (None, None))
        if earliest_started_at is not None and latest_completed_at is not None:
            dur = (latest_completed_at - earliest_started_at).total_seconds()
        else:
            dur = None

        report = step.report_content or _read_report_file(step.report_file, repo_root)

        result.append(
            StepDetail(
                step_id=step.step_id,
                agent_label=step.agent_label,
                step_type=step.step_type.value,
                status=step.status.value,
                duration_secs=dur,
                started_at=earliest_started_at,
                completed_at=latest_completed_at,
                error_message=error_msg,
                run_count=run_count,
                step_label=step.step_label,
                description=step.description,
                report_content=report,
                fix_cycle_count=fix_cycle_counts.get(step.id, 0),
            )
        )
    result.append(_synthetic_merge_step(bi))
    return result


def _get_metrics(
    project_id: str, item_id: str, steps: list[StepDetail], db: Session
) -> ItemMetrics:
    # Total duration: from first step start to last step end
    started_ats = [s.started_at for s in steps if s.started_at]
    completed_ats = [s.completed_at for s in steps if s.completed_at]
    total_dur: float | None = None
    if started_ats and completed_ats:
        total_dur = (max(completed_ats) - min(started_ats)).total_seconds()

    # Fix cycles: sum across all steps
    step_db_ids = list(
        db.scalars(
            select(WorkflowStep.id).where(
                WorkflowStep.project_id == project_id,
                WorkflowStep.work_item_id == item_id,
            )
        ).all()
    )
    fix_count = 0
    if step_db_ids:
        fix_count = len(
            list(db.scalars(select(FixCycle.id).where(FixCycle.step_id.in_(step_db_ids))).all())
        )

    steps_completed = sum(1 for s in steps if s.status == "completed")
    return ItemMetrics(
        total_duration_secs=total_dur,
        fix_cycles_count=fix_count,
        steps_completed=steps_completed,
        steps_total=len(steps),
    )


def _get_batch_ref(project_id: str, item_id: str, db: Session) -> str | None:
    bi = db.scalar(
        select(BatchItem)
        .where(
            BatchItem.project_id == project_id,
            BatchItem.work_item_id == item_id,
        )
        .order_by(BatchItem.id.desc())
    )
    return bi.batch_id if bi else None


def _get_batch_item_error(project_id: str, item_id: str, db: Session) -> str | None:
    """Return the batch_item notes if the item failed at setup (no step runs)."""
    bi = db.scalar(
        select(BatchItem)
        .where(
            BatchItem.project_id == project_id,
            BatchItem.work_item_id == item_id,
            BatchItem.status == BatchItemStatus.failed,
        )
        .order_by(BatchItem.id.desc())
    )
    if bi and bi.notes:
        return bi.notes
    return None


def _get_batch_item(project_id: str, item_id: str, db: Session) -> BatchItem | None:
    return db.scalar(
        select(BatchItem)
        .where(
            BatchItem.project_id == project_id,
            BatchItem.work_item_id == item_id,
        )
        .order_by(BatchItem.id.desc())
    )


def _setup_status(bi: BatchItem | None) -> str:
    if bi is None:
        return "pending"
    if bi.worktree_info:
        return "completed"
    if bi.status == BatchItemStatus.setting_up:
        return "in_progress"
    if bi.status == BatchItemStatus.failed:
        return "failed"
    return "pending"


def _merge_status(bi: BatchItem | None) -> str:
    if bi is None or not bi.worktree_info:
        return "pending"
    if bi.merged_at is not None:
        return "completed"
    if bi.status in (BatchItemStatus.merging, BatchItemStatus.completed):
        return "in_progress"
    if bi.status == BatchItemStatus.failed:
        return "failed"
    return "pending"


def _synthetic_setup_step(bi: BatchItem | None) -> StepDetail:
    status = _setup_status(bi)
    dur: float | None = None
    if bi and bi.worktree_info and bi.started_at:
        from datetime import datetime

        created_raw = (
            bi.worktree_info.get("created_at") if isinstance(bi.worktree_info, dict) else None
        )
        if created_raw:
            try:
                created = datetime.fromisoformat(created_raw)
                if created.tzinfo is None:
                    created = created.replace(tzinfo=UTC)
                started = bi.started_at
                if started.tzinfo is None:
                    started = started.replace(tzinfo=UTC)
                dur = (created - started).total_seconds()
                if dur < 0:
                    dur = None
            except ValueError:
                pass
    return StepDetail(
        step_id="S00",
        agent_label="Worktree Setup",
        step_type="setup",
        status=status,
        duration_secs=dur,
        started_at=bi.started_at if bi else None,
        completed_at=None,
        error_message=bi.notes if bi and status == "failed" else None,
        run_count=0,
        is_synthetic=True,
    )


def _synthetic_merge_step(bi: BatchItem | None) -> StepDetail:
    status = _merge_status(bi)
    return StepDetail(
        step_id="MERGE",
        agent_label="Squash Merge",
        step_type="merge",
        status=status,
        duration_secs=None,
        started_at=None,
        completed_at=bi.merged_at if bi else None,
        error_message=bi.notes if bi and status == "failed" else None,
        run_count=0,
        is_synthetic=True,
    )


def _read_log_file(log_file: str | None) -> str | None:
    """Read log content directly from disk, stripping ANSI escape codes."""
    if log_file is None:
        return None
    path = Path(log_file)
    if not path.is_file():
        return None
    try:
        from orch.utils.log_capture import strip_ansi

        return strip_ansi(path.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return None


def _get_log_modified(log_file: str | None) -> str | None:
    """Return human-readable last-modified time for a log file."""
    if log_file is None:
        return None
    path = Path(log_file)
    if not path.is_file():
        return None
    try:
        from datetime import datetime

        mtime = path.stat().st_mtime
        dt = datetime.fromtimestamp(mtime, tz=UTC).astimezone()
        return dt.strftime("%H:%M:%S")
    except OSError:
        return None


def _reverse_log(content: str | None) -> str | None:
    """Return log content with lines in reverse order (newest first)."""
    if not content:
        return content
    lines = content.splitlines()
    lines.reverse()
    return "\n".join(lines)


def _setup_log_content(bi: BatchItem) -> str:
    lines = ["=== Worktree Setup ==="]
    if bi.worktree_info and isinstance(bi.worktree_info, dict):
        lines.append(f"Path:       {bi.worktree_info.get('path', '—')}")
        lines.append(f"Branch:     {bi.worktree_info.get('branch', '—')}")
        lines.append(f"Created at: {bi.worktree_info.get('created_at', '—')}")
    else:
        lines.append("Worktree info not available.")
    if bi.notes:
        lines.append("")
        lines.append(f"Notes: {bi.notes}")
    return "\n".join(lines)


def _merge_log_content(bi: BatchItem) -> str:
    lines = ["=== Squash Merge ==="]
    if bi.merged_at:
        lines.append(f"Merged at: {bi.merged_at.isoformat()}")
    if bi.merge_info and isinstance(bi.merge_info, dict):
        stdout = bi.merge_info.get("stdout", "")
        if stdout:
            lines.append("")
            lines.append("--- stdout ---")
            lines.append(stdout)
    if bi.notes:
        lines.append("")
        lines.append(f"Notes: {bi.notes}")
    if len(lines) == 1:
        lines.append("No merge output recorded.")
    return "\n".join(lines)


@dataclass
class ArtifactFile:
    """Deprecated — kept for backward compatibility with tests that import it.

    Use ``ArtifactNode`` and ``_list_artifact_tree`` instead.
    """

    name: str
    path: str
    size_bytes: int
    is_dir: bool = False


def _list_evidences(
    item: WorkItem, project: Project, db: Session, worktree_path: str | None = None
) -> list[EvidenceFile]:
    """Fetch evidences for item from DB first, then fall back to filesystem.

    DB is authoritative for completed/archived items; filesystem provides
    in-progress post-evidence snapshots written by browser verification
    agents that haven't flushed to the DB yet.
    """
    # DB-first
    rows = db.scalars(
        select(WorkItemEvidence).where(
            WorkItemEvidence.project_id == project.id,
            WorkItemEvidence.work_item_id == item.id,
        )
    ).all()
    seen: set[tuple[str, str]] = set()
    results: list[EvidenceFile] = []
    for row in rows:
        key = (row.phase.value, row.filename)
        if key in seen:
            continue
        seen.add(key)
        results.append(
            EvidenceFile(
                filename=row.filename,
                phase=row.phase.value,
                abs_path="",  # not from FS
                size_bytes=row.size_bytes,
                content=row.content,
                content_type=row.content_type,
            )
        )
    # FS fallback for in-progress post-evidence (worktree only)
    if worktree_path:
        rel_evidences = Path("ai-dev") / "active" / item.id / "evidences"
        base = Path(worktree_path) / rel_evidences
        for phase in ("pre", "post"):
            phase_dir = base / phase
            if not phase_dir.exists():
                continue
            try:
                for entry in sorted(phase_dir.iterdir()):
                    if entry.is_file():
                        key = (phase, entry.name)
                        if key not in seen:
                            seen.add(key)
                            results.append(
                                EvidenceFile(
                                    filename=entry.name,
                                    phase=phase,
                                    abs_path=str(entry),
                                    size_bytes=entry.stat().st_size,
                                )
                            )
            except OSError:
                pass
    return results


def _get_log_sections(project_id: str, item_id: str, db: Session) -> list[LogSection]:
    bi = _get_batch_item(project_id, item_id, db)

    setup_content = _setup_log_content(bi) if bi else "No batch item found."
    sections: list[LogSection] = [
        LogSection(
            step_id="S00",
            agent_label="Worktree Setup",
            status=_setup_status(bi),
            db_step_id=None,
            runs=[],
            static_content=setup_content,
        )
    ]

    workflow_steps = list(
        db.scalars(
            select(WorkflowStep)
            .where(
                WorkflowStep.project_id == project_id,
                WorkflowStep.work_item_id == item_id,
            )
            .order_by(WorkflowStep.step_number)
        ).all()
    )
    for step in workflow_steps:
        runs = list(
            db.scalars(
                select(StepRun).where(StepRun.step_id == step.id).order_by(StepRun.run_number)
            ).all()
        )
        run_logs = [
            RunLog(
                run_number=r.run_number,
                status=r.status.value,
                duration_secs=r.duration_secs,
                is_running=r.status.value == "running",
                log_content=_reverse_log(r.log_content or _read_log_file(r.log_file)),
                log_modified=_get_log_modified(r.log_file),
            )
            for r in runs
        ]
        sections.append(
            LogSection(
                step_id=step.step_id,
                agent_label=step.agent_label,
                status=step.status.value,
                db_step_id=step.id,
                runs=run_logs,
            )
        )

    merge_content = _merge_log_content(bi) if bi else "No batch item found."
    sections.append(
        LogSection(
            step_id="MERGE",
            agent_label="Squash Merge",
            status=_merge_status(bi),
            db_step_id=None,
            runs=[],
            static_content=merge_content,
        )
    )
    return sections


def _get_fix_cycles(project_id: str, item_id: str, db: Session) -> list[FixCycleDetail]:
    """Return all fix cycles for a work item, ordered by step then cycle number."""
    workflow_steps = list(
        db.scalars(
            select(WorkflowStep)
            .where(
                WorkflowStep.project_id == project_id,
                WorkflowStep.work_item_id == item_id,
            )
            .order_by(WorkflowStep.step_number)
        ).all()
    )
    if not workflow_steps:
        return []

    step_map = {s.id: s for s in workflow_steps}
    fix_cycles = list(
        db.scalars(
            select(FixCycle)
            .where(FixCycle.step_id.in_(list(step_map.keys())))
            .order_by(FixCycle.step_id, FixCycle.cycle_number)
        ).all()
    )

    result: list[FixCycleDetail] = []
    for fc in fix_cycles:
        step = step_map.get(fc.step_id)
        dur: float | None = None
        if fc.started_at and fc.completed_at:
            dur = (fc.completed_at - fc.started_at).total_seconds()

        log_file = (fc.fix_metadata or {}).get("log_file")
        raw_log = _read_log_file(log_file)
        log_content = _reverse_log(raw_log) if raw_log else None

        result.append(
            FixCycleDetail(
                id=fc.id,
                db_step_id=fc.step_id,
                step_id=step.step_id if step else "?",
                agent_label=step.agent_label if step else "?",
                cycle_number=fc.cycle_number,
                trigger_type=fc.trigger_type.value,
                status=fc.status.value,
                started_at=fc.started_at,
                completed_at=fc.completed_at,
                duration_secs=dur,
                log_content=log_content,
                log_modified=_get_log_modified(log_file),
                is_running=fc.status.value == "in_progress",
            )
        )
    return result


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/item/{item_id}", response_class=HTMLResponse)
def item_detail(
    project_id: str,
    item_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    project = _get_project_or_404(project_id, db)
    item = _get_item_or_404(project_id, item_id, db)
    steps = _get_steps(project_id, item_id, db)
    metrics = _get_metrics(project_id, item_id, steps, db)
    batch_ref = _get_batch_ref(project_id, item_id, db)
    setup_error = _get_batch_item_error(project_id, item_id, db)

    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "pages/project/item_detail.html",
        {
            "current_project": project,
            "running_count": 0,
            "item": item,
            "item_type": item.type.value,
            "item_status": item.status.value,
            "steps": steps,
            "metrics": metrics,
            "batch_ref": batch_ref,
            "setup_error": setup_error,
        },
    )


@router.get("/item/{item_id}/fragment/header", response_class=HTMLResponse)
def item_header_fragment(
    project_id: str,
    item_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    """htmx fragment: returns item header + metrics for live refresh."""
    project = _get_project_or_404(project_id, db)
    item = _get_item_or_404(project_id, item_id, db)
    steps = _get_steps(project_id, item_id, db)
    metrics = _get_metrics(project_id, item_id, steps, db)
    batch_ref = _get_batch_ref(project_id, item_id, db)
    setup_error = _get_batch_item_error(project_id, item_id, db)

    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/item_header.html",
        {
            "current_project": project,
            "item": item,
            "item_type": item.type.value,
            "item_status": item.status.value,
            "batch_ref": batch_ref,
            "setup_error": setup_error,
            "metrics": metrics,
        },
    )


@router.get("/item/{item_id}/tab/overview", response_class=HTMLResponse)
def item_tab_overview(
    project_id: str,
    item_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    project = _get_project_or_404(project_id, db)
    item = _get_item_or_404(project_id, item_id, db)
    steps = _get_steps(project_id, item_id, db)

    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/item_overview.html",
        {
            "current_project": project,
            "item": item,
            "steps": steps,
        },
    )


@router.get("/item/{item_id}/tab/design-doc", response_class=HTMLResponse)
def item_tab_design_doc(
    project_id: str,
    item_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    project = _get_project_or_404(project_id, db)
    item = _get_item_or_404(project_id, item_id, db)

    # Prefer archived Tier 1 content; fall back to reading from disk
    content: str | None = item.design_doc_content
    if content is None and item.design_doc_path and project.repo_root:
        disk_path = Path(project.repo_root) / item.design_doc_path
        try:
            content = disk_path.read_text(encoding="utf-8")
        except OSError:
            content = None

    design_doc_html = render_markdown(content)

    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/item_design_doc.html",
        {
            "item": item,
            "design_doc_html": design_doc_html,
            "has_content": bool(content),
        },
    )


@router.get("/item/{item_id}/tab/functional-doc", response_class=HTMLResponse)
def item_tab_functional_doc(
    project_id: str,
    item_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    project = _get_project_or_404(project_id, db)
    item = _get_item_or_404(project_id, item_id, db)

    content: str | None = item.functional_doc_content
    if content is None and item.functional_doc_path and project.repo_root:
        disk_path = Path(project.repo_root) / item.functional_doc_path
        try:
            content = disk_path.read_text(encoding="utf-8")
        except OSError:
            content = None

    functional_doc_html = render_markdown(content)

    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/item_functional_doc.html",
        {
            "item": item,
            "functional_doc_html": functional_doc_html,
            "has_content": bool(content),
        },
    )


@router.get("/item/{item_id}/tab/reports", response_class=HTMLResponse)
def item_tab_reports(
    project_id: str,
    item_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    project = _get_project_or_404(project_id, db)
    item = _get_item_or_404(project_id, item_id, db)
    steps = _get_steps(project_id, item_id, db, project=project)

    report_sections = [
        ReportSection(
            step_id=s.step_id,
            agent_label=s.agent_label,
            step_type=s.step_type,
            status=s.status,
            run_count=s.run_count,
            report_html=render_markdown(s.report_content),
        )
        for s in steps
        if s.report_content
    ]

    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/item_reports.html",
        {
            "item": item,
            "report_sections": report_sections,
        },
    )


@router.get("/item/{item_id}/tab/artifacts", response_class=HTMLResponse)
def item_tab_artifacts(
    project_id: str,
    item_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    project = _get_project_or_404(project_id, db)
    item = _get_item_or_404(project_id, item_id, db)
    bi = _get_batch_item(project_id, item_id, db)
    worktree_path = bi.worktree_info.get("path") if bi and bi.worktree_info else None
    artifact_tree = _list_artifact_tree(project_id, item, project, worktree_path)

    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/item_artifacts.html",
        {
            "item": item,
            "artifact_tree": artifact_tree,
            "is_archived": item.archived_at is not None,
            "archive_size_bytes": item.archive_size_bytes,
        },
    )


@router.get("/item/{item_id}/artifact-raw")
def item_artifact_raw(
    project_id: str,
    item_id: str,
    path: str,
    db: Session = Depends(get_db),
) -> Response:
    """Serve a raw artifact file by relative path.

    Path traversal protection: the resolved path must be within the artifact root.
    """
    project = _get_project_or_404(project_id, db)
    item = _get_item_or_404(project_id, item_id, db)
    bi = _get_batch_item(project_id, item_id, db)
    worktree_path = bi.worktree_info.get("path") if bi and bi.worktree_info else None
    artifact_root = _resolve_artifact_root(item, project, worktree_path)
    if artifact_root is None:
        raise HTTPException(status_code=404, detail="Artifact root not found")

    # Resolve the requested file and protect against traversal
    try:
        requested = (artifact_root / path).resolve()
        requested.relative_to(artifact_root.resolve())
    except ValueError as err:
        raise HTTPException(status_code=403, detail="Access denied") from err

    if not requested.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    content_type, _ = mimetypes.guess_type(path)
    content_type = content_type or "application/octet-stream"
    try:
        data = requested.read_bytes()
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Could not read file") from exc
    return Response(content=data, media_type=content_type)


@router.get("/item/{item_id}/tab/logs", response_class=HTMLResponse)
def item_tab_logs(
    project_id: str,
    item_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    _get_project_or_404(project_id, db)
    item = _get_item_or_404(project_id, item_id, db)
    log_sections = _get_log_sections(project_id, item_id, db)

    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/item_logs.html",
        {
            "item": item,
            "log_sections": log_sections,
            "project_id": project_id,
        },
    )


@router.get("/item/{item_id}/tab/fix-cycles", response_class=HTMLResponse)
def item_tab_fix_cycles(
    project_id: str,
    item_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    _get_project_or_404(project_id, db)
    item = _get_item_or_404(project_id, item_id, db)
    fix_cycles = _get_fix_cycles(project_id, item_id, db)

    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/item_fix_cycles.html",
        {
            "item": item,
            "project_id": project_id,
            "fix_cycles": fix_cycles,
        },
    )


@router.get("/item/{item_id}/execution-report", response_class=HTMLResponse)
def item_execution_report(
    project_id: str,
    item_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    _get_project_or_404(project_id, db)
    item = _get_item_or_404(project_id, item_id, db)
    execution_report = assemble_execution_report(db, project_id, item_id)

    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "pages/project/item_execution_report.html",
        {
            "current_project": _get_project_or_404(project_id, db),
            "item": item,
            "execution_report": execution_report,
        },
    )


@router.get("/item/{item_id}/tab/execution-report", response_class=HTMLResponse)
def item_tab_execution_report(
    project_id: str,
    item_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    _get_project_or_404(project_id, db)
    item = _get_item_or_404(project_id, item_id, db)
    execution_report = assemble_execution_report(db, project_id, item_id)

    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/item_execution_report.html",
        {
            "item": item,
            "execution_report": execution_report,
        },
    )


@router.get("/item/{item_id}/tab/evidences", response_class=HTMLResponse)
def item_tab_evidences(
    project_id: str,
    item_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    project = _get_project_or_404(project_id, db)
    item = _get_item_or_404(project_id, item_id, db)
    bi = _get_batch_item(project_id, item_id, db)
    worktree_path = (bi.worktree_info or {}).get("path") if bi else None
    evidences = _list_evidences(item, project, db, worktree_path)

    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/item_evidences.html",
        {
            "item": item,
            "project_id": project_id,
            "evidences": evidences,
            "pre_evidences": [e for e in evidences if e.phase == "pre"],
            "post_evidences": [e for e in evidences if e.phase == "post"],
        },
    )


@router.get("/item/{item_id}/evidence/{phase}/{filename}")
def item_evidence_file(
    project_id: str,
    item_id: str,
    phase: str,
    filename: str,
    db: Session = Depends(get_db),
) -> Response:
    """Serve a single evidence image file (DB-first, FS fallback for in-progress)."""
    if phase not in ("pre", "post"):
        raise HTTPException(status_code=404, detail="Invalid evidence phase")
    project = _get_project_or_404(project_id, db)
    item = _get_item_or_404(project_id, item_id, db)

    # DB-first
    row = db.scalars(
        select(WorkItemEvidence).where(
            WorkItemEvidence.project_id == project_id,
            WorkItemEvidence.work_item_id == item_id,
            WorkItemEvidence.phase == EvidencePhase(phase),
            WorkItemEvidence.filename == filename,
        )
    ).first()
    if row is not None:
        return Response(
            content=row.content,
            media_type=row.content_type,
        )

    # FS fallback for in-progress post-evidence
    evidence_path = (
        Path(project.repo_root) / "ai-dev" / "active" / item.id / "evidences" / phase / filename
    )
    try:
        evidence_path.resolve().relative_to(
            (Path(project.repo_root) / "ai-dev" / "active" / item.id / "evidences").resolve()
        )
    except ValueError as err:
        raise HTTPException(status_code=403, detail="Access denied") from err
    if not evidence_path.is_file():
        raise HTTPException(status_code=404, detail="Evidence file not found")
    content_type, _ = mimetypes.guess_type(filename)
    content_type = content_type or "application/octet-stream"
    try:
        data = evidence_path.read_bytes()
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Could not read file") from exc
    return Response(content=data, media_type=content_type)


@router.get("/item/{item_id}/log-content/{step_db_id}/{run_number}", response_class=HTMLResponse)
def item_log_content(
    project_id: str,
    item_id: str,
    step_db_id: int,
    run_number: int,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    _get_item_or_404(project_id, item_id, db)
    run = db.scalar(
        select(StepRun).where(
            StepRun.step_id == step_db_id,
            StepRun.run_number == run_number,
        )
    )
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    log_content = _reverse_log(run.log_content or _read_log_file(run.log_file))
    log_modified = _get_log_modified(run.log_file)

    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/item_log_content.html",
        {
            "log_content": log_content,
            "log_modified": log_modified,
            "is_running": run.status.value == "running",
            "project_id": project_id,
            "item_id": item_id,
            "step_db_id": step_db_id,
            "run_number": run_number,
        },
    )
