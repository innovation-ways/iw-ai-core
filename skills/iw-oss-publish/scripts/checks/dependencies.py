"""OSS-DEP — Dependencies, SBOM, license policy, vulnerability scans."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from lib.context import Context
from lib.registry import register
from lib.results import RESULT_CAP, build_results_evidence
from lib.types import Finding, Severity, Status

DOMAIN = "dependencies"

OUTBOUND_DENY = {
    "Apache-2.0": {
        "GPL-2.0-only",
        "GPL-3.0-only",
        "GPL-3.0-or-later",
        "AGPL-3.0-only",
        "AGPL-3.0-or-later",
    },
    "MIT": {
        "GPL-2.0-only",
        "GPL-3.0-only",
        "GPL-3.0-or-later",
        "AGPL-3.0-only",
        "AGPL-3.0-or-later",
    },
}


@register(id_prefix="OSS-DEP", order=7, domain=DOMAIN)
def dependency_checks(ctx: Context) -> list[Finding]:
    out: list[Finding] = []

    # OSS-DEP-05: SBOM generation
    sbom_paths = _generate_sbom(ctx)
    if sbom_paths:
        out.append(
            Finding(
                id="OSS-DEP-05",
                severity=Severity.SHOULD,
                status=Status.PASS,
                domain=DOMAIN,
                summary="SBOM generated (SPDX + CycloneDX)",
                evidence={"paths": [str(p) for p in sbom_paths]},
                tool="syft",
                auto_fix_available=True,
                auto_apply_safe=True,
            )
        )
    else:
        out.append(
            Finding(
                id="OSS-DEP-05",
                severity=Severity.SHOULD,
                status=Status.SKIP,
                domain=DOMAIN,
                summary="syft unavailable or failed — SBOM not generated",
                tool="syft",
                auto_apply_safe=False,
            )
        )

    # OSS-DEP-01: license policy check (requires SBOM)
    spdx_path = ctx.iw_dir / "sbom.spdx.json"
    outbound = ctx.config.get("license", "Apache-2.0")
    deny = OUTBOUND_DENY.get(outbound, OUTBOUND_DENY["Apache-2.0"])
    elections = _load_license_elections(ctx.config)
    if spdx_path.exists():
        raw_flagged = _scan_sbom_licenses(spdx_path, deny)
        flagged, honored = _apply_license_elections(raw_flagged, elections, deny)
        if not flagged:
            extras: dict[str, Any] = {"outbound_license": outbound}
            if honored:
                extras["honored_elections"] = honored
            summary = f"No copyleft/proprietary deps incompatible with {outbound}"
            if honored:
                summary += f" ({len(honored)} license election(s) honored)"
            out.append(
                Finding(
                    id="OSS-DEP-01",
                    severity=Severity.MUST,
                    status=Status.PASS,
                    domain=DOMAIN,
                    summary=summary,
                    evidence=extras if honored else {},
                    tool="syft",
                    auto_apply_safe=False,
                )
            )
        else:
            extras = {"outbound_license": outbound}
            if honored:
                extras["honored_elections"] = honored
            out.append(
                Finding(
                    id="OSS-DEP-01",
                    severity=Severity.MUST,
                    status=Status.FAIL,
                    domain=DOMAIN,
                    summary=f"{len(flagged)} dep(s) license-incompatible with {outbound}",
                    detail="\n".join(f"  - {name} ({lic})" for name, lic in flagged[:20]),
                    remediation="Replace incompatible deps, change outbound license, or "
                    "document a license election under [dependencies.license_elections] "
                    "in .iw/oss-publish.toml.",
                    evidence=build_results_evidence(
                        [
                            {
                                "file": name,
                                "line": None,
                                "rule": lic,
                                "snippet_masked": f"license {lic} incompatible with {outbound}",
                            }
                            for name, lic in flagged
                        ],
                        total=len(flagged),
                        extras=extras,
                    ),
                    auto_apply_safe=False,
                )
            )
    else:
        out.append(
            Finding(
                id="OSS-DEP-01",
                severity=Severity.MUST,
                status=Status.SKIP,
                domain=DOMAIN,
                summary="SBOM unavailable — license policy check skipped",
                auto_apply_safe=False,
            )
        )

    # OSS-DEP-03, OSS-DEP-04: vulnerabilities via grype
    if spdx_path.exists() and ctx.has_tool("grype"):
        counts, vuln_records = _grype_scan(ctx, spdx_path)
        if counts is not None:
            critical = counts.get("Critical", 0)
            high = counts.get("High", 0)
            critical_records = [r for r in vuln_records if r["_severity"] == "Critical"]
            high_records = [r for r in vuln_records if r["_severity"] == "High"]

            # Strip internal _severity key before passing to evidence
            def _strip(records: list[dict]) -> list[dict]:
                return [{k: v for k, v in r.items() if k != "_severity"} for r in records]

            out.append(
                Finding(
                    id="OSS-DEP-03",
                    severity=Severity.MUST,
                    status=Status.PASS if critical == 0 else Status.FAIL,
                    domain=DOMAIN,
                    summary=f"Critical vulnerabilities: {critical}",
                    detail=_format_vuln_detail(critical_records) if critical else "",
                    evidence=build_results_evidence(_strip(critical_records), total=critical)
                    if critical
                    else {},
                    remediation=(
                        "Upgrade the affected package(s) to the fix version shown above, "
                        "or replace with a functionally equivalent alternative. "
                        "Regenerate the SBOM and re-run the check to confirm the count reaches zero."
                    )
                    if critical
                    else None,
                    tool="grype",
                    auto_apply_safe=False,
                )
            )
            out.append(
                Finding(
                    id="OSS-DEP-04",
                    severity=Severity.SHOULD,
                    status=Status.PASS if high == 0 else Status.FAIL,
                    domain=DOMAIN,
                    summary=f"High vulnerabilities: {high}",
                    detail=_format_vuln_detail(high_records) if high else "",
                    evidence=build_results_evidence(_strip(high_records), total=high)
                    if high
                    else {},
                    remediation=(
                        "Upgrade the affected package(s) to the fix version shown above, "
                        "or replace with a functionally equivalent alternative."
                    )
                    if high
                    else None,
                    tool="grype",
                    auto_apply_safe=False,
                )
            )
        else:
            out.append(
                Finding(
                    id="OSS-DEP-03",
                    severity=Severity.MUST,
                    status=Status.SKIP,
                    domain=DOMAIN,
                    summary="grype scan returned no data",
                    auto_apply_safe=False,
                )
            )

    # OSS-DEP-06: THIRD_PARTY_LICENSES file
    tpl = ctx.exists("THIRD_PARTY_LICENSES.md", "THIRD_PARTY_LICENSES", "THIRD-PARTY-NOTICES")
    out.append(
        Finding(
            id="OSS-DEP-06",
            severity=Severity.SHOULD,
            status=Status.PASS if tpl else Status.FAIL,
            domain=DOMAIN,
            summary=f"Third-party license file present: {tpl}"
            if tpl
            else "THIRD_PARTY_LICENSES file missing",
            remediation="`make_oss` regenerates from per-ecosystem license tools."
            if not tpl
            else None,
            auto_fix_available=True,
            auto_apply_safe=True,
        )
    )

    return out


_SBOM_EXCLUDES = [
    # Dev-only dirs that are never shipped as part of the OSS release.
    # .venv contains bundled binaries (e.g. Playwright's node runtime) that
    # trigger false-positive vulnerability hits unrelated to the project code.
    ".venv",
    "venv",
    ".tox",
    ".nox",
    "__pycache__",
    ".worktrees",
    ".iw",
]


def _generate_sbom(ctx: Context) -> list[Path]:
    if not ctx.has_tool("syft"):
        return []
    spdx = ctx.iw_dir / "sbom.spdx.json"
    cyclonedx = ctx.iw_dir / "sbom.cyclonedx.json"
    exclude_flags: list[str] = []
    for name in _SBOM_EXCLUDES:
        exclude_flags += ["--exclude", f"./{name}"]
    try:
        r = subprocess.run(
            [
                "syft",
                "scan",
                "dir:" + str(ctx.target),
                "-o",
                f"spdx-json={spdx}",
                "-o",
                f"cyclonedx-json={cyclonedx}",
                "-q",
                *exclude_flags,
            ],
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
        if r.returncode != 0:
            # Fallback: older syft uses `syft .` instead of `syft scan dir:`
            r2 = subprocess.run(
                [
                    "syft",
                    str(ctx.target),
                    "-o",
                    f"spdx-json={spdx}",
                    "-o",
                    f"cyclonedx-json={cyclonedx}",
                    "-q",
                    *exclude_flags,
                ],
                capture_output=True,
                text=True,
                timeout=300,
                check=False,
            )
            if r2.returncode != 0:
                return []
        return [p for p in (spdx, cyclonedx) if p.exists()]
    except (subprocess.SubprocessError, FileNotFoundError):
        return []


def _load_license_elections(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Read [dependencies.license_elections.<pkg>] entries from oss-publish.toml.

    Each entry should declare {upstream_licenses, elected, rationale}; only
    `elected` is consulted by the policy filter.
    """
    deps_cfg = config.get("dependencies")
    if not isinstance(deps_cfg, dict):
        return {}
    elections = deps_cfg.get("license_elections")
    if not isinstance(elections, dict):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for name, entry in elections.items():
        if isinstance(entry, dict) and isinstance(entry.get("elected"), str):
            out[name] = entry
    return out


