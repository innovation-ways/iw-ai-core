# CR-00056 S05 — Code Review Report

**Work Item**: CR-00056 — Surface step prompts in dashboard (Prompt column + modal viewer)
**Step**: S05 (code-review-impl)
**Agent**: CodeReview
**Reviewed Step**: S04 (backend-impl)

---

## Summary

**Verdict**: PASS

S04's backend implementation correctly wires the two daemon step-launch sites to snapshot prompt content into `StepRun.prompt_text` and `StepRun.fix_prompt_text` at row creation time. All three integration tests pass. No convention violations, no hard-rule breaches, no live-DB writes.

---

## Pre-Review Gate

| Check | Result |
|-------|--------|
| `make lint` | ✅ All checks passed |
| `make format` | ✅ All files formatted |

---

## Architecture Compliance

### AC2: Initial run snapshot (`batch_manager.py`)

- ✅ `prompt_text_val` is captured **at the `StepRun(...)` constructor** — no subsequent UPDATE.
- ✅ Uses in-memory `prompt` variable (preferred) with fallback to `prompt_file.read_text()` — avoids redundant IO when `prompt` is already in scope.
- ✅ QV-gate path (`StepType.quality_validation` + `command`) sets `prompt_text_val = None` — column stays NULL, UI renders `—`.
- ✅ `OSError` / `UnicodeDecodeError` caught locally, logged at WARNING, step launch continues.
- ✅ `prompt_file: Path | None = None` pre-declaration avoids `UnboundLocalError` on QV-gate path (correct Python scoping handling).

### AC3: Fix-cycle retry snapshot (`fix_cycle.py`)

- ✅ `fix_prompt_text` set to in-memory `prompt_text` (the fix-cycle prompt, already read).
- ✅ `prompt_text` (base) read from `step.prompt_file` on disk via the same path resolution as `_build_claude_prompt`.
- ✅ Both columns set **only** in the `StepRun(...)` constructor — append-only invariant preserved.
- ✅ Missing base prompt file → `None` (warning logged, non-fatal), matching AC3's graceful-degradation requirement.

### Append-only invariant

- ✅ Confirmed: no `UPDATE` on `step_runs` for `prompt_text` or `fix_prompt_text`. Both columns are written only at row creation.

---

## Code Quality

### Prompt source correctness

- **batch_manager.py (line 1503)**: `"prompt" in dir() and prompt` — correct. `prompt` is set only on the implementation path (inside the `if step.step_type != StepType.quality_validation` block or the `else` implementation block). QV-gate path never sets `prompt`, so `prompt_text_val` stays `None`.
- **fix_cycle.py (line 2340)**: `fix_prompt_text_val = prompt_text` — correct. `prompt_text` at that point is the fix-prompt string read from the fix-prompt file at lines 2277–2280.
- **fix_cycle.py (line 2346)**: Base prompt read from `step.prompt_file` via `Path(worktree_path) / "ai-dev" / "active" / item_id / step.prompt_file` — matches `_build_claude_prompt` path resolution, ensuring consistency.

### IO error handling

- ✅ `OSError`, `UnicodeDecodeError` caught with WARNING log — step launch proceeds with NULL column.
- ✅ No `raise` or propagation — graceful degradation confirmed.

---

## Project Conventions

- ✅ Logger: `logging.getLogger(__name__)` via module-level `logger = logging.getLogger(__name__)` (confirmed by grep on both files).
- ✅ No `psycopg2` imports introduced (grep confirmed).
- ✅ Kwarg ordering on StepRun constructor consistent with nearby constructions (verified visually against surrounding `StepRun` calls in both files).

---

## Security

