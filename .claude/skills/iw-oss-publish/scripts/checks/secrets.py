"""OSS-SEC — Secret scanning via gitleaks / trufflehog."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from lib.context import Context
from lib.registry import register
from lib.types import Finding, Severity, Status

DOMAIN = "secrets"

# Hard cap on per-finding SARIF results carried in evidence and persisted to
# the oss_finding_detail table. The SARIF file on disk still has every record;
# the cap only bounds what we ship to the dashboard so a runaway scan can't
# bloat the database or the modal.
RESULT_CAP = 500

_MASK_KEEP = 4  # chars retained at each end when masking a long secret


@register(id_prefix="OSS-SEC", order=3, domain=DOMAIN)
def secrets(ctx: Context) -> list[Finding]:
    out: list[Finding] = []

    # OSS-SEC-01: working-tree scan
    out.append(
        _gitleaks_scan(
            ctx,
            check_id="OSS-SEC-01",
            scope="tree",
            args=[
                "detect",
                "--no-git",
                "--source",
                str(ctx.target),
                "--report-format",
                "sarif",
                "--report-path",
                str(ctx.iw_dir / "gitleaks-tree.sarif"),
                "--exit-code",
                "0",
            ],  # we read output; don't fail the process
        )
    )

    # OSS-SEC-02: full history scan
    out.append(
        _gitleaks_scan(
            ctx,
            check_id="OSS-SEC-02",
            scope="history",
            args=[
                "detect",
                "--source",
                str(ctx.target),
                "--log-opts=--all",
                "--report-format",
                "sarif",
                "--report-path",
                str(ctx.iw_dir / "gitleaks-history.sarif"),
                "--exit-code",
                "0",
            ],
        )
    )

    # OSS-SEC-04: .gitleaks.toml present
    gl = ctx.path(".gitleaks.toml")
    out.append(
        Finding(
            id="OSS-SEC-04",
            severity=Severity.SHOULD,
            status=Status.PASS if gl.exists() else Status.FAIL,
            domain=DOMAIN,
            summary=".gitleaks.toml present"
            if gl.exists()
            else ".gitleaks.toml missing — using gitleaks defaults only",
            remediation="`make_oss` will write a config with IW-specific rules."
            if not gl.exists()
            else None,
            auto_fix_available=True,
            auto_apply_safe=True,
            source_research=["R-00061 #2"],
        )
    )

    # OSS-SEC-05: detect-secrets baseline (opt-in)
    if ctx.config.get("secrets", {}).get("detect_secrets_baseline"):
        baseline = ctx.path(".secrets.baseline")
        out.append(
            Finding(
                id="OSS-SEC-05",
                severity=Severity.MAY,
                status=Status.PASS if baseline.exists() else Status.FAIL,
                domain=DOMAIN,
                summary="detect-secrets baseline present"
                if baseline.exists()
                else "detect-secrets baseline missing (opted in)",
                auto_fix_available=True,
                auto_apply_safe=True,
            )
        )

    return out


def _gitleaks_scan(ctx: Context, check_id: str, scope: str, args: list[str]) -> Finding:
    if not ctx.has_tool("gitleaks"):
        return Finding(
            id=check_id,
            severity=Severity.MUST,
            status=Status.SKIP,
            domain=DOMAIN,
            summary=f"gitleaks unavailable — {scope} secrets scan skipped",
            remediation="Install gitleaks: bash .claude/skills/iw-oss-publish/scripts/install_tools.sh",
            tool="gitleaks",
        )

    try:
        r = subprocess.run(
            ["gitleaks", *args],
            cwd=ctx.target,
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
    except (subprocess.SubprocessError, FileNotFoundError) as exc:
        return Finding(
            id=check_id,
            severity=Severity.MUST,
            status=Status.SKIP,
            domain=DOMAIN,
            summary=f"gitleaks invocation failed ({scope})",
            detail=str(exc),
            tool="gitleaks",
        )

    sarif_path = args[args.index("--report-path") + 1] if "--report-path" in args else None
    evidence = _build_evidence_from_sarif(sarif_path, target=ctx.target)
    leaks = evidence["finding_count"]

    if leaks == 0:
        return Finding(
            id=check_id,
            severity=Severity.MUST,
            status=Status.PASS,
            domain=DOMAIN,
            summary=f"No secrets detected ({scope} scan)",
            tool="gitleaks",
            evidence=evidence,
            source_research=["R-00061 #2"],
        )
    return Finding(
        id=check_id,
        severity=Severity.MUST,
        status=Status.FAIL,
        domain=DOMAIN,
        summary=f"{leaks} secret(s) detected ({scope} scan)",
        detail=(r.stdout or r.stderr or "").strip()[:2000],
        remediation=(
            "Review the SARIF report. Rotate any real credentials immediately. "
            "For history leaks: use `publish` mode and choose a rewrite strategy."
        ),
        tool="gitleaks",
        evidence=evidence,
        source_research=["R-00061 #2"],
    )


def _mask_secret(value: str | None) -> str:
    """Return ``value`` with its middle bytes replaced by ``*``.

    - ``None`` and empty inputs return an empty string.
    - Surrounding whitespace is stripped before masking (gitleaks snippets often
      include leading/trailing spaces from the source line).
    - Strings of length ``2 * _MASK_KEEP`` or shorter are entirely masked, so
      we never leak short tokens.
    - Otherwise the first and last ``_MASK_KEEP`` chars are kept and the middle
      is replaced one-for-one with ``*``.
    """
    if not value:
        return ""
    s = value.strip()
    if not s:
        return ""
    if len(s) <= 2 * _MASK_KEEP:
        return "*" * len(s)
    return s[:_MASK_KEEP] + "*" * (len(s) - 2 * _MASK_KEEP) + s[-_MASK_KEEP:]


def _normalise_uri(uri: str, target: Path | str) -> str:
    """Convert a SARIF artifactLocation.uri to a project-relative path.

    Gitleaks emits absolute paths when invoked with ``--source <abs>``; the
    dashboard is far more useful with ``src/foo.py`` than
    ``/home/.../iw-ai-core/src/foo.py``. If the URI is outside the target tree,
    return it verbatim — a confusing ``../../...`` is worse than a long path.
    """
    target_path = Path(target).resolve()
    try:
        candidate = Path(uri)
        if candidate.is_absolute():
            rel = candidate.resolve().relative_to(target_path)
            return rel.as_posix()
    except (ValueError, OSError):
        return uri
    return uri


def _parse_sarif_results(
    sarif_path: str | None, *, target: Path | str
) -> tuple[list[dict[str, Any]], int]:
    """Read a gitleaks SARIF document and return ``(records, total)``.

    ``records`` is capped at :data:`RESULT_CAP`; ``total`` always reflects the
    real number of results across every run in the document. Malformed JSON,
    missing files, and an absent ``sarif_path`` all fall through to
    ``([], 0)`` rather than raising — the caller should not have to mind
    whether the gitleaks process produced a SARIF.
    """
    if not sarif_path:
        return [], 0
    try:
        with open(sarif_path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return [], 0

    records: list[dict[str, Any]] = []
    total = 0
    for run in data.get("runs", []):
        for res in run.get("results", []):
            total += 1
            if len(records) >= RESULT_CAP:
                continue
            rule = res.get("ruleId") or "unknown"
            file_path = ""
            line: int | None = None
            snippet = ""
            locations = res.get("locations") or []
            if locations:
                phys = locations[0].get("physicalLocation") or {}
                artifact = phys.get("artifactLocation") or {}
                uri = artifact.get("uri") or ""
                if uri:
                    file_path = _normalise_uri(uri, target)
                region = phys.get("region") or {}
                line_raw = region.get("startLine")
                if isinstance(line_raw, int):
                    line = line_raw
                snippet_obj = region.get("snippet") or {}
                snippet = snippet_obj.get("text") or ""
            records.append(
                {
                    "file": file_path,
                    "line": line,
                    "rule": rule,
                    "snippet_masked": _mask_secret(snippet),
                }
            )
    return records, total


def _build_evidence_from_sarif(sarif_path: str | None, *, target: Path | str) -> dict[str, Any]:
    """Assemble the ``Finding.evidence`` dict carried into persistence.

    Persistence pops ``results`` out of this dict and writes the items as
    ``oss_finding_detail`` rows; the remaining aggregate fields stay in
    ``oss_finding.evidence_json`` for the modal's "Evidence" section.
    """
    results, total = _parse_sarif_results(sarif_path, target=target)
    return {
        "sarif": sarif_path,
        "finding_count": total,
        "total_results": total,
        "capped": total > RESULT_CAP,
        "results": results,
    }
