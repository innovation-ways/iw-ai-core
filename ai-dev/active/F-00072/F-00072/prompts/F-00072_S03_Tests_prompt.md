# F-00072_S03_Tests_prompt

**Work Item**: F-00072 -- Pragmatic Migration Safety + Schema Validation
**Step**: S03
**Agent**: tests-impl

---

## ⛔ Docker is off-limits / ⛔ Migrations: agents generate, daemon applies

(Standard policies.)

## Input Files

- `ai-dev/active/F-00072/F-00072_Feature_Design.md`
- S01–S02 reports
- `tests/integration/test_migration_roundtrip.py`
- `.github/workflows/schema-validation.yml`

## Output Files

- New: `tests/unit/test_migration_roundtrip_targets.py`
- `ai-dev/active/F-00072/reports/F-00072_S03_Tests_report.md`

## Context

Smoke regression guard locking the public surface of F-00072.

## Requirements

```python
"""Regression guard for F-00072 — migration safety surface."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
ROUNDTRIP_TEST = REPO_ROOT / "tests" / "integration" / "test_migration_roundtrip.py"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "schema-validation.yml"

SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def test_roundtrip_test_exists() -> None:
    assert ROUNDTRIP_TEST.is_file(), (
        "tests/integration/test_migration_roundtrip.py missing — see F-00072"
    )


def test_roundtrip_uses_pytest_integration_marker() -> None:
    text = ROUNDTRIP_TEST.read_text()
    assert "@pytest.mark.integration" in text, (
        "Roundtrip test must be marked @pytest.mark.integration so it runs "
        "under `make test-integration`"
    )


def test_roundtrip_parametrizes_revisions() -> None:
    text = ROUNDTRIP_TEST.read_text()
    assert "@pytest.mark.parametrize" in text, (
        "Roundtrip test must parametrize over revisions"
    )
    # Should NOT hardcode revision IDs (12-char alembic hashes)
    hardcoded_revs = re.findall(r'"[0-9a-f]{12}"', text)
    assert not hardcoded_revs, (
        f"Roundtrip test appears to hardcode revisions: {hardcoded_revs} — "
        f"must read from alembic history dynamically"
    )


def test_workflow_exists() -> None:
    assert WORKFLOW.is_file()


def test_workflow_runs_alembic_check() -> None:
    text = WORKFLOW.read_text()
    assert "alembic check" in text, (
        "schema-validation workflow must run `alembic check`"
    )


def test_workflow_actions_pinned_to_sha() -> None:
    text = WORKFLOW.read_text()
    pattern = re.compile(r"uses:\s*([\w./-]+)@([\w./-]+)")
    for action, ref in pattern.findall(text):
        assert SHA_RE.match(ref), (
            f"Action {action!r} pinned to non-SHA ref {ref!r}"
        )


def test_workflow_permissions_minimal() -> None:
    data = yaml.safe_load(WORKFLOW.read_text())
    perms = data.get("permissions", {})
    assert perms == {"contents": "read"}, (
        f"schema-validation must have only contents: read — got {perms}"
    )


def test_workflow_postgres_service_present() -> None:
    data = yaml.safe_load(WORKFLOW.read_text())
    job = next(iter(data["jobs"].values()))
    services = job.get("services", {})
    assert "postgres" in services, "Workflow must declare a postgres service"


def test_roundtrip_no_downgrade_minus_one() -> None:
    """Rule 4a: downgrade must use explicit revision ID, never -1."""
    text = ROUNDTRIP_TEST.read_text()
    # Catch both alembic.command and subprocess forms
    assert 'downgrade", "-1"' not in text, (
        "Roundtrip test uses `downgrade -1` — rule 4a requires an explicit parent revision ID"
    )
    assert '"downgrade", "-1"' not in text, (
        "Roundtrip test uses `downgrade -1` — rule 4a requires an explicit parent revision ID"
    )
    assert "downgrade -1" not in text, (
        "Roundtrip test uses `downgrade -1` — rule 4a requires an explicit parent revision ID"
    )
```

## Project Conventions

- File location: `tests/unit/test_migration_roundtrip_targets.py`.
- Filesystem-only; no live-DB.
- Use `pyyaml`.

## TDD Requirement

Strip a string (e.g. `alembic check` from the workflow) temporarily, confirm the corresponding test fails clearly, then restore.

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
  "work_item": "F-00072",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["tests/unit/test_migration_roundtrip_targets.py"],
  "preflight": {"format": "ok", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
