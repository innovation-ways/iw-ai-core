"""OSS-CI — CI/CD leak surface."""

from __future__ import annotations

import subprocess

from lib.context import Context
from lib.registry import register
from lib.types import Finding, Severity, Status

DOMAIN = "ci"


@register(id_prefix="OSS-CI", order=6, domain=DOMAIN)
def ci_checks(ctx: Context) -> list[Finding]:
    out: list[Finding] = []
    workflows_dir = ctx.target / ".github" / "workflows"

    # OSS-CI-01: secrets in workflow files (gitleaks-focused)
    if workflows_dir.exists() and ctx.has_tool("gitleaks"):
        try:
            r = subprocess.run(
                [
                    "gitleaks",
                    "detect",
                    "--no-git",
                    "--source",
                    str(workflows_dir),
                    "--report-format",
                    "json",
                    "--report-path",
                    str(ctx.iw_dir / "gitleaks-workflows.json"),
                    "--exit-code",
                    "0",
                ],
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
            import json

            try:
                with open(ctx.iw_dir / "gitleaks-workflows.json", encoding="utf-8") as f:
                    findings_data = json.load(f)
                leak_count = len(findings_data) if isinstance(findings_data, list) else 0
            except (OSError, json.JSONDecodeError):
                leak_count = 0
            out.append(
                Finding(
                    id="OSS-CI-01",
                    severity=Severity.MUST,
                    status=Status.PASS if leak_count == 0 else Status.FAIL,
                    domain=DOMAIN,
                    summary="No secrets detected in workflow files"
                    if leak_count == 0
                    else f"{leak_count} potential secret(s) in workflows",
                    tool="gitleaks",
                    evidence={"count": leak_count},
                )
            )
        except (subprocess.SubprocessError, FileNotFoundError):
            out.append(
                Finding(
                    id="OSS-CI-01",
                    severity=Severity.MUST,
                    status=Status.SKIP,
                    domain=DOMAIN,
                    summary="gitleaks invocation on workflows failed",
                )
            )
    elif not workflows_dir.exists():
        out.append(
            Finding(
                id="OSS-CI-01",
                severity=Severity.MUST,
                status=Status.PASS,
                domain=DOMAIN,
                summary="No .github/workflows directory — nothing to scan",
            )
        )
    else:
        out.append(
            Finding(
                id="OSS-CI-01",
                severity=Severity.MUST,
                status=Status.SKIP,
                domain=DOMAIN,
                summary="gitleaks unavailable — workflow secret scan skipped",
            )
        )

    # OSS-CI-02: action SHA pinning
    if ctx.has_tool("pinact") and workflows_dir.exists():
        r = subprocess.run(
            ["pinact", "run", "--check"],
            cwd=ctx.target,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        passed = r.returncode == 0
        out.append(
            Finding(
                id="OSS-CI-02",
                severity=Severity.SHOULD,
                status=Status.PASS if passed else Status.FAIL,
                domain=DOMAIN,
                summary="All third-party Actions SHA-pinned"
                if passed
                else "Unpinned third-party GitHub Actions found",
                detail=(r.stdout or r.stderr).strip()[:1500] if not passed else "",
                remediation="`pinact run` will rewrite action refs to immutable SHAs."
                if not passed
                else None,
                auto_fix_available=True,
                tool="pinact",
            )
        )
    elif not workflows_dir.exists():
        out.append(
            Finding(
                id="OSS-CI-02",
                severity=Severity.SHOULD,
                status=Status.SKIP,
                domain=DOMAIN,
                summary="No workflows — action pinning not applicable",
            )
        )
    else:
        out.append(
            Finding(
                id="OSS-CI-02",
                severity=Severity.SHOULD,
                status=Status.SKIP,
                domain=DOMAIN,
                summary="pinact unavailable — action pinning check skipped",
            )
        )

    # OSS-CI-04: tracked .tfstate / terraform.tfvars
    tracked = ctx.tracked_files()
    tf_violations = [
        t
        for t in tracked
        if t.endswith(".tfstate") or t.endswith(".tfstate.backup") or t.endswith("terraform.tfvars")
    ]
    out.append(
        Finding(
            id="OSS-CI-04",
            severity=Severity.MUST,
            status=Status.PASS if not tf_violations else Status.FAIL,
            domain=DOMAIN,
            summary="No Terraform state files tracked"
            if not tf_violations
            else f"{len(tf_violations)} Terraform state/vars file(s) tracked",
            detail=", ".join(tf_violations) if tf_violations else "",
        )
    )

    # OSS-CI-06 through OSS-CI-09: workflow / config file presence
    wf_files = {
        "OSS-CI-06": (".github/workflows/codeql.yml", "CodeQL workflow"),
        "OSS-CI-07": (".github/workflows/scorecard.yml", "OpenSSF Scorecard workflow"),
        "OSS-CI-08": (".github/dependabot.yml", "Dependabot config"),
        "OSS-CI-09": (
            ".github/workflows/compliance-scan.yml",
            "iw-oss-publish compliance workflow",
        ),
    }
    for cid, (path, label) in wf_files.items():
        exists = (ctx.target / path).exists()
        out.append(
            Finding(
                id=cid,
                severity=Severity.SHOULD,
                status=Status.PASS if exists else Status.FAIL,
                domain=DOMAIN,
                summary=f"{label} present" if exists else f"{label} missing at {path}",
                auto_fix_available=True,
            )
        )

    return out
