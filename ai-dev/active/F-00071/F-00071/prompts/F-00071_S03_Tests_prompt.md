# F-00071_S03_Tests_prompt

**Work Item**: F-00071 -- Local + CI Security Scanning
**Step**: S03
**Agent**: tests-impl

---

## ⛔ Docker is off-limits / ⛔ Migrations: agents generate, daemon applies

(Standard policies.)

## Input Files

- `ai-dev/active/F-00071/F-00071_Feature_Design.md`
- S01–S02 reports
- `Makefile`, `pyproject.toml`, `.trivyignore`, `.github/workflows/security-scan.yml`

## Output Files

- New: `tests/unit/test_security_targets.py`
- `ai-dev/active/F-00071/reports/F-00071_S03_Tests_report.md`

## Context

Smoke tests that lock the public surface of F-00071 so future work doesn't accidentally remove a security target or downgrade an action pin.

## Requirements

```python
"""Regression guard for F-00071 — security scanning surface."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import tomllib
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
MAKEFILE = REPO_ROOT / "Makefile"
PYPROJECT = REPO_ROOT / "pyproject.toml"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "security-scan.yml"
TRIVYIGNORE = REPO_ROOT / ".trivyignore"

REQUIRED_MAKE_TARGETS = (
    "security-deps",
    "security-iac",
    "security-image-",   # prefix match (could be -dashboard, -daemon, etc.)
    "security-all",
    "security-report",
)

REQUIRED_DEV_DEPS = ("pip-audit", "bandit")

SHA_RE = re.compile(r"^[0-9a-f]{40}$")


@pytest.mark.parametrize("target", REQUIRED_MAKE_TARGETS)
def test_makefile_target_present(target: str) -> None:
    text = MAKEFILE.read_text()
    # Match start-of-line `target:` (with possible chars after for prefix-match targets)
    found = bool(re.search(rf"^{re.escape(target)}[\w-]*:\s", text, re.MULTILINE))
    assert found, f"Makefile target '{target}*' missing — see F-00071"


def test_workflow_file_exists() -> None:
    assert WORKFLOW.is_file()


def test_workflow_required_jobs() -> None:
    data = yaml.safe_load(WORKFLOW.read_text())
    assert "deps-audit" in data["jobs"]
    assert "iac-scan" in data["jobs"]


def test_workflow_permissions_minimal() -> None:
    data = yaml.safe_load(WORKFLOW.read_text())
    perms = data.get("permissions", {})
    assert perms.get("contents") == "read"
    assert perms.get("security-events") == "write"
    # Only those two — no `id-token`, `actions: write`, etc.
    extras = set(perms.keys()) - {"contents", "security-events"}
    assert not extras, f"Unexpected permissions: {extras}"


def test_workflow_actions_pinned_to_sha() -> None:
    text = WORKFLOW.read_text()
    # Find every `uses: <action>@<ref>` line
    pattern = re.compile(r"uses:\s*([\w./-]+)@([\w./-]+)")
    for action, ref in pattern.findall(text):
        assert SHA_RE.match(ref), (
            f"Action {action!r} pinned to non-SHA ref {ref!r} — must be a 40-char commit SHA"
        )


def test_workflow_triggers_pr_push_schedule() -> None:
    data = yaml.safe_load(WORKFLOW.read_text())
    # YAML parses `on:` to `True` because of yaml's bool aliasing — handle both keys
    on = data.get(True, data.get("on"))
    assert "pull_request" in on
    assert "push" in on
    assert "schedule" in on


@pytest.mark.parametrize("dep", REQUIRED_DEV_DEPS)
def test_dev_dep_present(dep: str) -> None:
    data = tomllib.loads(PYPROJECT.read_text())
    dev_deps = data["dependency-groups"]["dev"]
    found = any(item.startswith(dep) for item in dev_deps)
    assert found, f"Dev dep '{dep}' missing from [dependency-groups] dev — see F-00071"


def test_bandit_config_excludes_tests() -> None:
    data = tomllib.loads(PYPROJECT.read_text())
    bandit = data.get("tool", {}).get("bandit", {})
    excludes = set(bandit.get("exclude_dirs", []))
    assert "tests" in excludes
    assert "scripts" in excludes


def test_trivyignore_exists() -> None:
    assert TRIVYIGNORE.is_file()
    text = TRIVYIGNORE.read_text()
    # File should be commented-only at this stage (no active ignores)
    non_comment_lines = [
        line for line in text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    assert not non_comment_lines, (
        f".trivyignore has active ignores without justification: {non_comment_lines}"
    )
```

## Project Conventions

- File location: `tests/unit/test_security_targets.py`.
- Use `pyyaml` and stdlib `tomllib` (Python 3.12).
- No live-DB calls.

## TDD Requirement

Strip a Makefile target temporarily and re-run a single parametrized case to confirm the assertion fails clearly before claiming GREEN.

## Pre-flight Quality Gates

1. `make format`
2. `make typecheck`
3. `make lint`
4. `make test-unit`

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "tests-impl",
  "work_item": "F-00071",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["tests/unit/test_security_targets.py"],
  "preflight": {"format": "ok", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
