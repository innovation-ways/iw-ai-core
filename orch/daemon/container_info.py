"""container_info — read-only per-worktree Docker container inspection.

Scans all containers labelled ``iwcore.role=per-worktree``, groups them into
compose stacks (one stack per BatchItem), and enriches each stack with
BatchItem data from the database.

This module is intentionally read-only — no containers are created, modified,
or removed. Teardown is handled by worktree_reaper and worktree_compose.
"""

from __future__ import annotations

import contextlib
import json
import logging
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from orch.daemon.worktree_reaper import LABEL_BATCH_ITEM, LABEL_PROJECT, LABEL_ROLE
from orch.db.models import TERMINAL_BATCH_ITEM_STATUSES, BatchItem

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_DOCKER_TIME_FORMATS = (
    "%Y-%m-%d %H:%M:%S %z",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S%z",
)


def _parse_docker_time(raw: str) -> datetime | None:
    s = raw.replace(" UTC", "").strip()
    for fmt in _DOCKER_TIME_FORMATS:
        try:
            dt = datetime.strptime(s, fmt)  # noqa: DTZ007
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            return dt
        except ValueError:
            continue
    return None


def _parse_labels(raw: str | dict[str, Any]) -> dict[str, str]:
    if isinstance(raw, dict):
        return raw
    labels: dict[str, str] = {}
    if not isinstance(raw, str):
        return labels
    for entry in raw.split(","):
        entry = entry.strip()
        if "=" in entry:
            k, v = entry.split("=", 1)
            labels[k.strip()] = v.strip()
    return labels


@dataclass
class ContainerService:
    name: str
    container_id: str
    image: str
    state: str  # running / exited / paused / dead / created
    status_text: str  # "Up 2 hours", "Exited (1) 3 hours ago"
    ports: str


@dataclass
class ContainerStack:
    compose_project: str
    batch_item_pk: int | None
    item_id: str | None
    project_id: str | None
    services: list[ContainerService] = field(default_factory=list)
    classification: str = "malformed"  # active / stale / orphan / malformed
    created_at: datetime | None = None

    @property
    def age_secs(self) -> float:
        if self.created_at is None:
            return 0.0
        return (datetime.now(UTC) - self.created_at).total_seconds()

    @property
    def age_display(self) -> str:
        secs = int(self.age_secs)
        if secs < 60:
            return f"{secs}s"
        if secs < 3600:
            return f"{secs // 60}m"
        if secs < 86400:
            h, m = secs // 3600, (secs % 3600) // 60
            return f"{h}h {m:02d}m"
        d, h = secs // 86400, (secs % 86400) // 3600
        return f"{d}d {h}h"

    @property
    def all_running(self) -> bool:
        return bool(self.services) and all(s.state == "running" for s in self.services)

    @property
    def any_unhealthy(self) -> bool:
        return any(s.state not in ("running", "created") for s in self.services)

    @property
    def service_summary(self) -> str:
        return ", ".join(f"{s.name}={s.state}" for s in self.services)

    @property
    def all_ports(self) -> str:
        seen: list[str] = []
        for svc in self.services:
            for p in svc.ports.split(","):
                p = p.strip()
                if p and p not in seen:
                    seen.append(p)
        return ", ".join(seen) if seen else "—"


def scan_stacks(db: Session) -> list[ContainerStack]:
    """Return one ContainerStack per iwcore-* compose project, sorted oldest-first."""
    raw = _docker_ps_all()
    if not raw:
        return []

    groups: dict[str, list[dict[str, Any]]] = {}
    for c in raw:
        labels = _parse_labels(c.get("Labels", ""))
        project = labels.get("com.docker.compose.project") or (
            f"iwcore-{labels[LABEL_BATCH_ITEM]}"
            if LABEL_BATCH_ITEM in labels
            else f"unlabelled-{c.get('ID', 'x')[:8]}"
        )
        groups.setdefault(project, []).append(c)

    stacks: list[ContainerStack] = []
    for compose_project, containers in groups.items():
        first_labels = _parse_labels(containers[0].get("Labels", ""))
        batch_item_id_raw = first_labels.get(LABEL_BATCH_ITEM)
        project_id: str | None = first_labels.get(LABEL_PROJECT)

        batch_item_pk: int | None = None
        with contextlib.suppress(ValueError, TypeError):
            if batch_item_id_raw is not None:
                batch_item_pk = int(batch_item_id_raw)

        classification = "malformed"
        item_id: str | None = None
        if batch_item_pk is not None:
            row = db.get(BatchItem, batch_item_pk)
            if row is None:
                classification = "orphan"
            elif row.status in TERMINAL_BATCH_ITEM_STATUSES:
                classification = "stale"
                item_id = row.work_item_id
                project_id = project_id or row.project_id
            else:
                classification = "active"
                item_id = row.work_item_id
                project_id = project_id or row.project_id

        services: list[ContainerService] = []
        oldest: datetime | None = None
        for c in containers:
            labels = _parse_labels(c.get("Labels", ""))
            svc_name = labels.get("com.docker.compose.service", "unknown")
            created = _parse_docker_time(c.get("CreatedAt", ""))
            if created and (oldest is None or created < oldest):
                oldest = created
            services.append(
                ContainerService(
                    name=svc_name,
                    container_id=c.get("ID", "")[:12],
                    image=c.get("Image", ""),
                    state=(c.get("State") or "unknown").lower(),
                    status_text=c.get("Status", ""),
                    ports=c.get("Ports", ""),
                )
            )
        services.sort(key=lambda s: s.name)

        stacks.append(
            ContainerStack(
                compose_project=compose_project,
                batch_item_pk=batch_item_pk,
                item_id=item_id,
                project_id=project_id,
                services=services,
                classification=classification,
                created_at=oldest,
            )
        )

    stacks.sort(key=lambda s: s.age_secs, reverse=True)
    return stacks


def remove_stack(compose_project: str) -> tuple[bool, str]:
    """Tear down a compose stack by project name (docker compose down -v).

    Should only be called for stale or orphan stacks.  No validation is
    performed here — the caller is responsible for checking classification
    before invoking.
    """
    try:
        result = subprocess.run(  # noqa: S603
            [  # noqa: S607
                "docker",
                "compose",
                "-p",
                compose_project,
                "down",
                "-v",
                "--remove-orphans",
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        if result.returncode != 0:
            return False, result.stderr.strip()
        return True, ""
    except Exception as exc:
        return False, str(exc)


def _docker_ps_all() -> list[dict[str, Any]]:
    try:
        result = subprocess.run(  # noqa: S603
            [  # noqa: S607
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
            logger.warning("[container_info] docker ps failed: %s", result.stderr.strip())
            return []
    except Exception as exc:
        logger.warning("[container_info] docker query failed: %s", exc)
        return []

    rows: list[dict[str, Any]] = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        with contextlib.suppress(json.JSONDecodeError):
            rows.append(json.loads(line))
    return rows
