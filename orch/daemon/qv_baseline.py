"""Pure QV baseline fingerprinting — parsers, fingerprint algebra, JSON serialization.

No DB calls, no subprocess orchestration, no daemon state.
All functions are pure and deterministic (Invariant 6: same input → same output).

Parsers
-------
parse_ruff  — handles `ruff check` JSON (--output-format json) and text output.
              Key: "<relative_file>::<rule_code>" (no line number).
parse_pytest — extracts FAILED nodeids. Key: the nodeid itself.
parse_mypy  — lines of form "<file>:<line>: error: <msg> [code]".
              Key: "<file>::<code>" (no line, no message).

Subtraction algebra
-------------------
subtract(current, baseline) -> Fingerprint
  Returns every failure in `current` that is NOT in `baseline`.
  Unparseable entries always surface (fail-safe).
  Ordering from `current` is preserved (Invariant 4).

GATE_PARSERS maps gate name → parser callable.
"format" (ruff format --check) is intentionally absent — its output shape
is incompatible and would route all findings to `unparseable`, breaking AC1.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

__all__ = [
    "FailureEntry",
    "Fingerprint",
    "parse_ruff",
    "parse_pytest",
    "parse_mypy",
    "GATE_PARSERS",
    "fingerprint_to_jsonable",
    "fingerprint_from_jsonable",
    "subtract",
]


@dataclass(frozen=True)
class FailureEntry:
    """One canonical failure identifier from a QV gate."""

    kind: str
    key: str


@dataclass(frozen=True)
class Fingerprint:
    """Canonical failure set from a QV gate."""

    failures: tuple[FailureEntry, ...]
    unparseable: tuple[str, ...] = ()


_UNPARSEABLE_RE = re.compile(r"^(?:\s*$|\s*#)")


def _make_key(kind: str, key: str) -> FailureEntry:
    return FailureEntry(kind=kind, key=key)


def _sort_failures(failures: list[FailureEntry]) -> tuple[FailureEntry, ...]:
    return tuple(sorted(failures, key=lambda f: (f.kind, f.key)))


_RUFF_TEXT_RE = re.compile(
    r"^(?P<file>[^:]+):(?P<line>\d+):(?P<col>\d+): "
    r"(?P<code>[A-Z]\d+)\s+(?P<msg>.+)$",
)

_RUFF_JSON_RE = re.compile(r'^\s*\{"(?:filename|cell)"')


def parse_ruff(raw_output: str) -> Fingerprint:
    """Parse `ruff check` output (JSON or text) into a Fingerprint.

    Key: "<relative_file>::<rule_code>" — no line number.
    Unparseable lines are collected as-is.
    """
    failures: list[FailureEntry] = []
    unparseable: list[str] = []

    text_lines = raw_output.strip().splitlines()
    if text_lines and _RUFF_JSON_RE.match(text_lines[0]):
        failures, unparseable = _parse_ruff_json(raw_output)
    else:
        failures, unparseable = _parse_ruff_text(text_lines)

    return Fingerprint(failures=_sort_failures(failures), unparseable=tuple(unparseable))


def _parse_ruff_text(lines: list[str]) -> tuple[list[FailureEntry], list[str]]:
    failures: list[FailureEntry] = []
    unparseable: list[str] = []
    for raw in lines:
        if not raw.strip() or _UNPARSEABLE_RE.match(raw):
            continue
        m = _RUFF_TEXT_RE.match(raw)
        if m:
            failures.append(_make_key("lint", f"{m.group('file')}::{m.group('code')}"))
        else:
            unparseable.append(raw)
    return failures, unparseable


def _parse_ruff_json(raw_output: str) -> tuple[list[FailureEntry], list[str]]:
    failures: list[FailureEntry] = []
    unparseable: list[str] = []
    try:
        data = json.loads(raw_output)
    except json.JSONDecodeError:
        unparseable.append(raw_output)
        return failures, unparseable

    if isinstance(data, list):
        entries = data
    elif isinstance(data, dict) and "results" in data:
        entries = data["results"]
    else:
        entries = []

    seen: set[tuple[str, str]] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            unparseable.append(str(entry))
            continue
        filename = entry.get("filename", "")
        code = entry.get("code", "")
        if filename and code:
            key = (filename, code)
            if key not in seen:
                seen.add(key)
                failures.append(_make_key("lint", f"{filename}::{code}"))
        else:
            unparseable.append(str(entry))
    return failures, unparseable


_PYTEST_FAILED_RE = re.compile(r"^(?P<prefix>FAILED)\s+(?P<nodeid>\S+)\s*-\s*(?P<msg>.*)$")


def parse_pytest(raw_output: str) -> Fingerprint:
    """Parse pytest output into a Fingerprint.

    Extracts each "FAILED <nodeid> - <msg>" line's nodeid.
    Key: the nodeid itself (no trailing error message).
    Boundary Behavior row 5: ignore trailing error message.
    Boundary Behavior row 6: if no explicit FAILED lines (e.g. xdist worker crash),
    treat the whole section as unparseable.
    """
    failures: list[FailureEntry] = []
    unparseable: list[str] = []
    seen: set[str] = set()

    lines = raw_output.strip().splitlines()

    for raw in lines:
        if not raw.strip() or _UNPARSEABLE_RE.match(raw):
            continue
        m = _PYTEST_FAILED_RE.match(raw)
        if m:
            nodeid = m.group("nodeid")
            if nodeid and nodeid not in seen:
                seen.add(nodeid)
                failures.append(_make_key("test", nodeid))
        elif raw.startswith(("===", "FAILED", "PASSED")):
            continue
        else:
            unparseable.append(raw)

    return Fingerprint(failures=_sort_failures(failures), unparseable=tuple(unparseable))


_MYPY_LINE_RE = re.compile(
    r"^(?P<file>[^:]+):(?P<line>\d+): "
    r"(?P<severity>error|warning|note|info):\s+"
    r"(?P<msg>.+?)"
    r"(?:\s+\[(?P<code>[a-z][a-z0-9-]*)\])?$",
    re.IGNORECASE,
)


def parse_mypy(raw_output: str) -> Fingerprint:
    """Parse mypy output into a Fingerprint.

    Lines of the form: path/file.py:42: error: Message [error-code]
    Key: "<file>::<error_code>" — no line number, no message.
    If no error code present, key is "<file>::<severity>" (fail-safe).
    """
    failures: list[FailureEntry] = []
    unparseable: list[str] = []
    seen: set[tuple[str, str]] = set()

    for raw in raw_output.strip().splitlines():
        if not raw.strip() or _UNPARSEABLE_RE.match(raw):
            continue
        m = _MYPY_LINE_RE.match(raw)
        if m:
            file = m.group("file")
            severity = m.group("severity").lower()
            code = m.group("code")
            key_str = f"{file}::{code}" if code else f"{file}::{severity}"
            key_val = code if code else severity
            key = (file, key_val)
            if key not in seen:
                seen.add(key)
                failures.append(_make_key("typecheck", key_str))
        else:
            unparseable.append(raw)

    return Fingerprint(failures=_sort_failures(failures), unparseable=tuple(unparseable))


GATE_PARSERS: Mapping[str, Callable[[str], Fingerprint]] = {
    "lint": parse_ruff,
    "typecheck": parse_mypy,
    "unit-tests": parse_pytest,
    "frontend-tests": parse_pytest,
    "integration-tests": parse_pytest,
}


def fingerprint_to_jsonable(fp: Fingerprint) -> dict[str, object]:
    """Serialize a Fingerprint to a JSON-serializable dict."""
    return {
        "failures": [{"kind": f.kind, "key": f.key} for f in fp.failures],
        "unparseable": list(fp.unparseable),
    }


def fingerprint_from_jsonable(data: dict[str, object]) -> Fingerprint:
    """Deserialize a JSON-serializable dict to a Fingerprint."""
    failures_raw = data.get("failures", [])
    if isinstance(failures_raw, list):
        failures = tuple(FailureEntry(kind=str(f["kind"]), key=str(f["key"])) for f in failures_raw)
    else:
        failures = ()
    unparseable_raw = data.get("unparseable", [])
    if isinstance(unparseable_raw, list):
        unparseable = tuple(str(u) for u in unparseable_raw)
    else:
        unparseable = ()
    return Fingerprint(failures=failures, unparseable=unparseable)


def subtract(current: Fingerprint, baseline: Fingerprint) -> Fingerprint:
    """Return failures in `current` that are NOT in `baseline`.

    Preserves the order from `current` (important for Invariant 4).
    Unparseable entries always surface — they are never matched against baseline.
    """
    baseline_keys = frozenset((f.kind, f.key) for f in baseline.failures)
    kept = tuple(f for f in current.failures if (f.kind, f.key) not in baseline_keys)
    return Fingerprint(failures=kept, unparseable=current.unparseable)
