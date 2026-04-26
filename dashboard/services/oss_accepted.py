"""Read/write .iw/oss-accepted.yaml — accepted-risk entries per finding."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Annotated, Any

import yaml
from pydantic import BaseModel, Field


class AcceptedEntry(BaseModel):
    check_id: Annotated[str, Field(min_length=1)]
    finding_hash: Annotated[str, Field(min_length=1)]
    reason: Annotated[str, Field(min_length=1)]
    accepted_at: str
    accepted_by: str


class AcceptedFile(BaseModel):
    accepted: list[AcceptedEntry] = []


if TYPE_CHECKING:
    from pathlib import Path


def accepted_path(repo_root: Path) -> Path:
    return repo_root / ".iw" / "oss-accepted.yaml"


def compute_finding_hash(check_id: str, summary: str, evidence: dict[str, Any] | None) -> str:
    """Stable SHA-256 over (check_id, summary, sorted-evidence-JSON). 16 hex chars."""
    h = hashlib.sha256()
    h.update(check_id.encode())
    h.update(b"\x00")
    h.update(summary.encode())
    h.update(b"\x00")
    if evidence is not None:
        h.update(json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode())
    return h.hexdigest()[:16]


def _coerce_accepted_at(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def load_accepted(repo_root: Path) -> AcceptedFile:
    path = accepted_path(repo_root)
    if not path.exists():
        return AcceptedFile(accepted=[])
    raw = yaml.safe_load(path.read_text()) or {}
    if raw.get("accepted"):
        for entry in raw["accepted"]:
            if "accepted_at" in entry:
                entry["accepted_at"] = _coerce_accepted_at(entry["accepted_at"])
    return AcceptedFile.model_validate(raw)


def append_accepted(repo_root: Path, entry: AcceptedEntry) -> None:
    """Idempotent: if (check_id, finding_hash) already accepted, no-op."""
    path = accepted_path(repo_root)
    file = load_accepted(repo_root)
    if any(
        e.check_id == entry.check_id and e.finding_hash == entry.finding_hash for e in file.accepted
    ):
        return
    file.accepted.append(entry)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(file.model_dump(), sort_keys=False, default_flow_style=False))


def is_accepted(file: AcceptedFile, check_id: str, finding_hash: str) -> AcceptedEntry | None:
    for e in file.accepted:
        if e.check_id == check_id and e.finding_hash == finding_hash:
            return e
    return None


def accepted_by() -> str:
    """Current user identity for accepted_by field."""
    return os.getenv("USER", "unknown")


def now_iso() -> str:
    """UTC ISO-8601 timestamp."""
    return datetime.now(UTC).isoformat()
