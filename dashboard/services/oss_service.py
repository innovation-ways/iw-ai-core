"""OSS compliance dashboard service.

Enqueues ProjectOssJob rows, spawns `uv run iw oss …` subprocesses,
streams stdout to the DB, and exposes helpers for Tier-1 probe + freshness computation.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import logging
import os
import re
import signal
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sqlalchemy.exc import SQLAlchemyError

from orch.db.models import (
    OssFinding,
    OssScan,
    OssScanStatus,
    Project,
    ProjectOssJob,
    ProjectOssJobKind,
    ProjectOssJobStatus,
)
from orch.oss.fix_recipes import get_recipe
from orch.oss.tool_probe import probe_tier1

if TYPE_CHECKING:
    from asyncio import StreamReader
    from collections.abc import AsyncGenerator, Callable

    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_STDOUT_TAIL_BYTES = 16 * 1024

_PROCESS_START_UTC = datetime.now(UTC)


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _truncate_tail(content: str) -> str:
    """Truncate content to the last _STDOUT_TAIL_BYTES bytes, preserving valid UTF-8.

    Args:
        content: Raw string output to trim.

    Returns:
        The original string if it fits within the byte limit, otherwise the
        trailing bytes decoded back to a string with replacement on bad sequences.
    """
    encoded = content.encode("utf-8", errors="replace")
    if len(encoded) <= _STDOUT_TAIL_BYTES:
        return content
    return encoded[-_STDOUT_TAIL_BYTES:].decode("utf-8", errors="replace")


async def _stream_to_tail(
    stream: StreamReader,
    job_id: int,
    session_factory: Callable[[], Session],
    persist_interval: float = 1.0,
) -> str:
    accumulated: list[str] = []
    last_persist = _utcnow()
    running = True

    async def _writer() -> None:
        nonlocal last_persist, running
        while running:
            await asyncio.sleep(persist_interval)
            if not accumulated:
                continue
            current = "".join(accumulated)
            tail = _truncate_tail(current)
            sess = session_factory()
            try:
                sess.query(ProjectOssJob).filter(ProjectOssJob.id == job_id).update(
                    {"stdout_tail": tail}, synchronize_session=False
                )
                sess.commit()
            except SQLAlchemyError:
                logger.exception("Failed to persist stdout_tail for job %s", job_id)
            finally:
                sess.close()
            last_persist = _utcnow()

    writer_task = asyncio.create_task(_writer())
    try:
        while True:
            line = await stream.readline()
            if not line:
                break
            decoded = line.decode("utf-8", errors="replace")
            accumulated.append(decoded)
    finally:
        running = False
        await writer_task

    return "".join(accumulated)


def _git_head(repo_root: str) -> str | None:
    """Return the full SHA of the current HEAD commit for a repository.

    Args:
        repo_root: Absolute path to the git repository root.

    Returns:
        40-character hex SHA string, or None if git is unavailable or the call fails.
    """
    try:
        git_path_str = subprocess.run(
            ["git", "which", "git"], capture_output=True, text=True
        ).stdout.strip()
        git_path = Path(git_path_str) if git_path_str else Path("git")
        result = subprocess.run(
            [str(git_path), "rev-parse", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.SubprocessError, OSError):
        logger.exception("Failed to get git HEAD for %s", repo_root)
    return None


async def _run_scan(
    project: Project,
    job_id: int,
    session_factory: Callable[[], Session],
) -> None:
    run_started_at = _utcnow()
    cmd = ["uv", "run", "iw", "oss", "scan", "--project", project.id]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=project.repo_root,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    if proc.stdout is None:
        raise RuntimeError("No stdout pipe from subprocess")
    full_output = await _stream_to_tail(proc.stdout, job_id, session_factory)
    exit_code = await proc.wait()
    tail = _truncate_tail(full_output)
    sess = session_factory()
    try:
        latest = (
            sess.query(OssScan)
            .filter(
                OssScan.project_id == project.id,
                OssScan.started_at >= run_started_at,
            )
            .order_by(OssScan.started_at.desc())
            .first()
        )

        if latest is not None and latest.status == OssScanStatus.error:
            job_status = ProjectOssJobStatus.error
            error_message: str | None = latest.error_message or (
                f"Scan exited with code {latest.exit_code}"
                if latest.exit_code is not None
                else "Scan errored"
            )
        elif latest is not None and latest.status == OssScanStatus.complete:
            job_status = ProjectOssJobStatus.complete
            error_message = None
        else:
            # `iw oss scan` exits 0 on green/yellow, 1 on red — both mean the scan
            # ran to completion. Any other exit code is a CLI/subprocess error.
            job_status = (
                ProjectOssJobStatus.complete if exit_code in (0, 1) else ProjectOssJobStatus.error
            )
            error_message = (
                f"Subprocess exited with code {exit_code}" if exit_code not in (0, 1) else None
            )

        sess.query(ProjectOssJob).filter(ProjectOssJob.id == job_id).update(
            {
                "exit_code": exit_code,
                "stdout_tail": tail,
                "completed_at": _utcnow(),
                "status": job_status,
                **({"scan_id": latest.id} if latest is not None else {}),
                **({"error_message": error_message} if error_message is not None else {}),
            },
            synchronize_session=False,
        )
        sess.commit()
    finally:
        sess.close()


async def _run_install(
    project: Project,
    job_id: int,
    session_factory: Callable[[], Session],
) -> None:
    cmd = ["uv", "run", "iw", "oss", "install", "--project", project.id]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=project.repo_root,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    if proc.stdout is None:
        raise RuntimeError("No stdout pipe from subprocess")
    full_output = await _stream_to_tail(proc.stdout, job_id, session_factory)
    exit_code = await proc.wait()
    tail = _truncate_tail(full_output)
    sess = session_factory()
    try:
        sess.query(ProjectOssJob).filter(ProjectOssJob.id == job_id).update(
            {
                "exit_code": exit_code,
                "stdout_tail": tail,
                "status": ProjectOssJobStatus.complete
                if exit_code == 0
                else ProjectOssJobStatus.error,
                "completed_at": _utcnow(),
                **(
                    {"error_message": f"Install exited with code {exit_code}"}
                    if exit_code != 0
                    else {}
                ),
            },
            synchronize_session=False,
        )
        sess.commit()
    finally:
        sess.close()


async def _run_fix(
    project: Project,
    job_id: int,
    session_factory: Callable[[], Session],
    check_id: str,
    apply: bool,
) -> None:
    cmd = ["uv", "run", "iw", "oss", "fix", check_id, "--project", project.id]
    if apply:
        cmd.append("--apply")
    cmd.append("--json")
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=project.repo_root,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    if proc.stdout is None:
        raise RuntimeError("No stdout pipe from subprocess")
    full_output = await _stream_to_tail(proc.stdout, job_id, session_factory)
    exit_code = await proc.wait()
    sess = session_factory()
    try:
        sess.query(ProjectOssJob).filter(ProjectOssJob.id == job_id).update(
            {
                "exit_code": exit_code,
                "stdout_tail": _truncate_tail(full_output),
                "completed_at": _utcnow(),
                "status": ProjectOssJobStatus.complete
                if exit_code == 0
                else ProjectOssJobStatus.error,
            },
            synchronize_session=False,
        )
        sess.commit()
    finally:
        sess.close()


async def run_fixes(
    session_factory: Callable[[], Session],
    job_id: int,
) -> None:
    """Apply a sequence of fix recipes and mark the job complete.

    Reads check_ids from job.stdout_tail (JSON array).
    """
    sess = session_factory()
    try:
        job = sess.query(ProjectOssJob).filter(ProjectOssJob.id == job_id).first()
    finally:
        sess.close()

    if job is None:
        logger.warning("Job %s not found", job_id)
        return

    check_ids: list[str] = []
    if job.stdout_tail:
        try:
            check_ids = json.loads(job.stdout_tail)
        except Exception:
            check_ids = []

    project = session_factory().get(Project, job.project_id)
    if project is None:
        logger.error("Project %s not found for job %s", job.project_id, job_id)
        return

    for cid in check_ids:
        recipe = get_recipe(cid)
        if recipe is None:
            logger.warning("No recipe for %s, skipping", cid)
            continue
        preview = recipe.apply(Path(project.repo_root))
        logger.info("Applied %s: %s", cid, [str(f) for f in preview.target_files])

    sess = session_factory()
    try:
        sess.query(ProjectOssJob).filter(ProjectOssJob.id == job_id).update(
            {
                "status": ProjectOssJobStatus.complete,
                "completed_at": _utcnow(),
                "exit_code": 0,
            },
            synchronize_session=False,
        )
        sess.commit()
    finally:
        sess.close()


async def run_job(session_factory: Callable[[], Session], job_id: int) -> None:
    """Fire-and-forget worker that executes a ProjectOssJob.

    Sets status='running', started_at=now(), then runs the appropriate subprocess
    and updates the job row on completion.
    """
    sess = session_factory()
    try:
        job = sess.query(ProjectOssJob).filter(ProjectOssJob.id == job_id).first()
    finally:
        sess.close()

    if job is None:
        logger.warning("Job %s not found", job_id)
        return

    project = session_factory().get(Project, job.project_id)
    if project is None:
        logger.error("Project %s not found for job %s", job.project_id, job_id)
        return

    sess = session_factory()
    try:
        sess.query(ProjectOssJob).filter(ProjectOssJob.id == job_id).update(
            {"status": ProjectOssJobStatus.running, "started_at": _utcnow()},
            synchronize_session=False,
        )
        sess.commit()
    finally:
        sess.close()

    try:
        if job.kind == ProjectOssJobKind.scan:
            await _run_scan(project, job_id, session_factory)
        elif job.kind == ProjectOssJobKind.install:
            await _run_install(project, job_id, session_factory)
        elif job.kind == ProjectOssJobKind.fix:
            check_id = ""
            if job.stdout_tail:
                try:
                    parsed = json.loads(job.stdout_tail)
                    if isinstance(parsed, list) and parsed:
                        check_id = parsed[0]
                    elif isinstance(parsed, str):
                        check_id = parsed
                except Exception:
                    check_id = job.stdout_tail
            await _run_fix(project, job_id, session_factory, check_id, apply=True)
        else:
            logger.error("Unknown job kind %s for job %s", job.kind, job_id)
    except Exception as exc:
        logger.exception("Job %s failed with exception: %s", job_id, exc)
        sess = session_factory()
        try:
            sess.query(ProjectOssJob).filter(ProjectOssJob.id == job_id).update(
                {
                    "status": ProjectOssJobStatus.error,
                    "error_message": str(exc),
                    "completed_at": _utcnow(),
                },
                synchronize_session=False,
            )
            sess.commit()
        finally:
            sess.close()


async def cancel_job(session: Session, job_id: int) -> None:
    """Cancel a running job: SIGTERM, wait, SIGKILL if needed."""
    job = session.query(ProjectOssJob).filter(ProjectOssJob.id == job_id).first()
    if job is None:
        return

    if job.status not in (ProjectOssJobStatus.running, ProjectOssJobStatus.queued):
        return

    session.query(ProjectOssJob).filter(ProjectOssJob.id == job_id).update(
        {"status": ProjectOssJobStatus.cancelled}, synchronize_session=False
    )
    session.commit()

    if job.status == ProjectOssJobStatus.running:
        try:
            pid_file = Path(f"/tmp/oss-job-{job_id}.pid")  # noqa: S108  # nosec B108 — ephemeral PID file, owner-only
            if pid_file.exists():
                pid = int(pid_file.read_text().strip())
                try:
                    os.kill(pid, signal.SIGTERM)
                    await asyncio.sleep(2)
                    with contextlib.suppress(ProcessLookupError):
                        os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                pid_file.unlink(missing_ok=True)
        except Exception as exc:
            logger.warning("Error sending SIGTERM to job %s: %s", job_id, exc)


def enqueue_job(
    session: Session,
    project_id: str,
    kind: ProjectOssJobKind | str,
    *,
    check_id: str | None = None,
    check_ids: list[str] | None = None,
) -> ProjectOssJob:
    """Create a new ProjectOssJob row with status=queued.

    The ``public_id`` (O-XXXXX) is auto-allocated by the model's
    ``before_insert`` event listener — no need to set it explicitly.

    For fix jobs: pass check_id for single-fix, or check_ids (JSON in stdout_tail) for batch.
    """
    if isinstance(kind, str):
        kind = ProjectOssJobKind(kind)
    job = ProjectOssJob(
        project_id=project_id,
        kind=kind,
        status=ProjectOssJobStatus.queued,
    )
    if check_id:
        job.stdout_tail = check_id
    elif check_ids:
        job.stdout_tail = json.dumps(check_ids)
    session.add(job)
    session.flush()
    return job


async def job_event_stream(
    session_factory: Callable[[], Session],
    job_id: int,
    heartbeat_interval: float = 20.0,
) -> AsyncGenerator[str, None]:
    """Yields SSE-formatted messages for job progress.

    On first call, replays current stdout_tail as 'progress' events, then
    subscribes to live updates via periodic polling.

    Additionally, while the scan is pending/running, emits 'row-update' events
    for each new OssFinding persisted to the DB (polling-based v1).
    """
    first = True
    last_tail = ""
    last_status: str | None = None
    last_finding_ids: set[int] = set()
    last_scan_id: int | None = None

    while True:
        sess = session_factory()
        try:
            job = sess.query(ProjectOssJob).filter(ProjectOssJob.id == job_id).first()
        finally:
            sess.close()

        if job is None:
            break

        current_tail = job.stdout_tail or ""

        if first:
            first = False
            if current_tail:
                for line in current_tail.splitlines(keepends=True):
                    yield f"event: progress\ndata: {line.rstrip()}\n\n"
            last_tail = current_tail
            last_status = job.status.value
            yield f"event: status\ndata: {job.status.value}\n\n"
        elif current_tail != last_tail:
            new_lines = current_tail[len(last_tail) :]
            for line in new_lines.splitlines(keepends=True):
                yield f"event: progress\ndata: {line.rstrip()}\n\n"
            last_tail = current_tail

        if job.status.value != last_status and job.status != ProjectOssJobStatus.running:
            last_status = job.status.value
            yield f"event: status\ndata: {job.status.value}\n\n"

        scan_id = job.scan_id

        if scan_id is not None:
            if scan_id != last_scan_id:
                last_scan_id = scan_id
                last_finding_ids = set()
            sess = session_factory()
            try:
                current_findings = (
                    sess.query(OssFinding)
                    .filter(OssFinding.scan_id == scan_id)
                    .order_by(OssFinding.id)
                    .all()
                )
                new_findings = [f for f in current_findings if f.id not in last_finding_ids]
                for f in new_findings:
                    last_finding_ids.add(f.id)
                    h_input = (
                        f"{f.check_id}:{f.domain}:{f.severity.value}:{f.status.value}:{f.summary}"
                    )
                    finding_hash = hashlib.sha256(h_input.encode()).hexdigest()[:16]
                    row_payload = {
                        "check_id": f.check_id,
                        "domain": f.domain,
                        "severity": f.severity.value,
                        "status": f.status.value,
                        "summary": f.summary,
                        "auto_apply_safe": f.auto_apply_safe,
                        "auto_fix_available": f.auto_fix_available,
                        "finding_hash": finding_hash,
                    }
                    yield f"event: row-update\ndata: {json.dumps(row_payload)}\n\n"
            finally:
                sess.close()

        if job.status in (
            ProjectOssJobStatus.complete,
            ProjectOssJobStatus.error,
            ProjectOssJobStatus.cancelled,
        ):
            exit_code = job.exit_code
            pill_color: str | None = None
            if scan_id is not None:
                sess = session_factory()
                try:
                    scan = sess.query(OssScan).filter(OssScan.id == scan_id).first()
                    if scan and scan.pill_color:
                        pill_color = scan.pill_color.value
                finally:
                    sess.close()
            yield f"event: complete\ndata: {exit_code},{scan_id or ''},{pill_color or ''}\n\n"
            break

        yield f": heartbeat {datetime.now(UTC).isoformat()}\n\n"
        await asyncio.sleep(heartbeat_interval)


def recover_orphaned_jobs(session: Session) -> int:
    """Mark running jobs older than process start as error.

    Called at module load time to satisfy Invariant #3 (server-shutdown safety).
    """
    count = 0
    jobs = (
        session.query(ProjectOssJob)
        .filter(
            ProjectOssJob.status == ProjectOssJobStatus.running,
            ProjectOssJob.started_at < _PROCESS_START_UTC,
        )
        .all()
    )
    for job in jobs:
        session.query(ProjectOssJob).filter(ProjectOssJob.id == job.id).update(
            {
                "status": ProjectOssJobStatus.error,
                "error_message": "orphaned by server restart",
                "completed_at": _utcnow(),
            },
            synchronize_session=False,
        )
        count += 1
    if count:
        session.commit()
        logger.warning("Marked %d orphaned OSS job(s) as error", count)
    return count


def probe_tier1_dashboard() -> dict[str, dict[str, Any]]:
    """Wrapper around orch.oss.tool_probe.probe_tier1 for dashboard use."""
    raw = probe_tier1()
    return {
        tool: {
            "installed": status.installed,
            "version": status.version,
            "install_cmd": status.install_cmd,
        }
        for tool, status in raw.items()
    }


def compute_freshness(project_id: str, session: Session) -> dict[str, Any]:
    """Compare latest oss_scan.head_sha vs git rev-parse HEAD for the project.

    Returns dict with keys: is_fresh (bool), last_scan_sha (str|None),
    current_sha (str|None), message (str).
    """
    project = session.query(Project).filter(Project.id == project_id).first()
    if project is None:
        return {
            "is_fresh": False,
            "last_scan_sha": None,
            "current_sha": None,
            "message": "project not found",
        }

    current_sha = _git_head(project.repo_root)
    latest = (
        session.query(OssScan)
        .filter(OssScan.project_id == project_id)
        .order_by(OssScan.started_at.desc())
        .first()
    )

    last_sha = latest.head_sha if latest else None

    if last_sha is None:
        return {
            "is_fresh": False,
            "last_scan_sha": None,
            "current_sha": current_sha,
            "message": "no scans yet",
        }

    if current_sha is None:
        return {
            "is_fresh": False,
            "last_scan_sha": last_sha,
            "current_sha": None,
            "message": "git unavailable — cannot determine freshness",
        }

    is_fresh = current_sha == last_sha
    return {
        "is_fresh": is_fresh,
        "last_scan_sha": last_sha,
        "current_sha": current_sha,
        "message": "" if is_fresh else "HEAD has advanced since last scan",
    }


def latest_scan(session: Session, project_id: str) -> OssScan | None:
    """Return the most recent OssScan row for project_id, or None."""
    return (
        session.query(OssScan)
        .filter(OssScan.project_id == project_id)
        .order_by(OssScan.started_at.desc())
        .first()
    )


def get_finding_details(
    session: Session,
    project_id: str,
    finding_id: int,
    *,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any] | None:
    """Return paginated detail rows for a single OssFinding.

    Returns ``None`` if the finding does not exist or belongs to a scan in a
    different project — the caller surfaces this as a 404.

    The shape mirrors what the modal expects: ``total`` is the number of
    persisted ``oss_finding_detail`` rows (capped at the skill's
    ``RESULT_CAP``), ``capped`` echoes the flag the skill set on the parent
    finding's ``evidence_json``, and ``results`` is a paginated slice ordered
    by ``ordinal`` so the UI can show a stable list across reloads.
    """
    from orch.db.models import OssFindingDetail

    finding = (
        session.query(OssFinding)
        .join(OssScan, OssScan.id == OssFinding.scan_id)
        .filter(OssFinding.id == finding_id, OssScan.project_id == project_id)
        .first()
    )
    if finding is None:
        return None

    safe_limit = max(1, min(int(limit), 1000))
    safe_offset = max(0, int(offset))

    total = (
        session.query(OssFindingDetail).filter(OssFindingDetail.finding_id == finding_id).count()
    )
    rows = (
        session.query(OssFindingDetail)
        .filter(OssFindingDetail.finding_id == finding_id)
        .order_by(OssFindingDetail.ordinal)
        .offset(safe_offset)
        .limit(safe_limit)
        .all()
    )
    capped = bool((finding.evidence_json or {}).get("capped"))

    # Fallback for scans persisted before the canonical results-shape rollout:
    # if we have zero detail rows but the evidence_json carries a list of
    # file/path/email hits under a known legacy key, synthesize result rows so
    # the user sees *where* the issues are without having to re-run the scan.
    legacy_source = "legacy_evidence"
    fallback_rows: list[dict[str, Any]] | None = None
    if total == 0:
        fallback_rows = _legacy_evidence_to_rows(
            finding.evidence_json or {}, rule_fallback=finding.check_id
        )
    if fallback_rows:
        sliced = fallback_rows[safe_offset : safe_offset + safe_limit]
        return {
            "total": len(fallback_rows),
            "limit": safe_limit,
            "offset": safe_offset,
            "capped": capped,
            "source": legacy_source,
            "results": [{"ordinal": safe_offset + i, **row} for i, row in enumerate(sliced)],
        }
    return {
        "total": total,
        "limit": safe_limit,
        "offset": safe_offset,
        "capped": capped,
        "results": [
            {
                "ordinal": d.ordinal,
                "file": d.file_path,
                "line": d.line_number,
                "rule": d.rule_id,
                "snippet_masked": d.snippet_masked or "",
            }
            for d in rows
        ],
    }


# Keys that older scans used to dump per-hit information into evidence_json
# instead of populating the oss_finding_detail table. Order matters: the first
# hit wins, so put the most specific keys first.
_LEGACY_RG_LINE_RE = re.compile(r"^(?P<file>[^:]+):(?P<line>\d+):(?P<text>.*)$")


def _legacy_evidence_to_rows(
    evidence: dict[str, Any], *, rule_fallback: str
) -> list[dict[str, Any]]:
    """Best-effort conversion from a legacy evidence dict into result rows.

    Returns an empty list when no recognised key carries per-hit data — the
    caller falls back to the (empty) detail-table response in that case.
    """

    def _from_rg(values: list[Any]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for v in values:
            if not isinstance(v, str):
                continue
            m = _LEGACY_RG_LINE_RE.match(v)
            if m is None:
                rows.append({"file": v, "line": None, "rule": rule_fallback, "snippet_masked": ""})
                continue
            try:
                line_no: int | None = int(m.group("line"))
            except ValueError:
                line_no = None
            rows.append(
                {
                    "file": m.group("file"),
                    "line": line_no,
                    "rule": rule_fallback,
                    "snippet_masked": m.group("text").strip()[:200],
                }
            )
        return rows

    # ripgrep-style "path:line:text" lists.
    for key in ("samples", "sample_hits"):
        if isinstance(evidence.get(key), list) and evidence[key]:
            return _from_rg(evidence[key])

    # Plain string lists (file paths, contributor emails).
    for key in ("violations", "paths", "non_noreply_emails"):
        items = evidence.get(key)
        if isinstance(items, list) and items:
            return [
                {"file": str(v), "line": None, "rule": rule_fallback, "snippet_masked": ""}
                for v in items
                if isinstance(v, (str, int, float))
            ]

    # OSS-HYG-04 large blobs: [{size_bytes, path}]
    if isinstance(evidence.get("large_objects"), list):
        rows: list[dict[str, Any]] = []
        for obj in evidence["large_objects"]:
            if not isinstance(obj, dict):
                continue
            size = obj.get("size_bytes")
            try:
                size_mb = int(size) // 1024 // 1024 if size is not None else None
            except (TypeError, ValueError):
                size_mb = None
            rows.append(
                {
                    "file": str(obj.get("path") or ""),
                    "line": None,
                    "rule": rule_fallback,
                    "snippet_masked": (
                        f"{size_mb} MB blob in history" if size_mb is not None else ""
                    ),
                }
            )
        if rows:
            return rows

    # OSS-DEP-01 license-incompatible deps: [{name, license}]
    if isinstance(evidence.get("incompatible"), list):
        rows = []
        for obj in evidence["incompatible"]:
            if not isinstance(obj, dict):
                continue
            rows.append(
                {
                    "file": str(obj.get("name") or ""),
                    "line": None,
                    "rule": str(obj.get("license") or rule_fallback),
                    "snippet_masked": f"license {obj.get('license') or '?'} incompatible",
                }
            )
        if rows:
            return rows

    return []


def _format_summary(summary: dict[str, Any]) -> str:
    """Format summary dict as a compact human-readable string for the status pill."""
    must_fail = summary.get("must_fail", 0)
    should_fail = summary.get("should_fail", 0)
    info_fail = summary.get("info_fail", 0)
    total = summary.get("total", 0)
    parts = []
    if must_fail > 0:
        parts.append(f"{must_fail} MUST failure{'s' if must_fail != 1 else ''}")
    if should_fail > 0:
        parts.append(f"{should_fail} SHOULD warning{'s' if should_fail != 1 else ''}")
    if info_fail > 0:
        parts.append(f"{info_fail} INFO")
    if not parts and total > 0:
        parts.append(f"{total} checks all clear")
    return ", ".join(parts) if parts else ""


def scan_summary(session: Session, project_id: str) -> dict[str, Any]:
    """Return the AC1 contract shape for the latest scan, or a 'not yet scanned' dict.

    Shape: {scan_id, status, pill_color, summary, is_stale, stale_message, ...}
    """
    scan = latest_scan(session, project_id)
    if scan is None:
        return {
            "scan_id": None,
            "status": None,
            "pill_color": None,
            "summary": None,
            "is_stale": False,
            "stale_message": "",
        }

    freshness = compute_freshness(project_id, session)
    return {
        "scan_id": scan.id,
        "status": scan.status.value if scan.status else None,
        "pill_color": scan.pill_color.value if scan.pill_color else None,
        "summary": _format_summary(scan.summary_json) if scan.summary_json else "",
        "is_stale": not freshness["is_fresh"],
        "stale_message": freshness["message"],
        "head_sha": scan.head_sha,
    }