def _apply_license_elections(
    flagged: list[tuple[str, str]],
    elections: dict[str, dict[str, Any]],
    deny: set[str],
) -> tuple[list[tuple[str, str]], list[dict[str, str]]]:
    """Partition flagged tuples into (still_failing, honored_elections).

    A flagged (pkg, license) is honored only if the user has an election entry
    for pkg AND the elected license is NOT in the outbound deny set.
    """
    remaining: list[tuple[str, str]] = []
    honored: list[dict[str, str]] = []
    seen: set[str] = set()
    for name, lic in flagged:
        entry = elections.get(name)
        elected = entry.get("elected") if entry else None
        if elected and elected not in deny:
            if name not in seen:
                honored.append(
                    {
                        "name": name,
                        "flagged_license": lic,
                        "elected": elected,
                        "rationale": str(entry.get("rationale", ""))[:240],
                    }
                )
                seen.add(name)
            continue
        remaining.append((name, lic))
    return remaining, honored


def _scan_sbom_licenses(spdx_path: Path, deny: set[str]) -> list[tuple[str, str]]:
    try:
        with spdx_path.open(encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return []
    flagged: list[tuple[str, str]] = []
    for pkg in data.get("packages", []):
        name = pkg.get("name", "?")
        licenses: set[str] = set()
        for key in ("licenseConcluded", "licenseDeclared"):
            v = pkg.get(key)
            if v and v != "NOASSERTION":
                # Parse SPDX expressions (simplified: split on AND/OR/parens)
                import re as _re

                for tok in _re.split(r"[\s\(\)]+|AND|OR|WITH", v):
                    tok = tok.strip()
                    if tok and tok != "NOASSERTION":
                        licenses.add(tok)
        for lic in licenses:
            if lic in deny:
                flagged.append((name, lic))
    return flagged


def _grype_scan(ctx: Context, spdx_path: Path) -> tuple[dict[str, int] | None, list[dict]]:
    try:
        r = subprocess.run(
            ["grype", f"sbom:{spdx_path}", "-o", "json"],
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
        data = json.loads(r.stdout) if r.stdout else {}
        counts: dict[str, int] = {}
        records: list[dict] = []
        for match in data.get("matches", [])[:RESULT_CAP]:
            vuln = match.get("vulnerability", {})
            art = match.get("artifact", {})
            sev = vuln.get("severity", "Unknown")
            counts[sev] = counts.get(sev, 0) + 1
            pkg = art.get("name", "?")
            ver = art.get("version", "?")
            cve = vuln.get("id", "?")
            fix_versions = vuln.get("fix", {}).get("versions") or []
            fix_str = ", ".join(fix_versions) if fix_versions else "none"
            desc = (vuln.get("description") or "")[:120]
            records.append(
                {
                    "file": f"{pkg}@{ver}",
                    "line": None,
                    "rule": cve,
                    "snippet_masked": f"fix: {fix_str}" + (f" — {desc}" if desc else ""),
                    "_severity": sev,
                }
            )
        # Count remaining matches beyond the cap
        all_matches = data.get("matches", [])
        for match in all_matches[RESULT_CAP:]:
            sev = match.get("vulnerability", {}).get("severity", "Unknown")
            counts[sev] = counts.get(sev, 0) + 1
        # Persist for downstream tools / report
        (ctx.iw_dir / "grype-vulnerabilities.json").write_text(r.stdout or "{}", encoding="utf-8")
        return counts, records
    except (subprocess.SubprocessError, FileNotFoundError, json.JSONDecodeError):
        return None, []


def _format_vuln_detail(records: list[dict]) -> str:
    lines = []
    for r in records:
        pkg = r.get("file", "?")
        cve = r.get("rule", "?")
        snippet = r.get("snippet_masked", "")
        lines.append(f"  {pkg}  {cve}  {snippet}")
    return "\n".join(lines)
