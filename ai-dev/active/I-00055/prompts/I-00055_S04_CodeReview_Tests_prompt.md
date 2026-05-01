# I-00055_S04_CodeReview_Tests_prompt

**Work Item**: I-00055 -- Architecture Diagram renders twice on Code page; inline copy unreadable in dark mode
**Step Being Reviewed**: S03 (Tests)
**Review Step**: S04

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state.
Read-only introspection (`docker ps`, `docker inspect`, `docker logs`) is allowed.
Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Do not run `alembic upgrade/downgrade/stamp` against the live DB. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00055 --json`.
- `ai-dev/active/I-00055/I-00055_Issue_Design.md`
- `ai-dev/active/I-00055/reports/I-00055_S03_Tests_report.md`
- All test files added by S03 (typically `tests/unit/rag/test_mapgen.py`, `tests/dashboard/test_code_page_arch_diagram.py`)
- The implementation files those tests cover: `orch/rag/mapgen.py`, `dashboard/routers/code_ui.py`

## Output Files

- `ai-dev/active/I-00055/reports/I-00055_S04_CodeReview_report.md`

## Context

Review the test work added in S03. The tests must (a) prove the bug is fixed (would FAIL pre-S01), (b) prevent regression on the mapgen content invariant, and (c) prevent regression on the strip helper.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

NEW violations on the changed test files → CRITICAL findings (`category: conventions`).

## Review Checklist

### 1. Falsifiability (the I-003 lesson)

For each test, ask: "would this fail on pre-S01 code?" If a test would still pass with the bug present, it's a **shape check** — flag CRITICAL.

Specifically:

- The dashboard test MUST assert **exactly one** mermaid container, not "at least one" / "at most two" / "non-empty". The exact assertion to look for: `assert inline + bottom == 1`.
- The mapgen test MUST assert all three forbidden substrings absent: `## Architecture Diagram`, `<!-- purpose:`, ` ```mermaid `. Two-out-of-three is not enough.
- The idempotency test for the strip helper MUST compare equality of two consecutive applications, not just "no error".
- The non-trailing-H2 negative test (if added) MUST assert *equality with input*, proving the helper does not strip a non-trailing same-named H2.

### 2. Real-DB integration discipline

The dashboard test MUST use the project's standard testcontainer pattern from `tests/dashboard/conftest.py`. No DB mocks. FTS trigger setup respected. URL rewrite from psycopg2 to psycopg if applicable.

### 3. Test isolation

- Each test seeds its own project (no shared global state).
- No reliance on a particular project_id existing on disk.
- No live network, no Ollama, no LLM calls (the mapgen unit test is a pure string contract).

### 4. Coverage of both fix arms

- Confirm there is at least one test asserting the **mapgen writer no longer emits** the diagram.
- Confirm there is at least one test asserting the **render-time strip helper** removes the legacy block.
- Confirm the dashboard end-to-end test exercises BOTH together (legacy content + helper → exactly one diagram).

### 5. Convention conformance

Read `tests/CLAUDE.md`. Verify:

- Tests live under the correct subtree (`tests/unit/`, `tests/dashboard/`).
- Naming matches the project's pattern (`test_*.py`, `def test_*(...)`).
- Imports follow project style.

## Test Verification (NON-NEGOTIABLE)

```bash
make test-unit
make test-integration   # if previously green on main
```

Both must pass.

## Severity Levels

| Severity | Meaning | Action |
|----------|---------|--------|
| CRITICAL | Test is non-falsifiable, mocks the DB, or asserts only shape | Must fix |
| HIGH | Coverage gap on a fix arm; flaky test | Must fix |
| MEDIUM (fixable) | Convention violation, naming drift | Should fix |
| MEDIUM (suggestion) | Optional improvement | Author decides |
| LOW | Nitpick | Informational |

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "I-00055",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
