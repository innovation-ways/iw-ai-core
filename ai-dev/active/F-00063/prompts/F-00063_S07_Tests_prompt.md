# F-00063_S07_Tests_prompt

**Work Item**: F-00063 -- Stale Process & Migration Detector
**Step**: S07
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute docker container/volume/network mutating commands. Read-only commands and testcontainers in pytest fixtures are allowed. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade|downgrade|stamp` against the live orch DB. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `ai-dev/active/F-00063/F-00063_Feature_Design.md`
- All previous step reports (S01–S06)

## Output Files

- `ai-dev/active/F-00063/reports/F-00063_S07_Tests_report.md`

## Context

S01–S06 each wrote tests for their own scope. Your job is to fill remaining gaps — particularly cross-module behavior and every Boundary Behavior row in the design doc that isn't already covered.

Read the design doc's Boundary Behavior table and Invariants list. Cross-reference with the test files added in S01–S06. Add tests for any uncovered row.

## Requirements

### 1. Coverage gap analysis

For each row in the Boundary Behavior table, find or write a test that exercises it:

- Project not in `projects.toml` → 404 from staleness GET.
- Empty staleness config → empty fragment body.
- Port detect, nothing bound → `not_running`, grey, no red dot contribution.
- Pidfile missing / stale → `not_running`.
- Process found but cwd in agent worktree (outside `repo_root`) → ignored.
- Up-to-date when commits exist but excluded by `ignore_paths`.
- `hot_reload = true` → `hot_reload_skipped`, no Restart button.
- Only stop/start configured → two buttons; restart_command absent → no Restart button.
- Neither set → informational only.
- Two restart POSTs in <5s → second is 429.
- Alembic config missing → migrations section omitted.
- Alembic DB unreachable → `unreachable` rendered with error.
- Alembic up-to-date → green.
- Alembic upgrade failure → 502.
- Malformed `projects.toml` mid-render → 500 logged, other dashboard pages unaffected.
- Docker container stopped → `not_running`.
- pgrep multiple matches → oldest selected, warning logged.
- Self-restart endpoint returns 202 quickly (≤200 ms).

### 2. Invariant tests

For each invariant in the design doc, add at least one test that would catch a regression of that invariant. Examples:

- Inv 1: assert no new tables in `Base.metadata.tables` after the feature.
- Inv 4: spawn 3 rapid restart POSTs, assert exactly one subprocess invocation.
- Inv 5: alembic upgrade endpoint test verifies that — when `db_url_env` is configured — the env passed to the subprocess contains exactly that value and not another DB; and when `db_url_env` is omitted (e.g. iw-ai-core dogfood) the subprocess env equals the parent env unchanged.
- Inv 6: monkeypatch `projects.toml` mid-test, second call sees the new contents.
- Inv 8: red-dot fragment test with `not_running`-only services produces no red dot.

### 3. Performance smoke

A single test that calls `compute_project_staleness("iw-ai-core")` against a temp git repo with ~50 commits and ~5 watched paths and asserts it completes in under 500 ms.

### 4. Documentation in tests

Each test name should clearly describe what it verifies. Group by file matching the production module (`tests/unit/staleness/test_*.py` etc).

## Project Conventions

- Use `pytest` style (functions, not classes) matching the rest of `tests/`.
- For git-related tests, use a `tmp_path` fixture and shell out via `subprocess.run` to set up the repo. See existing tests for examples (`tests/unit/` already has examples of this pattern).
- For `/proc` and `subprocess` tests, mock at the boundary (`subprocess.run`, `pathlib.Path.read_text`) — don't try to mock `/proc` directly.
- For dashboard-router tests, use the existing FastAPI TestClient pattern in `tests/dashboard/`.
- NEVER connect tests to live DB on port 5433 — use testcontainers only (see `tests/CLAUDE.md`).

## TDD Requirement

Tests-only step. RED is implicit (no implementation to add). GREEN means all tests pass against the existing implementation. If a test fails because of a real bug, file a blocker — do NOT fix the bug here.

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit`
2. `make test-integration`
3. `make lint`
4. `make typecheck`

## Subagent Result Contract

```json
{
  "step": "S07",
  "agent": "tests-impl",
  "work_item": "F-00063",
  "completion_status": "complete|partial|blocked",
  "files_changed": [],
  "tests_passed": true,
  "test_summary": "",
  "blockers": [],
  "notes": ""
}
```
