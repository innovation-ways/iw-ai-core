"""Shared helpers for emitting structured per-row results in Finding.evidence.

Persistence at ``orch/oss/persistence.py`` pops ``evidence["results"]`` and
writes each entry to the ``oss_finding_detail`` table so the dashboard modal
can render a real per-hit table (file / line / rule / snippet) instead of a
JSON dump. Every check that has per-hit data should produce its evidence
through these helpers so the shape stays consistent.
"""

from __future__ import annotations

import re
from typing import Any

# Hard cap on per-finding detail records we ship to the dashboard. The raw
# tool output (SARIF, ripgrep stdout, …) on disk is unaffected; the cap only
# bounds what reaches the DB / modal. Mirrors the value used for SARIF in
# secrets.py so behavior stays consistent across checks.
RESULT_CAP = 500

_RG_LINE_RE = re.compile(r"^(?P<file>[^:]+):(?P<line>\d+):(?P<text>.*)$")


def parse_rg_lines(
    lines: list[str],
    *,
    rule_id: str,
    snippet_max_chars: int = 200,
) -> list[dict[str, Any]]:
    """Parse ripgrep ``--with-filename --line-number`` output into result records.

    Lines that don't match the ``path:line:text`` shape (e.g. binary-file
    notices) are skipped rather than raising — ripgrep can emit them
    unpredictably depending on flags.
    """
    records: list[dict[str, Any]] = []
    for raw in lines:
        m = _RG_LINE_RE.match(raw)
        if m is None:
            continue
        try:
            line_no: int | None = int(m.group("line"))
        except ValueError:
            line_no = None
        snippet = m.group("text").strip()
        if len(snippet) > snippet_max_chars:
            snippet = snippet[:snippet_max_chars] + "…"
        records.append(
            {
                "file": m.group("file"),
                "line": line_no,
                "rule": rule_id,
                "snippet_masked": snippet,
            }
        )
    return records


def build_results_evidence(
    records: list[dict[str, Any]],
    *,
    total: int | None = None,
    extras: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Wrap a list of per-row records in the canonical evidence shape.

    Persistence will pop ``results`` and write the rows to
    ``oss_finding_detail``; the remaining fields stay on
    ``oss_finding.evidence_json`` for the modal's "Evidence" section.
    """
    if total is None:
        total = len(records)
    capped = total > RESULT_CAP
    payload: dict[str, Any] = {
        "finding_count": total,
        "total_results": total,
        "capped": capped,
        "results": records[:RESULT_CAP],
    }
    if extras:
        payload.update(extras)
    return payload
