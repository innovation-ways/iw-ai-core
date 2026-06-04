"""DB persistence for OSS scan findings."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from orch.db.models import (
    OssFinding,
    OssFindingDetail,
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
    """Persist scan findings and tool run records from a findings JSON payload.

    Iterates the ``findings`` list in the payload, creates one OssFinding row
    per entry, and flushes OssFindingDetail rows for any per-row ``results``
    sub-list. Also records each entry in ``tools_available`` as an OssToolRun
    row. Commits the session on completion.

    Args:
        session: Active SQLAlchemy session used for all inserts.
        scan: Parent OssScan row; its id is used as the foreign key for all
            new findings and tool-run rows.
        findings_json: Parsed contents of the skill's oss-publish-findings.json,
            expected to contain ``findings`` and ``tools_available`` keys.
    """
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
        # `results` is the per-row detail payload (e.g. SARIF records). It
        # belongs in oss_finding_detail, not in the JSONB blob, so we pop it
        # off before persisting evidence_json.
        results: list[dict[str, Any]] = []
        if isinstance(evidence, dict):
            evidence_json = dict(evidence)
            raw_results = evidence_json.pop("results", None)
            if isinstance(raw_results, list):
                results = [r for r in raw_results if isinstance(r, dict)]
        else:
            evidence_json = None

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
            auto_apply_safe=f.get("auto_apply_safe", False),
            osps_control=f.get("osps_control"),
            tool=f.get("tool"),
            evidence_json=evidence_json,
            rationale=f.get("rationale"),
        )
        session.add(finding)
        if results:
            session.flush()  # populate finding.id for FK
            for ordinal, record in enumerate(results):
                line_raw = record.get("line")
                detail = OssFindingDetail(
                    finding_id=finding.id,
                    ordinal=ordinal,
                    file_path=str(record.get("file") or ""),
                    line_number=line_raw if isinstance(line_raw, int) else None,
                    rule_id=str(record.get("rule") or "unknown"),
                    snippet_masked=record.get("snippet_masked"),
                )
                session.add(detail)

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
    """Derive the dashboard pill colour from a scan summary dict.

    Returns ``"red"`` when any MUST-severity finding failed or requires human
    review, ``"yellow"`` when only SHOULD-severity findings are unresolved,
    and ``"green"`` when all findings are resolved.

    Args:
        summary: Aggregated counts dict produced by the skill scanner,
            expected to contain keys such as ``must_fail``,
            ``must_human_required``, ``should_fail``, and
            ``should_human_required``.

    Returns:
        One of ``"red"``, ``"yellow"``, or ``"green"``.
    """
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
    """Aggregate per-severity and per-status counts from a list of finding dicts.

    Produces a flat dict with keys of the form ``"<severity_lower>_<status>"``
    plus a ``"total"`` key summing all counts.

    Args:
        findings: List of raw finding dicts, each expected to have ``severity``
            and ``status`` string fields.

    Returns:
        Dict mapping ``"<severity>_<status>"`` composite keys to integer counts,
        plus ``"total"`` for the overall sum.
    """
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
