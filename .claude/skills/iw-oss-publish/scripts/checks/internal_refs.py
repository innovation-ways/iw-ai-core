"""OSS-REF — Internal reference detection (IPs, FQDNs, paths, emails)."""

from __future__ import annotations

import re
import subprocess
from typing import Any

from lib.context import Context
from lib.registry import register
from lib.results import RESULT_CAP, build_results_evidence, parse_rg_lines
from lib.types import Finding, Severity, Status

DOMAIN = "internal_refs"

# Directories to exclude by default (documentation, tests, fixtures, skill itself)
EXCLUDES = [
    "docs/**",
    "tests/**",
    "examples/**",
    "fixtures/**",
    ".iw/**",
    ".claude/**",
    "skills/iw-oss-publish/**",
    "**/vendor/**",
    "**/node_modules/**",
    "**/*.min.js",
    "**/*.min.css",
    "**/*.md",
    "**/*.lock",
    "package-lock.json",
    "uv.lock",
]

MAX_SAMPLE_CHARS = 200
MAX_DETAIL_CHARS = 8000


@register(id_prefix="OSS-REF", order=5, domain=DOMAIN)
def internal_refs(ctx: Context) -> list[Finding]:
    out: list[Finding] = []

    if not ctx.has_tool("ripgrep"):
        out.append(
            Finding(
                id="OSS-REF-ALL",
                severity=Severity.MUST,
                status=Status.SKIP,
                domain=DOMAIN,
                summary="ripgrep unavailable — internal-ref checks skipped",
                remediation="Install ripgrep: bash .claude/skills/iw-oss-publish/scripts/install_tools.sh",
                auto_apply_safe=False,
            )
        )
        return out

    # OSS-REF-01: RFC 1918 private IPs
    rfc1918 = _rg_search(
        ctx,
        r"(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})",
    )
    out.append(
        _result_to_finding(
            "OSS-REF-01",
            Severity.MUST,
            "RFC 1918 private IP addresses",
            rfc1918,
            remediation_hit="Replace with `example.com` or placeholder; move realistic examples to `docs/`.",
        )
    )

    # OSS-REF-02: internal FQDN suffixes
    suffixes = ctx.config.get("internal_fqdn_suffixes", [])
    if suffixes:
        pattern = (
            r"\b[a-zA-Z0-9][a-zA-Z0-9-]{0,62}(" + "|".join(re.escape(s) for s in suffixes) + r")\b"
        )
        hits = _rg_search(ctx, pattern)
        out.append(
            _result_to_finding(
                "OSS-REF-02",
                Severity.MUST,
                "Internal FQDN suffixes (.internal/.corp/.local/…)",
                hits,
                remediation_hit="Replace with `example.com` or remove.",
            )
        )

    # OSS-REF-03: absolute user home paths
    hits = _rg_search(ctx, r"/(?:home|Users)/[A-Za-z][\w.-]+")
    out.append(
        _result_to_finding(
            "OSS-REF-03",
            Severity.SHOULD,
            "Absolute user home paths",
            hits,
            remediation_hit="Use `~` or environment variables instead.",
        )
    )

    # OSS-REF-04: employee email addresses (configurable domains)
    domains = ctx.config.get("internal_email_domains", [])
    if domains:
        pattern = r"[A-Za-z0-9._%+-]+@(?:" + "|".join(re.escape(d) for d in domains) + r")"
        hits = _rg_search(
            ctx,
            pattern,
            extra_excludes=[
                "SECURITY.md",
                "CODE_OF_CONDUCT.md",
                "CONTRIBUTING.md",
                "SUPPORT.md",
                "TRADEMARK.md",
            ],
        )
        out.append(
            _result_to_finding(
                "OSS-REF-04",
                Severity.SHOULD,
                f"Employee email addresses ({', '.join(domains)})",
                hits,
                remediation_hit="Remove or replace with group-alias email.",
            )
        )

    # OSS-REF-05: internal chat/tracker URLs
    chat_pattern = (
        r"(?:[a-z0-9-]+\.slack\.com|[a-z0-9-]+\.atlassian\.net/browse/|linear\.app/[a-z0-9-]+)"
    )
    hits = _rg_search(ctx, chat_pattern)
    out.append(
        _result_to_finding(
            "OSS-REF-05",
            Severity.MAY,
            "Internal chat/tracker URLs (Slack/Jira/Linear)",
            hits,
            remediation_hit="Remove or redact tenant-specific links.",
        )
    )

    return out


def _rg_search(
    ctx: Context, pattern: str, extra_excludes: list[str] | None = None
) -> dict[str, Any]:
    """Run ripgrep and return ``{count, lines, error?}``.

    ``lines`` are the raw ``path:line:text`` records (one per match), capped
    at :data:`RESULT_CAP * 2` so a runaway scan can't pull megabytes of stdout
    into memory; ``count`` is always the unbounded total. The caller turns
    ``lines`` into structured records via ``parse_rg_lines``.
    """
    excludes = list(EXCLUDES) + (extra_excludes or [])
    args = [
        "rg",
        "--no-heading",
        "--with-filename",
        "--line-number",
        "--color=never",
        f"--max-columns={MAX_SAMPLE_CHARS}",
        "--max-columns-preview",
        "-P",
    ]
    for e in excludes:
        args.extend(["-g", "!" + e])
    args.extend([pattern, str(ctx.target)])
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=60, check=False)
    except (subprocess.SubprocessError, FileNotFoundError):
        return {"count": 0, "lines": [], "error": "ripgrep invocation failed"}
    raw_lines = [ln for ln in r.stdout.splitlines() if ln.strip()]
    return {
        "count": len(raw_lines),
        "lines": [ln[:MAX_SAMPLE_CHARS] for ln in raw_lines[: RESULT_CAP * 2]],
    }


def _result_to_finding(
    check_id: str,
    severity: Severity,
    label: str,
    result: dict[str, Any],
    remediation_hit: str,
) -> Finding:
    if "error" in result:
        return Finding(
            id=check_id,
            severity=severity,
            status=Status.SKIP,
            domain=DOMAIN,
            summary=f"{label}: scan error",
            detail=result["error"],
            auto_apply_safe=False,
        )
    if result["count"] == 0:
        return Finding(
            id=check_id,
            severity=severity,
            status=Status.PASS,
            domain=DOMAIN,
            summary=f"No {label.lower()} detected",
            auto_apply_safe=False,
        )
    records = parse_rg_lines(result["lines"], rule_id=check_id)
    detail_body = "First matches:\n" + "\n".join(result["lines"][:10])
    if len(detail_body) > MAX_DETAIL_CHARS:
        detail_body = detail_body[:MAX_DETAIL_CHARS] + "\n… (truncated)"
    return Finding(
        id=check_id,
        severity=severity,
        status=Status.FAIL,
        domain=DOMAIN,
        summary=f"{result['count']} hit(s) for {label.lower()}",
        detail=detail_body,
        remediation=remediation_hit
        + " Review and decide per hit; excluded paths: `docs/`, `tests/`, `examples/`.",
        evidence=build_results_evidence(records, total=result["count"]),
        auto_apply_safe=False,
    )
