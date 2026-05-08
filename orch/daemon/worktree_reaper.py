"""worktree_reaper — label-based orphan and stale container reaper.

Scans for all ``iwcore-*`` compose stacks across the host, classifies each as
active / stale / orphan, and tears down the ones that are no longer needed.

Classification logic:
  - active   : container's BatchItem exists AND status NOT IN terminal set
  - stale    : container's BatchItem exists AND status IN terminal set
  - orphan  : no BatchItem row for the container's batch_item label
  - malformed: label format is unparseable — treated as orphan

Reaper invocation:
  - Daemon startup (before main poll loop)
  - Periodic (every N poll cycles — reuse the daemon's tick mechanism)

AC5 daemon-restart re-attach is handled separately in main.py.

This module also reaps ``iw-ai-core-e2e-<item>`` browser-verification compose
stacks that the daemon's ``run_env_down_hook`` failed to clean up (daemon
crash / non-zero exit swallowed by ``|| true`` / step bypassed the normal
end-of-step path).  Those stacks carry no ``iwcore.role`` label so they are
invisible to the worktree-compose scan; they are picked up here by name.
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from sqlalchemy import select
from sqlalchemy.orm import load_only

from orch.db.models import (
    TERMINAL_BATCH_ITEM_STATUSES,
    BatchItem,
    DaemonEvent,
    WorkItem,
    WorkItemStatus,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

LABEL_ROLE = "iwcore.role"
LABEL_BATCH_ITEM = "iwcore.batch_item"
LABEL_PROJECT = "iwcore.project"

ReaperClassification = Literal["active", "stale", "orphan", "malformed"]

# COMPOSE_PROJECT_NAME convention from scripts/e2e_up.sh:
#   iw-ai-core-e2e-<work_item_id_lc> (e.g. F-00079 -> iw-ai-core-e2e-f00079)
# A trailing "-debug" or similar suffix is also tolerated (we treat the
# leading work-item portion as authoritative for classification).
_E2E_PROJECT_PREFIX = "iw-ai-core-e2e-"
_E2E_PROJECT_RE = re.compile(rf"^{re.escape(_E2E_PROJECT_PREFIX)}([a-z]+)(\d+)(?:-.*)?$")

# A WorkItem whose status is in this set has finished its lifecycle; any e2e
# compose stack still up for it is leaked and safe to reap.
_TERMINAL_WORK_ITEM_STATUSES: frozenset[WorkItemStatus] = frozenset(
    {
        WorkItemStatus.completed,
        WorkItemStatus.failed,
        WorkItemStatus.cancelled,
    }
)

# docker-compose.e2e.yml lives at the repo root.  Resolve from this file's
# location so the reaper does not depend on the daemon's cwd.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_E2E_COMPOSE_FILE = _REPO_ROOT / "docker-compose.e2e.yml"


@dataclass(frozen=True)
class E2EStackFinding:
    """A leaked browser-verification compose stack."""

    compose_project: str
    work_item_id: str | None
    classification: ReaperClassification
    container_count: int


def _parse_e2e_work_item_id(compose_project: str) -> str | None:
    """Reverse the ``iw-ai-core-e2e-<lc>`` convention back to a WorkItem id.

    Examples:
        ``iw-ai-core-e2e-f00079``       -> ``F-00079``
        ``iw-ai-core-e2e-cr00035``      -> ``CR-00035``
        ``iw-ai-core-e2e-i00073``       -> ``I-00073``
        ``iw-ai-core-e2e-f00067-debug`` -> ``F-00067``
        ``iw-ai-core-e2e-smoketest``    -> ``None`` (no numeric tail)
    """
    m = _E2E_PROJECT_RE.match(compose_project)
    if not m:
        return None
    type_prefix, num = m.groups()
    return f"{type_prefix.upper()}-{num}"


def scan_e2e_stacks() -> list[E2EStackFinding]:
    """List every active or stopped ``iw-ai-core-e2e-*`` compose project.

    Uses ``docker compose ls --all --format json`` so the result is grouped
    by compose project (one entry per stack, not per container).
    """
    try:
        result = subprocess.run(  # noqa: S603,S607
            [  # noqa: S603,S607
                "docker",
                "compose",
                "ls",
                "--all",
                "--format",
                "json",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if result.returncode != 0:
            logger.warning("[reaper] docker compose ls failed: %s", result.stderr.strip())
            return []
    except Exception as exc:
        logger.warning("[reaper] failed to list compose projects: %s", exc)
        return []

    try:
        projects = json.loads(result.stdout) if result.stdout.strip() else []
    except json.JSONDecodeError as exc:
        logger.warning("[reaper] could not parse compose ls output: %s", exc)
        return []

    findings: list[E2EStackFinding] = []
    for entry in projects:
        name = entry.get("Name", "")
        if not name.startswith(_E2E_PROJECT_PREFIX):
            continue
        # `Status` is e.g. "running(4)" or "exited(3)" — pull the integer.
        status = str(entry.get("Status", ""))
        m = re.search(r"\((\d+)\)", status)
        container_count = int(m.group(1)) if m else 0
        findings.append(
            E2EStackFinding(
                compose_project=name,
                work_item_id=_parse_e2e_work_item_id(name),
                classification="malformed",
                container_count=container_count,
            )
        )
    return findings


def classify_e2e_stack(finding: E2EStackFinding, db: Session) -> ReaperClassification:
    """Classify an e2e stack against the orchestration DB.

    The compose project name encodes only the work-item id, not its
    project_id, so we look the work item up by id alone.  If multiple
    projects shared the same work-item id (they do not in practice — ids are
    globally allocated) we would treat the stack as active until *every*
    matching item reached a terminal state.
    """
    if finding.work_item_id is None:
        return "malformed"

    rows = (
        db.execute(
            select(WorkItem)
            .options(load_only(WorkItem.project_id, WorkItem.id, WorkItem.status))
            .where(WorkItem.id == finding.work_item_id)
        )
        .scalars()
        .all()
    )
    if not rows:
        return "orphan"

    if all(row.status in _TERMINAL_WORK_ITEM_STATUSES for row in rows):
        return "stale"
    return "active"


def _reap_e2e_stack(compose_project: str) -> bool:
    """Tear down a leaked e2e stack and remove the per-project images.

    Mirrors ``scripts/e2e_down.sh`` but is invoked directly from the reaper —
    we cannot call the script because we do not have a worktree cwd nor the
    ``COMPOSE_PROJECT_NAME`` env var the script expects.
    """
    cmd = [
        "docker",
        "compose",
    ]
    if _E2E_COMPOSE_FILE.is_file():
        cmd.extend(["-f", str(_E2E_COMPOSE_FILE)])
    cmd.extend(
        [
            "-p",
            compose_project,
            "down",
            "--remove-orphans",
            "--volumes",
            "--rmi",
            "local",
            "--timeout",
            "20",
        ]
    )
    try:
        result = subprocess.run(  # noqa: S603,S607
            cmd,  # noqa: S603,S607
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )
    except Exception as exc:
        logger.warning("[reaper] e2e down errored for %s: %s", compose_project, exc)
        return False
    if result.returncode != 0:
        logger.warning(
            "[reaper] e2e down exited %d for %s: %s",
            result.returncode,
            compose_project,
            result.stderr.strip(),
        )
        return False

    # `--rmi local` only removes the *currently tagged* per-project images.
    # Each `e2e_up.sh --build` cycle however orphans the previous build
    # (the new layer steals the tag); those untagged remnants still carry
    # the com.docker.compose.project label.  Sweep them by label so the
    # disk does not bloat by ~2 GB per fix-cycle re-provision.
    _prune_e2e_label_remnants(compose_project)
    return True


def _prune_e2e_label_remnants(compose_project: str) -> None:
    """Best-effort: delete any images still labelled with this compose project.

    Idempotent and silent — runs after a successful ``compose down`` to mop
    up dangling images that ``--rmi local`` left behind.  Failures are
    logged at debug level only; the caller treats teardown as successful
    regardless because the containers are already gone.
    """
    try:
        listing = subprocess.run(  # noqa: S603,S607
            [  # noqa: S603,S607
                "docker",
                "images",
                "-a",
                "--filter",
                f"label=com.docker.compose.project={compose_project}",
                "-q",
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except Exception as exc:
        logger.debug("[reaper] image label scan errored for %s: %s", compose_project, exc)
        return
    if listing.returncode != 0:
        logger.debug(
            "[reaper] image label scan exited %d for %s: %s",
            listing.returncode,
            compose_project,
            listing.stderr.strip(),
        )
        return
    image_ids = [line.strip() for line in listing.stdout.splitlines() if line.strip()]
    if not image_ids:
        return
    try:
        subprocess.run(  # noqa: S603,S607
            ["docker", "rmi", "-f", *image_ids],  # noqa: S603,S607
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except Exception as exc:
        logger.debug(
            "[reaper] failed to prune %d label-leftover image(s) for %s: %s",
            len(image_ids),
            compose_project,
            exc,
        )
        return
    logger.info(
        "[reaper] pruned %d label-leftover image(s) for %s",
        len(image_ids),
        compose_project,
    )


def reap_e2e_stacks(db: Session) -> list[E2EStackFinding]:
    """Reap leaked browser-verification compose stacks.

    Counterpart to :func:`reap` for ``iw-ai-core-e2e-*`` projects, which the
    worktree-label scan cannot see.  Stale/orphan/malformed stacks are torn
    down with image cleanup; active stacks are left alone.
    """
    findings = scan_e2e_stacks()
    reaped: list[E2EStackFinding] = []

    for finding in findings:
        actual = classify_e2e_stack(finding, db)
        if actual == "active":
            logger.debug(
                "[reaper] e2e stack %s is active (work_item=%s)",
                finding.compose_project,
                finding.work_item_id,
            )
            continue

        logger.info(
            "[reaper] reaping e2e stack %s (classification=%s, work_item=%s, containers=%d)",
            finding.compose_project,
            actual,
            finding.work_item_id,
            finding.container_count,
        )

        ok = _reap_e2e_stack(finding.compose_project)
        if not ok:
            # Keep going; emit no DaemonEvent for failed reaps so we retry on the next tick.
            continue

        reaped_finding = E2EStackFinding(
            compose_project=finding.compose_project,
            work_item_id=finding.work_item_id,
            classification=actual,
            container_count=finding.container_count,
        )
        reaped.append(reaped_finding)

        try:
            event = DaemonEvent(
                project_id=None,
                event_type="worktree_compose",
                entity_id=finding.work_item_id or finding.compose_project,
                entity_type="work_item",
                message=(
                    f"Reaped {actual} e2e stack {finding.compose_project} "
                    f"({finding.container_count} container(s))"
                ),
                event_metadata={
                    "phase": "reap_e2e",
                    "classification": actual,
                    "compose_project": finding.compose_project,
                    "work_item_id": finding.work_item_id,
                    "container_count": finding.container_count,
                },
            )
            db.add(event)
            db.commit()
        except Exception as exc:
            logger.warning("[reaper] failed to emit e2e reap event: %s", exc)
            db.rollback()

    return reaped


@dataclass(frozen=True)
class ReaperFinding:
    container_id: str
    batch_item_id: str | None
    project_id: str | None
    classification: ReaperClassification
    labels: dict[str, str]


def scan() -> list[ReaperFinding]:
    """Scan all containers with ``iwcore.role`` label.

    Runs: docker ps -a --filter label=iwcore.role --format '{{json .}}'
    Parses each line as JSON to extract container ID and full Labels dict.
    Returns a list of ReaperFinding objects.
    """
    try:
        result = subprocess.run(  # noqa: S603,S607
            [  # noqa: S603,S607
                "docker",
                "ps",
                "-a",
                "--filter",
                f"label={LABEL_ROLE}",
                "--format",
                "{{json .}}",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if result.returncode != 0:
            logger.warning("[reaper] docker ps failed: %s", result.stderr.strip())
            return []
    except Exception as exc:
        logger.warning("[reaper] failed to scan containers: %s", exc)
        return []

    findings: list[ReaperFinding] = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            logger.debug("[reaper] skipping unparseable docker output: %r", line)
            continue

        container_id = parsed.get("ID", "")
        labels_raw = parsed.get("Labels", "")

        if isinstance(labels_raw, str):
            labels: dict[str, str] = {}
            for entry in labels_raw.split(","):
                entry = entry.strip()
                if "=" in entry:
                    k, v = entry.split("=", 1)
                    labels[k.strip()] = v.strip()
        elif isinstance(labels_raw, dict):
            labels = labels_raw
        else:
            labels = {}

        batch_item_id: str | None = labels.get(LABEL_BATCH_ITEM)
        project_id: str | None = labels.get(LABEL_PROJECT)

        findings.append(
            ReaperFinding(
                container_id=container_id,
                batch_item_id=batch_item_id,
                project_id=project_id,
                classification="malformed",
                labels=labels,
            )
        )

    return findings


def _is_valid_batch_item_id(value: str) -> bool:
    """Return True if value looks like a valid batch item ID (e.g., F-00062)."""
    if not value:
        return False
    return bool(__import__("re").match(r"^[A-Z]+-\d+$", value))


def classify(finding: ReaperFinding, db: Session) -> ReaperClassification:
    """Classify a container finding based on DB state.

    The ``LABEL_BATCH_ITEM`` label stores ``BatchItem.id`` (integer PK),
    not ``work_item_id``.

    - No matching BatchItem row -> orphan
    - BatchItem.status in terminal set -> stale
    - Otherwise -> active
    """
    if finding.batch_item_id is None:
        return "malformed"

    try:
        batch_item_pk = int(finding.batch_item_id)
    except (ValueError, TypeError):
        return "malformed"

    row = db.get(BatchItem, batch_item_pk)

    if row is None:
        return "orphan"

    if row.status in TERMINAL_BATCH_ITEM_STATUSES:
        return "stale"

    return "active"


def reap(db: Session) -> list[ReaperFinding]:
    """Reap all stale, orphan, and malformed containers.

    Calls worktree_compose.down() for each non-active finding.
    Emits a DaemonEvent for each reap with classification info.
    Returns the list of reaped findings.
    """
    from orch.daemon import worktree_compose

    findings = scan()
    reaped: list[ReaperFinding] = []

    for finding in findings:
        prior_classification = finding.classification
        actual_classification = classify(finding, db)

        if actual_classification == "active":
            logger.debug(
                "[reaper] %s is active (batch_item=%s)",
                finding.container_id,
                finding.batch_item_id,
            )
            continue

        logger.info(
            "[reaper] reaping %s (classification=%s, batch_item=%s)",
            finding.container_id,
            actual_classification,
            finding.batch_item_id,
        )

        down_id = finding.batch_item_id or f"malformed-{finding.container_id[:12]}"
        try:
            worktree_compose.down(down_id, None)
        except Exception as exc:
            logger.warning(
                "[reaper] failed to reap %s: %s",
                finding.container_id,
                exc,
            )

        reaped_finding = ReaperFinding(
            container_id=finding.container_id,
            batch_item_id=finding.batch_item_id,
            project_id=finding.project_id,
            classification=actual_classification,
            labels=finding.labels,
        )
        reaped.append(reaped_finding)

        try:
            event = DaemonEvent(
                project_id=finding.project_id,
                event_type="worktree_compose",
                entity_id=down_id,
                entity_type="batch_item",
                message=f"Reaped {actual_classification} container {finding.container_id}",
                event_metadata={
                    "phase": "reap",
                    "classification": actual_classification,
                    "prior_classification": prior_classification,
                    "container_id": finding.container_id,
                    "labels": finding.labels,
                },
            )
            db.add(event)
            db.commit()
        except Exception as exc:
            logger.warning("[reaper] failed to emit reap event: %s", exc)
            db.rollback()

    # Also sweep iw-ai-core-e2e-* browser-verification stacks that the
    # per-step env_down hook failed to clean up.  These stacks carry no
    # iwcore.role label so the scan() above misses them entirely.
    try:
        reap_e2e_stacks(db)
    except Exception:
        logger.exception("[reaper] e2e stack sweep failed — continuing")

    return reaped
