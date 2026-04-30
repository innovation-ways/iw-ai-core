# F-00073_S03_Tests_prompt

**Work Item**: F-00073 -- Smoke Gate + Active Test CI + Logging Tests
**Step**: S03
**Agent**: tests-impl

---

## ⛔ Docker is off-limits / ⛔ Migrations: agents generate, daemon applies

(Standard policies.)

## Input Files

- `ai-dev/active/F-00073/F-00073_Feature_Design.md`
- S01–S02 reports
- `tests/unit/test_make_targets.py` — created by F-00069's S05 (already in main)
- `pyproject.toml`, `Makefile`, `.github/workflows/test-quality.yml`

## Output Files

- Modified: `tests/unit/test_make_targets.py` (extend with F-00073 assertions). If the file does not exist (F-00069's deliverable was renamed), create it.
- `ai-dev/active/F-00073/reports/F-00073_S03_Tests_report.md`

## Context

Add regression-guard tests asserting the F-00073 surface is intact: `make smoke` target, `smoke` marker registration, `test-quality.yml` workflow with the right jobs, and SHA-pinning of the new workflow.

## Requirements

Append (or create) the following tests in `tests/unit/test_make_targets.py`:

```python
"""F-00073 additions to the make-targets regression guard."""
# (Append below the F-00069 tests; do not duplicate setup.)

import re
from pathlib import Path

import pytest
import tomllib
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = REPO_ROOT / "pyproject.toml"
MAKEFILE = REPO_ROOT / "Makefile"
TEST_QUALITY = REPO_ROOT / ".github" / "workflows" / "test-quality.yml"

SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def test_smoke_marker_registered() -> None:
    data = tomllib.loads(PYPROJECT.read_text())
    markers = data["tool"]["pytest"]["ini_options"].get("markers", [])
    assert any(m.startswith("smoke:") for m in markers), (
        "Marker 'smoke' must be registered in pyproject.toml — see F-00073"
    )


def test_make_smoke_target_exists() -> None:
    text = MAKEFILE.read_text()
    assert re.search(r"^smoke:\s", text, re.MULTILINE), (
        "Makefile target `smoke` missing — see F-00073"
    )


def test_make_smoke_uses_strict_markers() -> None:
    text = MAKEFILE.read_text()
    smoke_section = re.search(r"^smoke:\s(.+?)(?:\n[\w-]+:|\Z)", text, re.MULTILINE | re.DOTALL)
    assert smoke_section, "Could not locate smoke target body"
    assert "--strict-markers" in smoke_section.group(1), (
        "make smoke must pass --strict-markers"
    )


def test_test_quality_workflow_exists() -> None:
    assert TEST_QUALITY.is_file()


@pytest.mark.parametrize("job", ["lint-typecheck", "unit", "integration", "smoke"])
def test_test_quality_workflow_has_job(job: str) -> None:
    data = yaml.safe_load(TEST_QUALITY.read_text())
    assert job in data["jobs"], f"test-quality.yml missing job {job!r}"


def test_test_quality_workflow_actions_pinned() -> None:
    text = TEST_QUALITY.read_text()
    pattern = re.compile(r"uses:\s*([\w./-]+)@([\w./-]+)")
    for action, ref in pattern.findall(text):
        assert SHA_RE.match(ref), (
            f"Action {action!r} pinned to non-SHA ref {ref!r}"
        )


def test_test_quality_workflow_permissions_minimal() -> None:
    data = yaml.safe_load(TEST_QUALITY.read_text())
    perms = data.get("permissions", {})
    assert perms == {"contents": "read"}, (
        f"test-quality.yml permissions must be `contents: read` only — got {perms}"
    )


def test_smoke_set_at_least_10_tests() -> None:
    """Lock that we have at least 10 tests with the smoke marker.

    This guards against accidental marker removal.
    """
    import subprocess
    result = subprocess.run(
        ["uv", "run", "pytest", "tests", "-m", "smoke", "--collect-only", "-q"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    # Count lines that look like test IDs (file::test pattern)
    test_ids = [
        line for line in result.stdout.splitlines()
        if "::" in line and not line.startswith("=")
    ]
    assert len(test_ids) >= 10, (
        f"Expected ≥10 smoke tests; found {len(test_ids)}.\n"
        f"Output:\n{result.stdout}"
    )
```

The last test runs pytest as a subprocess. This is a unit test that incidentally invokes pytest in `--collect-only` mode (no actual test execution, no DB) — fast enough for the unit suite. If it slows things down materially, move it to integration.

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

Prior incidents had tests that checked EXISTENCE only and still passed when the feature was broken.
For configuration and file-structure tests, verify SPECIFIC VALUES:

- BAD: `assert "smoke" in markers_str` (passes even if the entry is malformed or in a comment)
- GOOD: `assert any(m.startswith("smoke:") for m in markers)` (proves the marker is a real pytest marker entry)
- BAD: `assert "smoke" in makefile_text` (passes even if there's only a comment mentioning smoke)
- GOOD: `assert re.search(r"^smoke:\s", text, re.MULTILINE)` (proves a real Makefile target exists)
- BAD: `assert "contents" in perms` (doesn't prove the value or that no other permissions are granted)
- GOOD: `assert perms == {"contents": "read"}` (proves exact minimal-permission contract)

## Project Conventions

- File location: `tests/unit/test_make_targets.py` (extend in place).
- Use stdlib `tomllib` and `pyyaml`.
- Filesystem-only tests (the subprocess one is `--collect-only` so no DB).

## TDD Requirement

For each new assertion, strip the corresponding string from the live file and confirm the test fails clearly. Restore.

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
  "work_item": "F-00073",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["tests/unit/test_make_targets.py"],
  "preflight": {"format": "ok", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
