"""OSS-PII — Personal data in fixtures / contributor emails."""

from __future__ import annotations

import re
import subprocess

from lib.context import Context
from lib.registry import register
from lib.types import Finding, Severity, Status

DOMAIN = "privacy"

ALLOW_EMAIL_DOMAINS = {
    "example.com",
    "example.org",
    "example.net",
    "test.invalid",
    "users.noreply.github.com",
}

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})")
SSN_LIKE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")  # US SSN shape (not a validator)

# Fixture/test directories to scan
PII_SCAN_DIRS = ["tests", "test", "fixtures", "data", "seeds"]


@register(id_prefix="OSS-PII", order=10, domain=DOMAIN)
def privacy(ctx: Context) -> list[Finding]:
    out: list[Finding] = []

    # OSS-PII-01: real-looking emails in tests/fixtures
    if not ctx.has_tool("ripgrep"):
        out.append(
            Finding(
                id="OSS-PII-01",
                severity=Severity.MUST,
                status=Status.SKIP,
                domain=DOMAIN,
                summary="ripgrep unavailable — PII scan skipped",
                auto_apply_safe=False,
            )
        )
    else:
        flagged = _scan_fixtures_for_emails(ctx)
        if not flagged:
            out.append(
                Finding(
                    id="OSS-PII-01",
                    severity=Severity.MUST,
                    status=Status.PASS,
                    domain=DOMAIN,
                    summary="No real-looking emails in test fixtures",
                    auto_apply_safe=False,
                )
            )
        else:
            out.append(
                Finding(
                    id="OSS-PII-01",
                    severity=Severity.MUST,
                    status=Status.FAIL,
                    domain=DOMAIN,
                    summary=f"{len(flagged)} real-looking email(s) in fixtures",
                    detail="\n".join(flagged[:15]),
                    remediation="Replace with @example.com or @test.invalid; do not commit real PII.",
                    evidence=build_results_evidence(
                        parse_rg_lines(flagged, rule_id="OSS-PII-01"),
                        total=len(flagged),
                    ),
                    auto_apply_safe=False,
                )
            )

    # OSS-PII-02: SSN-shaped patterns in fixtures
    if ctx.has_tool("ripgrep"):
        ssn_hits = _scan_fixtures(ctx, r"\b\d{3}-\d{2}-\d{4}\b")
        if not ssn_hits:
            out.append(
                Finding(
                    id="OSS-PII-02",
                    severity=Severity.MUST,
                    status=Status.PASS,
                    domain=DOMAIN,
                    summary="No SSN-shaped patterns in fixtures",
                    auto_apply_safe=False,
                )
            )
        else:
            out.append(
                Finding(
                    id="OSS-PII-02",
                    severity=Severity.MUST,
                    status=Status.HUMAN_REQUIRED,
                    domain=DOMAIN,
                    summary=f"{len(ssn_hits)} SSN-shaped pattern(s) — human review required",
                    detail="\n".join(ssn_hits[:10]),
                    remediation="Verify test SSNs; replace with obviously fake values like 000-00-0000.",
                    evidence=build_results_evidence(
                        parse_rg_lines(ssn_hits, rule_id="OSS-PII-02"),
                        total=len(ssn_hits),
                    ),
                    auto_apply_safe=False,
                )
            )

    # OSS-PII-03: contributor email enumeration (cross-reference with OSS-HIST-03)
    if ctx.repo.contributor_email_count:
        out.append(
            Finding(
                id="OSS-PII-03",
                severity=Severity.SHOULD,
                status=Status.PASS,
                domain=DOMAIN,
                summary=f"{ctx.repo.contributor_email_count} distinct contributor email(s) in history",
                detail="See OSS-HIST-03 for non-noreply breakdown.",
                auto_apply_safe=False,
            )
        )

    return out


def _scan_fixtures(ctx: Context, pattern: str) -> list[str]:
    hits: list[str] = []
    for d in PII_SCAN_DIRS:
        path = ctx.target / d
        if not path.exists():
            continue
        try:
            r = subprocess.run(
                [
                    "rg",
                    "--no-heading",
                    "--with-filename",
                    "--line-number",
                    "--color=never",
                    "-P",
                    pattern,
                    str(path),
                ],
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
            hits.extend(ln for ln in r.stdout.splitlines() if ln.strip())
        except (subprocess.SubprocessError, FileNotFoundError):
            continue
    return hits


def _scan_fixtures_for_emails(ctx: Context) -> list[str]:
    raw_hits = _scan_fixtures(ctx, r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
    # Filter allowlisted domains
    filtered: list[str] = []
    for line in raw_hits:
        m = EMAIL_RE.search(line)
        if not m:
            continue
        domain = m.group(1).lower()
        if domain in ALLOW_EMAIL_DOMAINS:
            continue
        if domain.endswith(".example") or domain.endswith(".invalid") or domain.endswith(".test"):
            continue
        filtered.append(line)
    return filtered
