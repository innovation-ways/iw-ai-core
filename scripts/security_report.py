#!/usr/bin/env python3
"""Aggregate pip-audit, bandit, and trivy-iac JSON outputs into a combined report."""

from __future__ import annotations

import json
import sys
from pathlib import Path

SECURITY_DIR = Path("tests/output/security")
OUTPUT_FILE = SECURITY_DIR / "report.json"

TOOLS = {
    "pip-audit": SECURITY_DIR / "pip-audit.json",
    "bandit": SECURITY_DIR / "bandit.json",
    "trivy-iac": SECURITY_DIR / "trivy-iac.json",
}


def load_json(path: Path) -> dict | None:
    """Load a JSON file, returning None when the file is missing or malformed.

    Args:
        path: Path to the JSON file to read.

    Returns:
        Parsed dict, or None when the file does not exist or cannot be parsed.
    """
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def summarize_pip_audit(data: dict) -> list[dict]:
    """Extract vulnerability findings from a pip-audit JSON report.

    Args:
        data: Parsed pip-audit JSON output containing a ``dependencies`` list.

    Returns:
        List of dicts with ``package``, ``vuln_id``, ``fix_versions``, and
        ``severity`` keys.
    """
    vulns = []
    for dep in data.get("dependencies", []):
        for vuln in dep.get("vulns", []):
            vulns.append(
                {
                    "package": dep.get("name", "?"),
                    "vuln_id": vuln.get("id", "?"),
                    "fix_versions": vuln.get("fix_versions", []),
                    "severity": vuln.get("severity", "?"),
                }
            )
    return vulns


def summarize_bandit(data: dict) -> list[dict]:
    """Extract findings from a bandit JSON report.

    Args:
        data: Parsed bandit JSON output containing a ``results`` list.

    Returns:
        List of dicts with ``filename``, ``issue_id``, ``severity``,
        ``confidence``, ``line``, and ``message`` keys.
    """
    findings = []
    for issue in data.get("results", []):
        findings.append(
            {
                "filename": issue.get("filename", "?"),
                "issue_id": issue.get("issue_id", "?"),
                "severity": issue.get("issue_severity", "?"),
                "confidence": issue.get("issue_confidence", "?"),
                "line": issue.get("line", "?"),
                "message": issue.get("text", "?"),
            }
        )
    return findings


def summarize_trivy_iac(data: dict) -> list[dict]:
    """Extract vulnerability findings from a trivy IAC JSON report.

    Args:
        data: Parsed trivy JSON output containing a ``Results`` list.

    Returns:
        List of dicts with ``target``, ``vuln_id``, ``severity``, and
        ``description`` (truncated to 120 chars) keys.
    """
    findings = []
    for result in data.get("Results", []):
        for vuln in result.get("Vulnerabilities", []) or []:
            findings.append(
                {
                    "target": result.get("Target", "?"),
                    "vuln_id": vuln.get("VulnerabilityID", "?"),
                    "severity": vuln.get("Severity", "?"),
                    "description": vuln.get("Description", "?")[:120],
                }
            )
    return findings


def build_markdown(summary: dict) -> str:
    """Render the aggregated security summary as a Markdown string.

    Args:
        summary: Dict mapping tool names to their status, findings list, and
                 finding count, as produced by ``main``.

    Returns:
        Markdown string with one ``##`` section per tool and up to 20 findings
        listed per section.
    """
    lines = [
        "# Security Scan Summary",
        "",
    ]
    for tool, result in summary.items():
        if result["status"] == "skipped":
            lines.append(f"## {tool}: SKIPPED (unavailable)")
        else:
            lines.append(f"## {tool}: {result['finding_count']} finding(s)")
            if result["findings"]:
                for f in result["findings"][:20]:
                    if tool == "pip-audit":
                        lines.append(
                            f"  - **{f['vuln_id']}** in {f['package']} "
                            f"(severity={f['severity']}, fix={f['fix_versions']})"
                        )
                    elif tool == "bandit":
                        lines.append(
                            f"  - [{f['issue_id']}] {f['filename']}:{f['line']} "
                            f"({f['severity']}/{f['confidence']}) {f['message'][:80]}"
                        )
                    elif tool == "trivy-iac":
                        lines.append(
                            f"  - **{f['vuln_id']}** in {f['target']} "
                            f"({f['severity']}): {f['description'][:80]}"
                        )
                if len(result["findings"]) > 20:
                    lines.append(f"  ... and {len(result['findings']) - 20} more")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    """Aggregate tool outputs from ``tests/output/security/`` and write ``report.json``.

    Returns:
        0 always; missing tool outputs are reported as skipped rather than errors.
    """
    summary: dict[str, dict] = {}

    # pip-audit
    raw = load_json(TOOLS["pip-audit"])
    if raw is None:
        summary["pip-audit"] = {"status": "skipped", "findings": [], "finding_count": 0}
    else:
        findings = summarize_pip_audit(raw)
        summary["pip-audit"] = {
            "status": "ok",
            "findings": findings,
            "finding_count": len(findings),
        }

    # bandit
    raw = load_json(TOOLS["bandit"])
    if raw is None:
        summary["bandit"] = {"status": "skipped", "findings": [], "finding_count": 0}
    else:
        findings = summarize_bandit(raw)
        summary["bandit"] = {"status": "ok", "findings": findings, "finding_count": len(findings)}

    # trivy-iac
    raw = load_json(TOOLS["trivy-iac"])
    if raw is None:
        summary["trivy-iac"] = {"status": "skipped", "findings": [], "finding_count": 0}
    else:
        findings = summarize_trivy_iac(raw)
        summary["trivy-iac"] = {
            "status": "ok",
            "findings": findings,
            "finding_count": len(findings),
        }

    report = {
        "summary": summary,
        "markdown": build_markdown(summary),
    }

    SECURITY_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
