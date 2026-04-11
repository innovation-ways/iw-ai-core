"""Shared helpers for test and quality gate routers."""

from __future__ import annotations

import json
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import HTTPException
from fastapi.responses import Response
from sqlalchemy import select

from orch.db.models import Project, TestRun

if TYPE_CHECKING:
    from datetime import datetime

    from sqlalchemy.orm import Session


def get_project_or_404(project_id: str, db: Session) -> Project:
    project = db.scalar(select(Project).where(Project.id == project_id))
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    return project


def action_response(
    message: str,
    toast_type: str = "success",
    *,
    reload: bool = False,
) -> Response:
    """Return 204 with HX-Trigger header to show a toast."""
    toast: dict[str, Any] = {"message": message, "type": toast_type}
    if reload:
        toast["reload"] = True
    trigger = json.dumps({"showToast": toast})
    return Response(
        status_code=204,
        headers={
            "HX-Trigger": trigger,
            "HX-Refresh": "false",
        },
    )


@dataclass
class CategoryCard:
    """A card representing a test or quality gate category."""

    key: str
    label: str
    description: str
    command: str
    group: str = ""
    bundle: bool = False
    last_run: TestRun | None = None


@dataclass
class RunRow:
    """A row in the runs history table."""

    id: int
    category: str
    status: str
    command: str
    duration_secs: float | None
    started_at: datetime | None
    finished_at: datetime | None
    exit_code: int | None
    has_report: bool
    has_log: bool


def build_category_cards(
    project_id: str,
    config_section: dict[str, Any],
    db: Session,
    *,
    run_type: str = "test",
) -> list[CategoryCard]:
    """Build category cards with last run info."""
    categories = config_section.get("categories", {})
    cards = []
    for key, cat in categories.items():
        last_run = db.scalar(
            select(TestRun)
            .where(
                TestRun.project_id == project_id,
                TestRun.category == key,
                TestRun.run_type == run_type,
            )
            .order_by(TestRun.created_at.desc())
            .limit(1)
        )
        cards.append(
            CategoryCard(
                key=key,
                label=cat.get("label", key),
                description=cat.get("description", ""),
                command=cat.get("command", ""),
                group=cat.get("group", ""),
                bundle=cat.get("bundle", False),
                last_run=last_run,
            )
        )
    return cards


def build_run_rows(project_id: str, db: Session, *, run_type: str = "test") -> list[RunRow]:
    """Build run rows for the runs table, filtered by run_type."""
    runs = list(
        db.scalars(
            select(TestRun)
            .where(TestRun.project_id == project_id, TestRun.run_type == run_type)
            .order_by(TestRun.created_at.desc())
            .limit(50)
        )
    )
    return [
        RunRow(
            id=r.id,
            category=r.category,
            status=r.status.value,
            command=r.command,
            duration_secs=r.duration_secs,
            started_at=r.started_at,
            finished_at=r.finished_at,
            exit_code=r.exit_code,
            has_report=bool(r.allure_report_dir and Path(r.allure_report_dir).is_dir()),
            has_log=bool(r.log_path and Path(r.log_path).is_file()),
        )
        for r in runs
    ]


def group_cards(cards: list[CategoryCard]) -> list[tuple[str, list[CategoryCard]]]:
    """Group cards by their group field, preserving config order.

    Cards without a group go into "" (rendered without a header).
    The "suites" group always sorts last.
    """
    groups: OrderedDict[str, list[CategoryCard]] = OrderedDict()
    for card in cards:
        groups.setdefault(card.group, []).append(card)
    # Move "suites" group to end if present
    if "suites" in groups:
        suites = groups.pop("suites")
        groups["suites"] = suites
    return list(groups.items())
