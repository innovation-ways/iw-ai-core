"""Async subprocess orchestration for OSS compliance scanning."""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from orch.oss import persistence

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy.orm import Session

    from orch.db.models import Project

from orch.db.models import OssScan, OssScanMode, OssScanStatus

logger = logging.getLogger(__name__)


async def run_scan(
    project: Project,
    mode: str = "scan",
    *,
    session_factory: Callable[[], Session],
    skill_scan_path: Path,
) -> OssScan:
    """Run the iw-oss-publish orchestrator against project.repo_path.

    - Creates an oss_scan row with status='pending' and captures head_sha
      (via `git rev-parse HEAD` in the project dir) BEFORE starting the subprocess.
    - Starts a subprocess: `python3 {skill_scan_path} --target {project.repo_path}
      --mode {mode} --no-tool-check`
    - Streams stdout/stderr; on completion reads
      `{project.repo_path}/.iw/oss-publish-findings.json` and calls
      persistence.persist_findings() to populate oss_finding + oss_tool_run rows.
    - Sets oss_scan.status='complete', exit_code, pill_color (per invariant #3
      in the design doc), summary_json, completed_at.
    - On subprocess error (non-2 exit), sets status='error', error_message.
    - Returns the updated OssScan row.
    """
    session = session_factory()

    head_sha = _get_git_head(project.repo_root)

    scan = OssScan(
        project_id=project.id,
        status=OssScanStatus.pending,
        mode=OssScanMode(mode),
        head_sha=head_sha,
    )
    session.add(scan)
    session.flush()

    try:
        logger.info("Starting OSS scan for project %s (mode=%s)", project.id, mode)
        logger.info("  skill_scan_path=%s", skill_scan_path)
        logger.info("  target=%s", project.repo_root)

        proc = await asyncio.create_subprocess_exec(
            "python3",
            str(skill_scan_path),
            "--target",
            project.repo_root,
            "--mode",
            mode,
            "--no-tool-check",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

        scan.status = OssScanStatus.running
        session.flush()

        stdout_lines: list[str] = []
        stdout = proc.stdout
        while stdout is not None:
            line = await stdout.readline()
            if not line:
                break
            decoded = line.decode("utf-8", errors="replace")
            stdout_lines.append(decoded)
            logger.debug("scan: %s", decoded.rstrip())

        exit_code = await proc.wait()

        if exit_code == 2:
            findings_path = Path(project.repo_root) / ".iw" / "oss-publish-findings.json"
            if findings_path.exists():
                findings_json = json.loads(findings_path.read_text())
                summary = findings_json.get("summary", {})
                pill_color_str = persistence.compute_pill_color(summary)
                findings_json["head_sha"] = head_sha
                persistence.persist_findings(session, scan, findings_json)
                from orch.db.models import OssPillColor

                scan.pill_color = OssPillColor(pill_color_str)
                scan.summary_json = summary
            scan.status = OssScanStatus.complete
            scan.exit_code = exit_code
            scan.completed_at = datetime.now(UTC)
            session.commit()
            return scan

        scan.status = OssScanStatus.error
        scan.exit_code = exit_code
        scan.error_message = f"Subprocess exited with code {exit_code}"
        scan.completed_at = datetime.now(UTC)
        session.commit()
        return scan

    except Exception as exc:
        logger.exception("OSS scan failed for project %s", project.id)
        scan.status = OssScanStatus.error
        scan.error_message = str(exc)
        scan.completed_at = datetime.now(UTC)
        session.commit()
        return scan


def _get_git_head(repo_root: str) -> str | None:
    git_path = shutil.which("git")
    if git_path is None:
        return None
    try:
        result = subprocess.run(  # noqa: S603
            [git_path, "rev-parse", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        logger.exception("Failed to get git HEAD for %s", repo_root)
    return None
