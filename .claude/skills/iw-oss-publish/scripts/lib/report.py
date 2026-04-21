"""Report emission: markdown, JSON, SARIF stub."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .context import Context
from .types import Finding, Severity, Status


def _utc_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def summarize(findings: list[Finding]) -> dict[str, int]:
    """Count findings by severity x status."""
    counts = {
        "must_pass": 0,
        "must_fail": 0,
        "must_human": 0,
        "should_pass": 0,
        "should_fail": 0,
        "should_human": 0,
        "may_pass": 0,
        "may_fail": 0,
        "may_human": 0,
        "skip": 0,
        "total": 0,
    }
    for f in findings:
        counts["total"] += 1
        if f.status == Status.SKIP:
            counts["skip"] += 1
            continue
        key_prefix = f.severity.value.lower()
        if f.status == Status.PASS:
            counts[f"{key_prefix}_pass"] = counts.get(f"{key_prefix}_pass", 0) + 1
        elif f.status == Status.FAIL:
            counts[f"{key_prefix}_fail"] = counts.get(f"{key_prefix}_fail", 0) + 1
        elif f.status == Status.HUMAN_REQUIRED:
            counts[f"{key_prefix}_human"] = counts.get(f"{key_prefix}_human", 0) + 1
    return counts


def compute_exit_code(findings: list[Finding]) -> int:
    """Exit 1 if any MUST finding is fail or human-required; else 0."""
    for f in findings:
        if f.severity == Severity.MUST and f.status in (Status.FAIL, Status.HUMAN_REQUIRED):
            return 1
    return 0


def emit_json(ctx: Context, findings: list[Finding], skill_version: str) -> Path:
    """Write machine-readable findings to .iw/oss-publish-findings.json."""
    payload: dict[str, Any] = {
        "skill_version": skill_version,
        "generated_at": _utc_iso(),
        "target": str(ctx.target.resolve()),
        "mode": ctx.mode,
        "config": {k: v for k, v in ctx.config.items() if k not in ("checks", "tools")},
        "repo": {
            "current_branch": ctx.repo.current_branch,
            "head_sha": ctx.repo.head_sha,
            "visibility": ctx.repo.visibility,
            "remote_url": ctx.repo.remote_url,
            "commit_count": ctx.repo.commit_count,
            "contributor_email_count": ctx.repo.contributor_email_count,
            "ecosystems_detected": sorted(ctx.ecosystems),
        },
        "tools_available": ctx.tools,
        "findings": [f.to_dict() for f in findings],
        "summary": summarize(findings) | {"exit_code": compute_exit_code(findings)},
    }
    out = ctx.iw_dir / "oss-publish-findings.json"
    out.write_text(json.dumps(payload, indent=2, sort_keys=False), encoding="utf-8")
    return out


def emit_markdown(ctx: Context, findings: list[Finding]) -> Path:
    """Write human-readable report to .iw/oss-publish-report.md."""
    counts = summarize(findings)
    exit_code = compute_exit_code(findings)

    lines: list[str] = []
    cfg = ctx.config
    lines.append(f"# IW OSS Publish — {ctx.mode} — {cfg.get('project_name', '(unnamed)')}")
    lines.append("")
    lines.append(f"**Date**: {_utc_iso()}")
    lines.append(f"**Target**: `{ctx.target.resolve()}`")
    lines.append(f"**Mode**: `{ctx.mode}`")
    lines.append(f"**License**: `{cfg.get('license', 'unset')}`")
    lines.append(f"**Visibility**: `{ctx.repo.visibility}`")
    lines.append(f"**HEAD**: `{ctx.repo.head_sha[:12] if ctx.repo.head_sha else 'unknown'}`")
    lines.append(f"**Branch**: `{ctx.repo.current_branch or 'detached'}`")
    lines.append(f"**Ecosystems**: {', '.join(sorted(ctx.ecosystems)) or '(none detected)'}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| Severity | Pass | Fail | Human | Total |")
    lines.append("|----------|------|------|-------|-------|")
    for sev in ("must", "should", "may"):
        total = (
            counts.get(f"{sev}_pass", 0)
            + counts.get(f"{sev}_fail", 0)
            + counts.get(f"{sev}_human", 0)
        )
        lines.append(
            f"| {sev.upper():<8} | {counts.get(f'{sev}_pass', 0):>4} | "
            f"{counts.get(f'{sev}_fail', 0):>4} | {counts.get(f'{sev}_human', 0):>5} | {total:>5} |"
        )
    lines.append("")
    lines.append(f"**Skipped**: {counts.get('skip', 0)}")
    lines.append(f"**Exit code**: {exit_code}")
    lines.append("")

    # Missing Tier-1 tools warning
    missing = [
        t
        for t, v in ctx.tools.items()
        if v is None and t in ("gitleaks", "ripgrep", "syft", "grant", "grype")
    ]
    if missing:
        lines.append("## ⚠ Missing Tier-1 tools")
        lines.append("")
        lines.append("Some checks were skipped because required tools are missing:")
        for t in missing:
            lines.append(f"- `{t}`")
        lines.append("")
        lines.append("Install with: `bash .claude/skills/iw-oss-publish/scripts/install_tools.sh`")
        lines.append("")

    def _group(severity: Severity, status: Status) -> list[Finding]:
        return [f for f in findings if f.severity == severity and f.status == status]

    # Blockers
    blockers = _group(Severity.MUST, Status.FAIL) + _group(Severity.MUST, Status.HUMAN_REQUIRED)
    if blockers:
        lines.append("## Blockers (MUST)")
        lines.append("")
        for f in blockers:
            lines.extend(_render_finding(f))
        lines.append("")

    # Warnings
    warnings = _group(Severity.SHOULD, Status.FAIL) + _group(Severity.SHOULD, Status.HUMAN_REQUIRED)
    if warnings:
        lines.append("## Warnings (SHOULD)")
        lines.append("")
        for f in warnings:
            lines.extend(_render_finding(f))
        lines.append("")

    # Info
    info = _group(Severity.MAY, Status.FAIL) + _group(Severity.MAY, Status.HUMAN_REQUIRED)
    if info:
        lines.append("## Info (MAY)")
        lines.append("")
        for f in info:
            lines.extend(_render_finding(f))
        lines.append("")

    # Human judgment roll-up
    human = [f for f in findings if f.status == Status.HUMAN_REQUIRED]
    if human:
        lines.append("## Human Judgment Required")
        lines.append("")
        for f in human:
            lines.append(f"- **{f.id}**: {f.summary}")
            if f.remediation:
                lines.append(f"  - {f.remediation}")
        lines.append("")

    # Passes (collapsed)
    passed = [f for f in findings if f.status == Status.PASS]
    if passed:
        lines.append(f"<details><summary>✅ Passes ({len(passed)})</summary>")
        lines.append("")
        for f in passed:
            lines.append(f"- {f.id} — {f.summary}")
        lines.append("")
        lines.append("</details>")
        lines.append("")

    # Artifacts
    lines.append("## Artifacts")
    lines.append("")
    lines.append("- `.iw/oss-publish-findings.json` — machine-readable findings")
    lines.append("- `.iw/oss-publish-report.md` — this report")
    if ctx.has_tool("gitleaks"):
        lines.append(
            "- `.iw/gitleaks-tree.sarif` / `.iw/gitleaks-history.sarif` — uploadable to GitHub Code Scanning"
        )
    if ctx.has_tool("syft"):
        lines.append(
            "- `.iw/sbom.spdx.json` / `.iw/sbom.cyclonedx.json` — Software Bill of Materials"
        )
    lines.append("")

    # Next step
    lines.append("## Next Step")
    lines.append("")
    if exit_code != 0:
        lines.append(
            "Run `iw-oss-publish make_oss` to auto-fix what can be fixed, "
            "then review the resulting punchlist."
        )
    elif counts.get("should_fail", 0) + counts.get("should_human", 0) > 0:
        lines.append(
            "No blockers. Address SHOULD warnings for a clean compliance posture, "
            "then run `iw-oss-publish publish` when ready."
        )
    else:
        lines.append("Compliance is clean. Ready for `iw-oss-publish publish`.")
    lines.append("")

    out = ctx.iw_dir / "oss-publish-report.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def _render_finding(f: Finding) -> list[str]:
    out: list[str] = []
    out.append(f"### `{f.id}` — {f.summary}")
    if f.detail:
        out.append("")
        out.append(f.detail)
    if f.remediation:
        out.append("")
        out.append(f"**Remediation**: {f.remediation}")
    meta: list[str] = []
    if f.osps_control:
        meta.append(f"OSPS: `{f.osps_control}`")
    if f.tool:
        meta.append(f"Tool: `{f.tool}`")
    if f.auto_fix_available:
        meta.append("auto-fixable")
    if f.source_research:
        meta.append("Source: " + ", ".join(f.source_research))
    if meta:
        out.append("")
        out.append(f"*{' · '.join(meta)}*")
    out.append("")
    return out


def emit_sarif_combined(ctx: Context, findings: list[Finding]) -> Path | None:
    """Emit a minimal SARIF 2.1.0 file covering non-secrets findings.

    Gitleaks emits its own SARIF; this file complements it with iw-oss-publish
    structural findings so GitHub Code Scanning can surface both.
    """
    results = []
    for f in findings:
        if f.status != Status.FAIL or not f.id.startswith("OSS-"):
            continue
        level = {"MUST": "error", "SHOULD": "warning", "MAY": "note", "INFO": "note"}.get(
            f.severity.value, "note"
        )
        results.append(
            {
                "ruleId": f.id,
                "level": level,
                "message": {"text": f.summary + (f"\n{f.detail}" if f.detail else "")},
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": str(ctx.target.name)},
                        }
                    }
                ],
            }
        )

    if not results:
        return None

    sarif = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "iw-oss-publish",
                        "informationUri": "https://github.com/innovation-ways/iw-ai-core",
                        "rules": [],
                    }
                },
                "results": results,
            }
        ],
    }
    out = ctx.iw_dir / "iw-oss-publish.sarif"
    out.write_text(json.dumps(sarif, indent=2), encoding="utf-8")
    return out
