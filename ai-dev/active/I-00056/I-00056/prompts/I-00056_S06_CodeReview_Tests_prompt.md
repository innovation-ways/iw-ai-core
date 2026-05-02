# I-00056_S06_CodeReview_Tests_prompt

**Work Item**: I-00056 -- Code page lands on a wall of prose — components hidden, hard to scan
**Step Being Reviewed**: S05 (Tests)
**Review Step**: S06

---

## ⛔ Docker is off-limits

Read-only `docker ps/inspect/logs` only. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Do not run alembic upgrade/downgrade/stamp. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `uv run iw item-status I-00056 --json`
- `ai-dev/active/I-00056/I-00056_Issue_Design.md`
- `ai-dev/active/I-00056/reports/I-00056_S05_Tests_report.md`
- All test files added by S05
- The implementation files those tests cover

## Output Files

- `ai-dev/active/I-00056/reports/I-00056_S06_CodeReview_report.md`

## Pre-Review Gate

```bash
make lint
make format
```

NEW violations on changed test files → CRITICAL.

## Review Checklist

### 1. Falsifiability

For each test, ask: would it FAIL on pre-S01/S03 code?

- The wrap-helper tests must distinguish "Purpose has open" from "all H2s have open" and from "no H2s have open". A test that only checks `"<details>" in html` is not enough.
- The chips endpoint test must assert specific URLs (`/code/modules/orch-daemon`, `/code/modules/dashboard`), not just that a link exists.
- The slot-before-prose test must compare INDICES, not just check both substrings exist.
- The mapgen prompt test must assert BOTH the new string is present AND the old string is absent. Either alone is insufficient.

### 2. Real-DB integration discipline

- Dashboard tests use the project's testcontainer pattern (`tests/dashboard/conftest.py`).
- No DB mocks.
- FTS triggers run after `create_all()`.

### 3. Coverage of all four arms

- (a) wrap helper — present, with at least 5 cases (purpose-open, subsequent-closed, pre-h1-content-preserved, no-h2-passthrough, idempotent).
- (b) chips endpoint — returns links per module.
- (c) page-level slot order — chips slot before prose.
- (d) mapgen prompt — 1–3 sentences locked in.

### 4. Test isolation

- Tests don't share DB state.
- No global module mutations (no `importlib.reload(orch.config)`).
- No reliance on local `.env` values — use `monkeypatch.delenv` if needed.

### 5. Convention conformance

Read `tests/CLAUDE.md`. Verify:

- Tests live under `tests/unit/`, `tests/dashboard/` — NOT in `tests/integration/` unless they spin a testcontainer.
- `psycopg2://` URLs are replaced with `psycopg://`.
- No live-DB connections (port 5433).

## Test Verification

```bash
make test-unit
make test-integration   # if green on main
```

## Severity Levels

| CRITICAL | Test asserts only shape; mocks the DB; non-falsifiable | Must fix |
| HIGH | Coverage gap on a fix arm | Must fix |
| MEDIUM (fixable) | Convention drift | Should fix |
| MEDIUM (suggestion) | Optional improvement | Author decides |
| LOW | Nitpick | Informational |

## Review Result Contract

```json
{
  "step": "S06",
  "agent": "CodeReview",
  "work_item": "I-00056",
  "step_reviewed": "S05",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
