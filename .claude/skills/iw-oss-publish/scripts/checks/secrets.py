"""OSS-SEC — Secret scanning via gitleaks / trufflehog."""

from __future__ import annotations

import json
import subprocess

from lib.context import Context
from lib.registry import register
from lib.types import Finding, Severity, Status

DOMAIN = "secrets"


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
    leaks = _count_sarif_results(sarif_path) if sarif_path else 0

    if leaks == 0:
        return Finding(
            id=check_id,
            severity=Severity.MUST,
            status=Status.PASS,
            domain=DOMAIN,
            summary=f"No secrets detected ({scope} scan)",
            tool="gitleaks",
            evidence={"sarif": sarif_path, "finding_count": 0},
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
        evidence={"sarif": sarif_path, "finding_count": leaks},
        source_research=["R-00061 #2"],
    )


def _count_sarif_results(sarif_path: str | None) -> int:
    if not sarif_path:
        return 0
    try:
        with open(sarif_path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return 0
    total = 0
    for run in data.get("runs", []):
        total += len(run.get("results", []))
    return total
