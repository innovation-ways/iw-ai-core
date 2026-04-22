"""DB persistence for OSS scan findings."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from orch.db.models import (
    OssFinding,
    OssFindingSeverity,
    OssFindingStatus,
    OssScan,
    OssToolRun,
    OssToolRunStatus,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def persist_findings(
    session: Session,
    scan: OssScan,
    findings_json: dict[str, Any],
) -> None:
    findings = findings_json.get("findings", [])
    for f in findings:
        severity_raw = f.get("severity", "INFO")
        try:
            severity = OssFindingSeverity[severity_raw]
        except KeyError:
            severity = OssFindingSeverity.INFO

        status_raw = f.get("status", "fail")
        try:
            status = OssFindingStatus(status_raw)
        except ValueError:
            status_map = {
                "pass": OssFindingStatus.pass_status,
                "fail": OssFindingStatus.fail,
                "skip": OssFindingStatus.skip,
                "human_required": OssFindingStatus.human_required,
            }
            status = status_map.get(status_raw, OssFindingStatus.fail)

        evidence = f.get("evidence")
        evidence_json = evidence if isinstance(evidence, dict) else None

        finding = OssFinding(
            scan_id=scan.id,
            check_id=f.get("id", "UNKNOWN"),
            severity=severity,
            status=status,
            domain=f.get("domain", "unknown"),
            summary=f.get("summary", ""),
            detail=f.get("detail"),
            remediation=f.get("remediation"),
            auto_fix_available=f.get("auto_fix_available", False),
            osps_control=f.get("osps_control"),
            tool=f.get("tool"),
            evidence_json=evidence_json,
        )
        session.add(finding)

    tools_available = findings_json.get("tools_available", {})
    for tool_name, version in tools_available.items():
        tool_run = OssToolRun(
            scan_id=scan.id,
            tool=tool_name,
            version=version,
            status=OssToolRunStatus.ok,
            started_at=datetime.now(UTC),
        )
        session.add(tool_run)

    session.commit()


def compute_pill_color(summary: dict[str, Any]) -> str:
    must_fail = summary.get("must_fail", 0)
    must_human_required = summary.get("must_human_required", 0)
    if must_fail > 0 or must_human_required > 0:
        return "red"

    should_fail = summary.get("should_fail", 0)
    should_human_required = summary.get("should_human_required", 0)
    if should_fail > 0 or should_human_required > 0:
        return "yellow"

    return "green"


def compute_summary_counts(findings: list[dict[str, Any]]) -> dict[str, Any]:
    counts: dict[str, dict[str, int]] = {}
    for f in findings:
        severity = f.get("severity", "INFO")
        status = f.get("status", "fail")
        if severity not in counts:
            counts[severity] = {}
        counts[severity][status] = counts[severity].get(status, 0) + 1

    result: dict[str, Any] = {}
    for severity, status_counts in counts.items():
        for status, count in status_counts.items():
            key = f"{severity.lower()}_{status}"
            result[key] = count

    result["total"] = sum(r for r in result.values() if r)
    return result
