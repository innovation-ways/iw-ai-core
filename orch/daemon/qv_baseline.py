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

GATE_PARSERS maps gate name → precise parser callable.
parser_for_gate() returns a precise parser when known, otherwise a conservative
line-based fallback so every gate gets baseline subtraction coverage.
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
    "parse_assertion_scanner",
    "parse_generic_lines",
    "GATE_PARSERS",
    "parser_for_gate",
    "fingerprint_to_jsonable",
    "fingerprint_from_jsonable",
    "subtract",
    "is_pre_existing_only",
    "_SuppressedFindings",
]


class _SuppressedFindings(str):
    """Empty findings that specifically signal: all gate failures are pre-existing.

    A ``str`` subclass whose value is always ``""`` so every existing emptiness
    check (``if not findings``, ``findings == ""``) behaves identically and
    nothing else needs to change. Carries metadata needed to emit the event and
    transition the step without re-resolving anything.

    Instance-level metadata is stored in class-level ``_meta[id(self)]`` since
    ``str`` has no ``__dict__``. ``gate_name``, ``suppressed_keys``, and
    ``suppressed_count`` are class variables resolved from that dict so mypy
    sees them as proper attributes.
    """

    _meta: dict[int, dict[str, object]] = {}

    def __new__(cls, gate_name: str, suppressed_keys: tuple[str, ...]) -> _SuppressedFindings:
        obj = super().__new__(cls, "")
        cls._meta[id(obj)] = {
            "gate_name": gate_name,
            "suppressed_keys": suppressed_keys,
            "suppressed_count": len(suppressed_keys),
        }
        return obj

    @property
    def gate_name(self) -> str:
        return self._meta[id(self)]["gate_name"]  # type: ignore[return-value]

    @property
    def suppressed_keys(self) -> tuple[str, ...]:
        return self._meta[id(self)]["suppressed_keys"]  # type: ignore[return-value]

    @property
    def suppressed_count(self) -> int:
        return self._meta[id(self)]["suppressed_count"]  # type: ignore[return-value]


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
    """Construct a FailureEntry with the given kind and key."""
    return FailureEntry(kind=kind, key=key)


def _sort_failures(failures: list[FailureEntry]) -> tuple[FailureEntry, ...]:
    """Return a sorted, deduplicated tuple of FailureEntry objects."""
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
    """Parse ruff text-format output lines into (failures, unparseable)."""
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
    """Parse ruff JSON-format output into (failures, unparseable)."""
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


# pytest's short-summary line. The trailing " - <reason>" is optional: pytest
# omits it for assertion-introspection failures (the common case) and only adds
# it for collection/setup errors. The original regex *required* the dash, so the
# bare "FAILED <nodeid>" line was silently dropped — every test failure became
# zero parsed failures plus, under `pytest -v`, a few thousand "<nodeid> PASSED"
# progress lines in the `unparseable` bucket. That ~349 KB blob is what made the
# I-00074 fix-cycle prompt overflow execve's argv limit so every fix cycle died
# on launch ("/usr/bin/timeout: Argument list too long"). Make the dash optional.
_PYTEST_FAILED_RE = re.compile(r"^FAILED\s+(?P<nodeid>\S+)(?:\s+-\s+(?P<msg>.*))?\s*$")

# `pytest -v` prints one line per test: "<path>::<test> PASSED [ 12%]" (also
# SKIPPED / XFAIL / XPASS / ERROR / FAILED). These are pure progress noise that
# must never reach `unparseable`. FAILED/ERROR verbose lines are redundant with
# the short summary above (which `_PYTEST_FAILED_RE` already captures), so it is
# safe to drop all of them.
_PYTEST_VERBOSE_RESULT_RE = re.compile(r"^\S+::.*\s(?:PASSED|FAILED|SKIPPED|XFAIL|XPASS|ERROR)\b")

# Hard ceiling on the lines kept in `unparseable`, so a parser miss can never
# bloat a fix-cycle prompt again. Keep the head (run header / error context) and
# the tail (the failure summary that lives at the bottom of pytest output).
_MAX_UNPARSEABLE_LINES = 80


def cap_unparseable(lines: list[str]) -> list[str]:
    """Truncate the middle of an over-long `unparseable` list, keeping head + tail."""
    if len(lines) <= _MAX_UNPARSEABLE_LINES:
        return list(lines)
    head = _MAX_UNPARSEABLE_LINES // 2
    tail = _MAX_UNPARSEABLE_LINES - head
    omitted = len(lines) - _MAX_UNPARSEABLE_LINES
    return [*lines[:head], f"...({omitted} lines omitted)...", *lines[-tail:]]


