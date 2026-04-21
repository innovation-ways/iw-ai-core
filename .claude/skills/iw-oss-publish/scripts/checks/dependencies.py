"""OSS-DEP — Dependencies, SBOM, license policy, vulnerability scans."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from lib.context import Context
from lib.registry import register
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
            )
        )

    # OSS-DEP-01: license policy check (requires SBOM)
    spdx_path = ctx.iw_dir / "sbom.spdx.json"
    outbound = ctx.config.get("license", "Apache-2.0")
    deny = OUTBOUND_DENY.get(outbound, OUTBOUND_DENY["Apache-2.0"])
    if spdx_path.exists():
        flagged = _scan_sbom_licenses(spdx_path, deny)
        if not flagged:
            out.append(
                Finding(
                    id="OSS-DEP-01",
                    severity=Severity.MUST,
                    status=Status.PASS,
                    domain=DOMAIN,
                    summary=f"No copyleft/proprietary deps incompatible with {outbound}",
                    tool="syft",
                )
            )
        else:
            out.append(
                Finding(
                    id="OSS-DEP-01",
                    severity=Severity.MUST,
                    status=Status.FAIL,
                    domain=DOMAIN,
                    summary=f"{len(flagged)} dep(s) license-incompatible with {outbound}",
                    detail="\n".join(f"  - {name} ({lic})" for name, lic in flagged[:20]),
                    remediation="Replace incompatible deps, or change outbound license.",
                    evidence={"incompatible": [{"name": n, "license": l} for n, l in flagged[:50]]},
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
            )
        )

    # OSS-DEP-03, OSS-DEP-04: vulnerabilities via grype
    if spdx_path.exists() and ctx.has_tool("grype"):
        counts = _grype_scan(ctx, spdx_path)
        if counts:
            critical = counts.get("Critical", 0)
            high = counts.get("High", 0)
            out.append(
                Finding(
                    id="OSS-DEP-03",
                    severity=Severity.MUST,
                    status=Status.PASS if critical == 0 else Status.FAIL,
                    domain=DOMAIN,
                    summary=f"Critical vulnerabilities: {critical}",
                    detail=json.dumps(counts, indent=2) if critical else "",
                    tool="grype",
                )
            )
            out.append(
                Finding(
                    id="OSS-DEP-04",
                    severity=Severity.SHOULD,
                    status=Status.PASS if high == 0 else Status.FAIL,
                    domain=DOMAIN,
                    summary=f"High vulnerabilities: {high}",
                    detail=json.dumps(counts, indent=2) if high else "",
                    tool="grype",
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
        )
    )

    return out


def _generate_sbom(ctx: Context) -> list[Path]:
    if not ctx.has_tool("syft"):
        return []
    spdx = ctx.iw_dir / "sbom.spdx.json"
    cyclonedx = ctx.iw_dir / "sbom.cyclonedx.json"
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


def _grype_scan(ctx: Context, spdx_path: Path) -> dict[str, int]:
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
        for match in data.get("matches", []):
            sev = match.get("vulnerability", {}).get("severity", "Unknown")
            counts[sev] = counts.get(sev, 0) + 1
        # Persist for downstream tools / report
        (ctx.iw_dir / "grype-vulnerabilities.json").write_text(r.stdout or "{}", encoding="utf-8")
        return counts
    except (subprocess.SubprocessError, FileNotFoundError, json.JSONDecodeError):
        return {}
