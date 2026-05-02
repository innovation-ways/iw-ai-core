"""Helpers for the self_assess step type.

The self_assess step runs the iw-item-analyze skill against a just-completed
work item before merge. It is purely informational — failures never block
merge (see is_soft_step). The skill's structured findings are written to disk
as <ID>_self_assess_findings.json alongside the human-readable
<ID>_self_assess_report.md narrative; both files live in the per-item
reports dir.

This module provides:
  - SelfAssessFinding / SelfAssessmentData dataclasses
  - parse_findings_json: tolerant JSON parser
  - is_self_assess_step: type-narrowing helper
  - findings_path_for: convention-based sidecar path resolver
  - is_soft_step_failure: should this step's failure block batch progression?
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

# Valid severity values for a finding.
_VALID_SEVERITIES: frozenset[str] = frozenset({"HIGH", "MED", "LOW"})

# Valid target values for a finding.
_VALID_TARGETS: frozenset[str] = frozenset({"iw-ai-core", "project"})


@dataclass(frozen=True)
class SelfAssessFinding:
    """A single process finding from the self_assess step."""

    severity: Literal["HIGH", "MED", "LOW"]
    clazz: str  # noqa: A002  (class is a Python keyword — field renamed to avoid shadowing)
    target: Literal["iw-ai-core", "project"]
    title: str
    recommendation: str
    paste_prompt: str
    evidence: list[str] = field(default_factory=list)
    effort: str | None = None


@dataclass(frozen=True)
class SelfAssessmentData:
    """Full self-assessment output from the iw-item-analyze skill."""

    narrative_md: str | None = None
    findings: list[SelfAssessFinding] = field(default_factory=list)
    coverage_notes: str | None = None
    bottom_line: str | None = None


class SelfAssessParseError(ValueError):
    """Raised when the findings JSON cannot be parsed or fails validation."""


def parse_findings_json(text: str) -> SelfAssessmentData:
    """Parse a structured findings JSON string into SelfAssessmentData.

    Unknown toplevel fields are ignored. Required finding fields are enforced:
    severity (must be HIGH/MED/LOW), class, target (must be iw-ai-core/project),
    title, recommendation, paste_prompt.

    Raises SelfAssessParseError on malformed JSON, missing required fields,
    or invalid severity/target values.
    """
    if not text or not text.strip():
        raise SelfAssessParseError("Findings JSON is empty")

    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SelfAssessParseError(f"Malformed JSON: {exc}") from exc

    if not isinstance(raw, dict):
        raise SelfAssessParseError("Findings JSON must be a top-level object")

    # narrative_md is optional
    narrative_md = raw.get("narrative_md")
    if narrative_md is not None and not isinstance(narrative_md, str):
        narrative_md = None

    coverage_notes = raw.get("coverage_notes")
    if coverage_notes is not None and not isinstance(coverage_notes, str):
        coverage_notes = None

    bottom_line = raw.get("bottom_line")
    if bottom_line is not None and not isinstance(bottom_line, str):
        bottom_line = None

    # findings list is required; empty list is OK
    raw_findings = raw.get("findings")
    if not isinstance(raw_findings, list):
        raise SelfAssessParseError("findings must be a list")

    findings: list[SelfAssessFinding] = []
    for i, item in enumerate(raw_findings):
        if not isinstance(item, dict):
            raise SelfAssessParseError(f"findings[{i}] must be an object")

        # Required fields
        severity = item.get("severity")
        if not isinstance(severity, str) or severity not in _VALID_SEVERITIES:
            raise SelfAssessParseError(
                f"findings[{i}].severity must be one of {sorted(_VALID_SEVERITIES)}"
            )

        clazz = item.get("class")
        if not isinstance(clazz, str):
            raise SelfAssessParseError(f"findings[{i}].class must be a string")

        target = item.get("target")
        if not isinstance(target, str) or target not in _VALID_TARGETS:
            raise SelfAssessParseError(
                f"findings[{i}].target must be one of {sorted(_VALID_TARGETS)}"
            )

        title = item.get("title")
        if not isinstance(title, str):
            raise SelfAssessParseError(f"findings[{i}].title must be a string")

        recommendation = item.get("recommendation")
        if not isinstance(recommendation, str):
            raise SelfAssessParseError(f"findings[{i}].recommendation must be a string")

        paste_prompt = item.get("paste_prompt")
        if not isinstance(paste_prompt, str):
            raise SelfAssessParseError(f"findings[{i}].paste_prompt must be a string")

        # Optional fields with defaults
        evidence_raw = item.get("evidence")
        if isinstance(evidence_raw, list) and all(isinstance(e, str) for e in evidence_raw):
            evidence: list[str] = evidence_raw
        else:
            evidence = []

        effort = item.get("effort")
        if effort is not None and not isinstance(effort, str):
            effort = None

        findings.append(
            SelfAssessFinding(
                severity=severity,  # type: ignore[arg-type]
                clazz=clazz,
                target=target,  # type: ignore[arg-type]
                title=title,
                recommendation=recommendation,
                paste_prompt=paste_prompt,
                evidence=evidence,
                effort=effort,
            )
        )

    return SelfAssessmentData(
        narrative_md=narrative_md,
        findings=findings,
        coverage_notes=coverage_notes,
        bottom_line=bottom_line,
    )


def is_self_assess_step(step_type: object) -> bool:
    """Return True if step_type is the self_assess enum member or string.

    Mirrors the ``is_browser_verification_step`` pattern from
    ``orch.daemon.browser_env``.
    """
    if isinstance(step_type, str):
        return step_type in ("self_assess", "StepType.self_assess")
    # Enum member
    name = getattr(step_type, "name", None)
    return name == "self_assess" if name else False


def findings_path_for(report_path: Path | str) -> Path:
    """Derive the canonical findings JSON sidecar path from the report path.

    Convention:
      ``<stem>_report.md``  →  ``<stem>_findings.json``
      ``<stem>.md``          →  ``<stem>_findings.json``

    The dashboard uses this to discover the sidecar from ``StepRun.report_file``
    without needing a new DB column.
    """
    p = Path(report_path)
    name = p.name

    # Replace trailing _report.md or just .md
    if name.endswith("_report.md"):
        stem = name[:-10]  # strip "_report.md"
    elif name.endswith(".md"):
        stem = name[:-3]  # strip ".md"
    else:
        # No known suffix — append _findings.json
        stem = name

    return p.parent / f"{stem}_findings.json"


# Terminal run statuses that constitute a "failure" for soft-step purposes.
_SOFT_STEP_FAILURE_STATUSES: frozenset[str] = frozenset({"failed", "timeout", "killed", "stalled"})


def is_soft_step_failure(step_type: object, run_status: object) -> bool:
    """Return True when step_type is self_assess AND run_status is a failure.

    A self_assess step that fails does not block batch_item progression to
    ``merging``. The StepRun row still records the actual failure for
    reporting purposes.

    Used by batch progression logic to determine whether a failed step should
    be treated as terminal-success for merge purposes.
    """
    if not is_self_assess_step(step_type):
        return False
    # Extract the string value from the enum or string
    if hasattr(run_status, "value"):
        status = str(run_status.value)
    else:
        status = str(run_status) if run_status is not None else ""
    return status in _SOFT_STEP_FAILURE_STATUSES
