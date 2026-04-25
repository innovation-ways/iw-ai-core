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
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from orch.db.models import TERMINAL_BATCH_ITEM_STATUSES, BatchItem, DaemonEvent

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

LABEL_ROLE = "iwcore.role"
LABEL_BATCH_ITEM = "iwcore.batch_item"
LABEL_PROJECT = "iwcore.project"

ReaperClassification = Literal["active", "stale", "orphan", "malformed"]


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

    return reaped
