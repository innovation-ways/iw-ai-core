"""Coverage view-model service — reads pytest-cov JSON output for the dashboard."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PackageRow:
    name: str
    line_pct: float
    branch_pct: float | None
    missing_lines: int
    badge: str


@dataclass(frozen=True)
class FileRow:
    path: str
    line_pct: float
    branch_pct: float | None
    missing_lines: int
    badge: str


@dataclass(frozen=True)
class CoverageView:
    available: bool
    error: str | None
    overall_line_pct: float | None
    overall_branch_pct: float | None
    threshold: int
    gap_pct: float | None
    mtime_iso: str | None
    test_count: int | None
    packages: list[PackageRow] = field(default_factory=list)
    files_by_package: dict[str, list[FileRow]] = field(default_factory=dict)


def _badge(line_pct: float, threshold: int) -> str:
    if line_pct >= threshold:
        return "green"
    if line_pct >= threshold - 10:
        return "amber"
    return "red"


def _read_fail_under(pyproject_path: Path) -> int:
    import tomllib

    try:
        with pyproject_path.open("rb") as f:
            data = tomllib.load(f)
    except Exception:
        return 0

    try:
        return int(data["tool"]["coverage"]["report"]["fail_under"])
    except Exception:
        return 0


def load_coverage(
    coverage_json_path: Path = Path("tests/output/coverage/coverage.json"),
    pyproject_path: Path = Path("pyproject.toml"),
) -> CoverageView:
    threshold = _read_fail_under(pyproject_path)

    if not coverage_json_path.exists():
        return CoverageView(
            available=False,
            error=None,
            threshold=threshold,
            overall_line_pct=None,
            overall_branch_pct=None,
            gap_pct=None,
            mtime_iso=None,
            test_count=None,
        )

    mtime_iso: str | None = None
    try:
        mtime = coverage_json_path.stat().st_mtime
        mtime_iso = datetime.fromtimestamp(mtime, tz=UTC).isoformat()
    except Exception as exc:
        logger.debug("Could not read coverage.json mtime: %s", exc)

    try:
        with coverage_json_path.open() as f:
            data = json.load(f)
    except Exception as exc:
        logger.warning("Failed to parse %s: %s", coverage_json_path, exc)
        return CoverageView(
            available=False,
            error=str(exc),
            threshold=threshold,
            overall_line_pct=None,
            overall_branch_pct=None,
            gap_pct=None,
            mtime_iso=mtime_iso,
            test_count=None,
        )

    totals = data.get("totals", {})
    overall_line_pct = totals.get("percent_covered")
    overall_branch_pct = totals.get("branch_percent_covered")
    test_count = totals.get("num_statements_covered")
    gap_pct = None
    if overall_line_pct is not None:
        gap_pct = overall_line_pct - threshold

    files_map: dict[str, Any] = data.get("files", {})

    package_files: dict[str, list[FileRow]] = {}
    package_agg: dict[str, list[float]] = {}

    for file_path, file_data in files_map.items():
        if "/" not in file_path:
            continue
        package_name = file_path.split("/")[0]
        summary = file_data.get("summary", {})
        line_pct = summary.get("percent_covered", 0.0)
        branch_pct = summary.get("branch_percent_covered")
        missing_lines = summary.get("missing_lines", 0)

        file_row = FileRow(
            path=file_path,
            line_pct=line_pct,
            branch_pct=branch_pct,
            missing_lines=missing_lines,
            badge=_badge(line_pct, threshold),
        )
        package_files.setdefault(package_name, []).append(file_row)
        package_agg.setdefault(package_name, []).append(line_pct)

    packages: list[PackageRow] = []
    for name, line_list in package_agg.items():
        line_pct = sum(line_list) / len(line_list) if line_list else 0.0
        branch_pct = None
        total_missing = sum(f.missing_lines for f in package_files.get(name, []))
        packages.append(
            PackageRow(
                name=name,
                line_pct=line_pct,
                branch_pct=branch_pct,
                missing_lines=total_missing,
                badge=_badge(line_pct, threshold),
            ),
        )

    packages.sort(key=lambda p: p.name)

    return CoverageView(
        available=True,
        error=None,
        overall_line_pct=overall_line_pct,
        overall_branch_pct=overall_branch_pct,
        threshold=threshold,
        gap_pct=gap_pct,
        mtime_iso=mtime_iso,
        test_count=test_count,
        packages=packages,
        files_by_package=package_files,
    )