def parse_pytest(raw_output: str) -> Fingerprint:
    """Parse pytest output into a Fingerprint.

    Extracts each ``FAILED <nodeid>`` short-summary line's nodeid (the trailing
    ``- <reason>`` is optional). ``pytest -v`` per-test progress lines and the
    ``===`` banners are dropped; anything else is collected as ``unparseable``
    (capped — see :func:`cap_unparseable`).
    Boundary Behavior row 5: ignore trailing error message.
    Boundary Behavior row 6: if no explicit FAILED lines (e.g. xdist worker crash),
    surface the (capped) section as unparseable.
    """
    failures: list[FailureEntry] = []
    unparseable: list[str] = []
    seen: set[str] = set()

    lines = raw_output.strip().splitlines()

    for raw in lines:
        stripped = raw.strip()
        if not stripped or _UNPARSEABLE_RE.match(raw):
            continue
        m = _PYTEST_FAILED_RE.match(stripped)
        if m:
            nodeid = m.group("nodeid")
            if nodeid and nodeid not in seen:
                seen.add(nodeid)
                failures.append(_make_key("test", nodeid))
            continue
        if _PYTEST_VERBOSE_RESULT_RE.match(stripped) or stripped.startswith(
            ("===", "FAILED", "PASSED")
        ):
            continue
        unparseable.append(raw)

    return Fingerprint(
        failures=_sort_failures(failures),
        unparseable=tuple(cap_unparseable(unparseable)),
    )


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


_ASSERTION_SCANNER_RE = re.compile(
    r"^(?P<file>.+?):(?P<line>\d+):\s+"
    r"(?P<category>[^:]+):\s+"
    r"(?P<test_name>[^:]+):\s+"
    r"(?P<message>.+)$"
)


def parse_assertion_scanner(raw_output: str) -> Fingerprint:
    """Parse `check_test_assertions.py` human output into a Fingerprint.

    Expected format per violation:
    ``<file>:<line>: <category>: <test_name>: <message>``

    Key: ``<file>::<test_name>`` (stable identity), intentionally excluding the
    message text because wording can change without changing the underlying
    failure.
    """
    failures: list[FailureEntry] = []
    unparseable: list[str] = []
    seen: set[tuple[str, str]] = set()

    for raw in raw_output.strip().splitlines():
        stripped = raw.strip()
        if not stripped or _UNPARSEABLE_RE.match(raw):
            continue
        match = _ASSERTION_SCANNER_RE.match(stripped)
        if not match:
            unparseable.append(raw)
            continue
        file = match.group("file")
        test_name = match.group("test_name")
        key = (file, test_name)
        if key in seen:
            continue
        seen.add(key)
        failures.append(_make_key("assertion", f"{file}::{test_name}"))

    return Fingerprint(failures=_sort_failures(failures), unparseable=tuple(unparseable))


def parse_generic_lines(raw_output: str) -> Fingerprint:
    """Fallback parser for gates without a dedicated parser.

    Each non-empty stripped line becomes ``FailureEntry(kind="line", key=<line>)``.
    This is conservative but can falsely suppress a new failure if its output line
    is byte-identical to a baselined line.
    """
    failures: list[FailureEntry] = []
    seen: set[str] = set()

    for raw in raw_output.splitlines():
        normalized = raw.strip()
        if not normalized or _UNPARSEABLE_RE.match(raw):
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        failures.append(_make_key("line", normalized))

    return Fingerprint(failures=_sort_failures(failures), unparseable=())


GATE_PARSERS: Mapping[str, Callable[[str], Fingerprint]] = {
    "lint": parse_ruff,
    "typecheck": parse_mypy,
    "unit-tests": parse_pytest,
    "frontend-tests": parse_pytest,
    "assertions": parse_assertion_scanner,
}


def parser_for_gate(gate_name: str) -> Callable[[str], Fingerprint]:
    """Return parser for any gate (precise parser if known, generic fallback otherwise)."""
    if gate_name == "integration-tests":
        return parse_pytest
    return GATE_PARSERS.get(gate_name, parse_generic_lines)


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


def is_pre_existing_only(current: Fingerprint, baseline: Fingerprint) -> bool:
    """True iff every current failure (incl. unparseable) is already in baseline.

    Reuses ``subtract`` so the comparison is keyed on ``(kind, key)`` and is
    correct for every gate parser (not just pytest). ``subtract`` never matches
    ``unparseable`` entries against the baseline, so any unparseable line forces
    a ``False`` (fail-safe: if we cannot parse it, we cannot suppress it).

    Returns
    -------
    True
        when ``current`` has no failures at all, or every parseable failure in
        ``current`` is present in ``baseline`` and ``current`` has no unparseable
        entries.
    False
        as soon as one current failure (parseable or unparseable) is absent from
        ``baseline``.
    """
    delta = subtract(current, baseline)
    return not delta.failures and not delta.unparseable
