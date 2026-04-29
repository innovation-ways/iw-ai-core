# F-00070_S03_Tests_prompt

**Work Item**: F-00070 -- Pre-commit Hardening
**Step**: S03
**Agent**: tests-impl

---

## ⛔ Docker is off-limits / ⛔ Migrations: agents generate, daemon applies

(Standard policies.)

## Input Files

- `ai-dev/active/F-00070/F-00070_Feature_Design.md`
- S01–S02 reports
- `.pre-commit-config.yaml`
- `tests/CLAUDE.md`

## Output Files

- New: `tests/unit/test_precommit_config.py`
- `ai-dev/active/F-00070/reports/F-00070_S03_Tests_report.md`

## Context

Write a smoke test that asserts the expected hook IDs are present in `.pre-commit-config.yaml`. This is a regression guard: if a future agent removes a hook, this test fails immediately.

## Requirements

### 1. Smoke test

```python
"""Regression guard for .pre-commit-config.yaml — F-00070."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / ".pre-commit-config.yaml"

EXPECTED_HOOK_IDS = {
    # Existing
    "ruff",
    "ruff-format",
    "mypy",
    # Added by F-00070
    "trailing-whitespace",
    "end-of-file-fixer",
    "check-yaml",
    "check-json",
    "check-toml",
    "check-added-large-files",
    "detect-private-key",
    "check-merge-conflict",
    "check-case-conflict",
}


def _all_hook_ids(config_path: Path) -> set[str]:
    data = yaml.safe_load(config_path.read_text())
    ids: set[str] = set()
    for repo in data.get("repos", []):
        for hook in repo.get("hooks", []):
            ids.add(hook["id"])
    return ids


def test_precommit_config_exists() -> None:
    assert CONFIG_PATH.is_file(), f".pre-commit-config.yaml missing at {CONFIG_PATH}"


@pytest.mark.parametrize("hook_id", sorted(EXPECTED_HOOK_IDS))
def test_expected_hook_present(hook_id: str) -> None:
    assert hook_id in _all_hook_ids(CONFIG_PATH), (
        f"Hook '{hook_id}' missing from .pre-commit-config.yaml — "
        f"see F-00070 design doc"
    )


def test_pre_commit_hooks_repo_rev_pinned() -> None:
    """Reject HEAD / latest / branch refs."""
    data = yaml.safe_load(CONFIG_PATH.read_text())
    for repo in data.get("repos", []):
        rev = str(repo.get("rev", ""))
        url = str(repo.get("repo", ""))
        assert rev, f"Repo {url} has no rev pin"
        assert rev.lower() not in {"head", "latest", "main", "master"}, (
            f"Repo {url} uses unpinned rev '{rev}' — pin to a tag"
        )


def test_large_files_threshold_set() -> None:
    data = yaml.safe_load(CONFIG_PATH.read_text())
    for repo in data.get("repos", []):
        for hook in repo.get("hooks", []):
            if hook.get("id") == "check-added-large-files":
                args = " ".join(hook.get("args", []))
                assert "--maxkb=" in args, "check-added-large-files needs --maxkb=<n>"
                return
    pytest.fail("check-added-large-files hook not found")
```

### 2. PyYAML availability

`pyyaml` is required. Verify it's in dev deps; if not, add it. (It's commonly transitive via testcontainers or other deps — check first via `uv tree`.)

### 3. No live-DB calls

Tests are filesystem-only. No DB, no API.

## Project Conventions

- File goes under `tests/unit/test_precommit_config.py`.
- Use `pytest.mark.parametrize` for the hook ID assertions so each missing hook reports as a distinct failure.

## TDD Requirement

For each test, run RED first (deliberately strip a hook from a temp copy of the config and verify the test fails) before claiming GREEN. The actual config in the repo should make all tests pass after F-00070 S01.

## Pre-flight Quality Gates

1. `make format`
2. `make typecheck`
3. `make lint`
4. `make test-unit` — passes including the new tests

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "tests-impl",
  "work_item": "F-00070",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/unit/test_precommit_config.py"
  ],
  "preflight": {"format": "ok", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
