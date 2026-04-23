"""OSS compliance dashboard service.

Enqueues ProjectOssJob rows, spawns `uv run iw oss …` subprocesses, provisions
throwaway worktrees for prepare/publish, streams stdout to the DB, and exposes
helpers for Tier-1 probe + freshness computation.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import subprocess
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sqlalchemy.exc import SQLAlchemyError

from orch.db.models import OssScan, Project, ProjectOssJob, ProjectOssJobKind, ProjectOssJobStatus
from orch.oss.tool_probe import probe_tier1

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable
    from asyncio import StreamReader
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_STDOUT_TAIL_BYTES = 16 * 1024

_PROCESS_START_UTC = datetime.now(UTC)

WORKTREE_KINDS = frozenset({ProjectOssJobKind.prepare, ProjectOssJobKind.publish})


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _truncate_tail(content: str) -> str:
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
        sess.query(ProjectOssJob).filter(ProjectOssJob.id == job_id).update(
            {
                "exit_code": exit_code,
                "stdout_tail": tail,
                "completed_at": _utcnow(),
                **(
                    {"scan_id": latest.id}
                    if (
                        latest := (
                            sess.query(OssScan)
                            .filter(OssScan.project_id == project.id)
                            .order_by(OssScan.started_at.desc())
                            .first()
                        )
                    )
                    is not None
                    else {}
                ),
                "status": ProjectOssJobStatus.complete
                if exit_code == 0
                else ProjectOssJobStatus.error,
                **(
                    {"error_message": f"Subprocess exited with code {exit_code}"}
                    if exit_code not in (0, 2)
                    else {}
                ),
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


async def _run_worktree(
    project: Project,
    job_id: int,
    kind: ProjectOssJobKind,
    session_factory: Callable[[], Session],
) -> None:
    worktree_path = Path(f"/tmp/oss-{uuid.uuid4()}")
    sess = session_factory()
    try:
        sess.query(ProjectOssJob).filter(ProjectOssJob.id == job_id).update(
            {"worktree_path": str(worktree_path)}, synchronize_session=False
        )
        sess.commit()
    finally:
        sess.close()

    git_path = Path(
        subprocess.run(["git", "which", "git"], capture_output=True, text=True).stdout.strip()
        or "git"
    )

    try:
        add_proc = await asyncio.create_subprocess_exec(
            str(git_path),
            "worktree",
            "add",
            str(worktree_path),
            "HEAD",
            cwd=project.repo_root,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        await add_proc.wait()
    except Exception as exc:
        logger.warning("Failed to create worktree for job %s: %s", job_id, exc)

    action = "prepare" if kind == ProjectOssJobKind.prepare else "publish"
    cmd = ["uv", "run", "iw", "oss", action, "--project", project.id]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(worktree_path),
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
                    {"error_message": f"{action} exited with code {exit_code}"}
                    if exit_code != 0
                    else {}
                ),
            },
            synchronize_session=False,
        )
        sess.commit()
    finally:
        sess.close()

    try:
        rm_proc = await asyncio.create_subprocess_exec(
            str(git_path),
            "worktree",
            "remove",
            "--force",
            str(worktree_path),
            cwd=project.repo_root,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        await rm_proc.wait()
    except Exception as exc:
        logger.warning("Failed to remove worktree %s for job %s: %s", worktree_path, job_id, exc)


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
        elif job.kind in WORKTREE_KINDS:
            await _run_worktree(project, job_id, job.kind, session_factory)
        elif job.kind == ProjectOssJobKind.install:
            await _run_install(project, job_id, session_factory)
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
    """Cancel a running job: SIGTERM, wait, SIGKILL if needed; clean up worktree."""
    job = session.query(ProjectOssJob).filter(ProjectOssJob.id == job_id).first()
    if job is None:
        return

    if job.status not in (ProjectOssJobStatus.running, ProjectOssJobStatus.queued):
        return

    worktree_path = job.worktree_path

    session.query(ProjectOssJob).filter(ProjectOssJob.id == job_id).update(
        {"status": ProjectOssJobStatus.cancelled}, synchronize_session=False
    )
    session.commit()

    if job.status == ProjectOssJobStatus.running:
        try:
            pid_file = Path(f"/tmp/oss-job-{job_id}.pid")
            if pid_file.exists():
                pid = int(pid_file.read_text().strip())
                try:
                    os.kill(pid, signal.SIGTERM)
                    await asyncio.sleep(2)
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                except ProcessLookupError:
                    pass
                pid_file.unlink(missing_ok=True)
        except Exception as exc:
            logger.warning("Error sending SIGTERM to job %s: %s", job_id, exc)

    if worktree_path:
        git_path = Path(
            subprocess.run(["git", "which", "git"], capture_output=True, text=True).stdout.strip()
            or "git"
        )
        try:
            rm_proc = await asyncio.create_subprocess_exec(
                str(git_path),
                "worktree",
                "remove",
                "--force",
                worktree_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            await rm_proc.wait()
        except Exception as exc:
            logger.warning(
                "Failed to remove worktree %s during cancel for job %s: %s",
                worktree_path,
                job_id,
                exc,
            )


def enqueue_job(session: Session, project_id: str, kind: ProjectOssJobKind | str) -> ProjectOssJob:
    """Create a new ProjectOssJob row with status=queued."""
    if isinstance(kind, str):
        kind = ProjectOssJobKind(kind)
    job = ProjectOssJob(
        project_id=project_id,
        kind=kind,
        status=ProjectOssJobStatus.queued,
    )
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
    """
    first = True
    last_tail = ""
    last_status: str | None = None

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

        if job.status in (
            ProjectOssJobStatus.complete,
            ProjectOssJobStatus.error,
            ProjectOssJobStatus.cancelled,
        ):
            scan_id = job.scan_id
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
    """Mark running jobs older than process start as error; clean up worktrees.

    Called at module load time to satisfy Invariant #3 (server-shutdown safety).
    """
    count = 0
    git_path = Path(
        subprocess.run(["git", "which", "git"], capture_output=True, text=True).stdout.strip()
        or "git"
    )
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
        if job.worktree_path:
            worktree = Path(job.worktree_path)
            if worktree.exists():
                try:
                    subprocess.run(
                        [str(git_path), "worktree", "remove", "--force", str(worktree)],
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                except Exception as exc:
                    logger.warning("Failed to cleanup orphaned worktree %s: %s", worktree, exc)
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


def scan_summary(session: Session, project_id: str) -> dict[str, Any]:
    """Return the AC1 contract shape for the latest scan, or a 'not yet scanned' dict.

    Shape: {scan_id, pill_color, summary, is_stale, stale_message, ...}
    """
    scan = latest_scan(session, project_id)
    if scan is None:
        return {
            "scan_id": None,
            "pill_color": None,
            "summary": None,
            "is_stale": False,
            "stale_message": "",
        }

    freshness = compute_freshness(project_id, session)
    return {
        "scan_id": scan.id,
        "pill_color": scan.pill_color.value if scan.pill_color else None,
        "summary": scan.summary_json,
        "is_stale": not freshness["is_fresh"],
        "stale_message": freshness["message"],
        "head_sha": scan.head_sha,
    }
