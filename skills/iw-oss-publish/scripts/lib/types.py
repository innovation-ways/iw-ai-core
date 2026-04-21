"""Shared types: Severity, Status, Finding."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Severity(str, Enum):
    MUST = "MUST"
    SHOULD = "SHOULD"
    MAY = "MAY"
    INFO = "INFO"


class Status(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"
    HUMAN_REQUIRED = "human_required"


@dataclass
class Finding:
    """One observation from a single check run."""

    id: str
    severity: Severity
    status: Status
    domain: str
    summary: str
    detail: str = ""
    remediation: str | None = None
    auto_fix_available: bool = False
    osps_control: str | None = None
    evidence: dict[str, Any] = field(default_factory=dict)
    tool: str | None = None
    source_research: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "severity": self.severity.value,
            "status": self.status.value,
            "domain": self.domain,
            "summary": self.summary,
            "detail": self.detail,
            "remediation": self.remediation,
            "auto_fix_available": self.auto_fix_available,
            "osps_control": self.osps_control,
            "evidence": self.evidence,
            "tool": self.tool,
            "source_research": self.source_research,
        }
