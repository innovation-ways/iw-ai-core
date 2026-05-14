"""Baseline test: `make security-sast` reports zero blocking findings.

Locks in CR-00051's deliverable: the Semgrep baseline is clean. If a future
change introduces a new finding, this test fails loudly in CI.

The `--exclude-rule` set MUST match the Makefile's `security-sast` target. If you
edit one, edit the other — Invariant I4 of CR-00051.

Skipped when `semgrep` is not on PATH (local dev convenience — CI installs
semgrep as a dev dependency via `uv sync --dev`).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

SEMGREP_CONFIGS = ("p/python", "p/owasp-top-ten", "p/security-audit")
SEMGREP_TARGETS = ("orch", "dashboard", "executor")

# Keep this tuple in sync with the four --exclude-rule flags in the Makefile's
# `security-sast` target. Invariant I4 of CR-00051.
SEMGREP_EXCLUDE_RULES = (
    "generic.html-templates.security.unquoted-attribute-var.unquoted-attribute-var",
    "generic.html-templates.security.var-in-href.var-in-href",
    "generic.html-templates.security.var-in-script-tag.var-in-script-tag",
    "html.security.plaintext-http-link.plaintext-http-link",
)


@pytest.mark.skipif(
    shutil.which("semgrep") is None,
    reason="semgrep not installed (install with `uv sync --dev`)",
)
def test_semgrep_baseline_is_zero_blocking_findings() -> None:
    cmd: list[str] = ["uv", "run", "semgrep"]
    for cfg in SEMGREP_CONFIGS:
        cmd.extend(["--config", cfg])
    for rule in SEMGREP_EXCLUDE_RULES:
        cmd.extend(["--exclude-rule", rule])
    cmd.extend(SEMGREP_TARGETS)
    cmd.extend(["--error", "--json"])

    result = subprocess.run(  # noqa: S603 — controlled argv, no shell
        cmd,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )

    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError:
        pytest.fail(
            f"Could not parse semgrep JSON output. exit={result.returncode}\n"
            f"stdout (first 500 chars): {result.stdout[:500]!r}\n"
            f"stderr (first 500 chars): {result.stderr[:500]!r}"
        )

    findings = report.get("results", [])
    if findings:
        summary_lines = [
            f"Expected 0 blocking semgrep findings, got {len(findings)}:",
        ]
        for f in findings[:20]:
            summary_lines.append(
                f"  {f.get('path')}:{f.get('start', {}).get('line')} {f.get('check_id')}"
            )
        if len(findings) > 20:
            summary_lines.append(f"  ... ({len(findings) - 20} more)")
        pytest.fail("\n".join(summary_lines))

    assert result.returncode == 0, (
        f"semgrep exited {result.returncode} despite zero results. "
        f"stderr (first 500 chars): {result.stderr[:500]!r}"
    )