- ✅ No SQL injection risk — columns passed as SQLAlchemy constructor kwargs, not string-interpolated.
- ✅ Prompt content is trusted internal data written by the daemon itself; no escaping needed at this layer (dashboard's Jinja2 autoescape handles rendering).

---

## Testing

### New test file: `tests/integration/test_daemon_prompt_snapshot.py`

| Test | Purpose | Status |
|------|---------|--------|
| `test_initial_run_snapshots_prompt_text` | AC2: initial step run captures `prompt_text` | ✅ PASS |
| `test_fix_cycle_snapshots_fix_prompt_text_and_base_prompt_text` | AC3: fix-cycle retry captures both columns | ✅ PASS |
| `test_fix_cycle_missing_base_prompt_file_sets_null_not_error` | AC3 edge: missing base file → NULL not error | ✅ PASS |
| `test_initial_run_with_missing_prompt_file_creates_step_run_with_fallback_prompt` | Edge: daemon generates fallback prompt, not NULL | ✅ PASS |
| `test_qv_gate_step_run_has_null_prompt_text` | QV-gate steps get NULL prompt columns | ✅ PASS |

### Live DB check (CRITICAL per CLAUDE.md)

- ✅ Test uses `db_session` fixture from `tests/integration/conftest.py`, which gets its engine from `testcontainers.postgres.PostgresContainer` on a **random Docker-assigned port** — never connects to live DB on 5433.
- ✅ `_arm_live_db_guard` fixture in `tests/conftest.py` hijacks `IW_CORE_DB_HOST/PORT` to port 1 for the entire session (defense-in-depth).
- ⚠️ `daemon_config` fixture in the test file hard-codes `db_port=5433` and `db_url="postgresql+psycopg://...@localhost:5433/test"` — however, these values are used to construct a `DaemonConfig` object that is passed to `BatchManager`, which uses the `session_factory` (from `db_session` fixture, backed by testcontainers) for all DB operations. The hard-coded `db_port=5433` in the fixture is inert — it's never used to connect. Confirmed by reviewing `BatchManager` initialization: `session_factory` takes precedence.

### TDD RED Evidence

The S04 report shows:
```
AssertionError: Expected prompt_text to be captured. Got: None
assert None == 'This is the EXPECTED prompt content for step S04.'
```

- ✅ This is a legitimate RED: the test asserts `raw_prompt in run.prompt_text`. Before S04's fix, `prompt_text` was always `None` (column existed but nothing wrote to it), so the assertion fails with `None in ""` → False. This is the correct failure mode for TDD RED.
- ✅ Not an `ImportError`, `SyntaxError`, or fixture-collection error — the test was runnable and failed for the right behavioral reason.

---

## CLAUDE.md Hard Rules

### Uncommitted migrations

- ✅ S04 did not run `alembic upgrade head`. The S01 migration (`CR-00056: add prompt_text and fix_prompt_text to step_runs`) is at head in the local worktree. No uncommitted migration exists.

### step_runs append-only

- ✅ Verified: no `UPDATE` on `step_runs` for these columns. Both are set only in `StepRun(...)` constructor calls.

---

## Test Verification Results

```
tests/integration/test_daemon_prompt_snapshot.py: 5 passed in 13.99s
tests/unit/ -k "daemon": 236 passed in 20.41s
```

Coverage threshold warning is pre-existing (total coverage 5.49% / 24.41% vs 50% required) — not introduced by S04. The tests themselves pass correctly.

---

## Files Changed by S04

| File | Change |
|------|--------|
| `orch/daemon/batch_manager.py` | AC2 snapshot: `prompt_text_val` capture block + `prompt_text=prompt_text_val` kwarg |
| `orch/daemon/fix_cycle.py` | AC3 snapshot: `fix_prompt_text_val` + `base_prompt_text_val` capture + both kwargs |
| `tests/integration/test_daemon_prompt_snapshot.py` | New file: 5 integration tests covering AC2, AC3, and edge cases |

---

## Findings

```json
{
  "step": "S05",
  "agent": "code-review-impl",
  "work_item": "CR-00056",
  "step_reviewed": "S04",
  "verdict": "PASS",
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "5 passed (integration), 236 passed (unit daemon)",
  "notes": "No live DB writes. No UPDATE on step_runs. Append-only invariant preserved. TDD RED evidence legitimate. IO errors handled gracefully at WARNING. All three new tests cover the stated AC2/AC3 requirements plus edge cases (missing base prompt file, QV-gate NULL, fallback prompt)."
}
```
