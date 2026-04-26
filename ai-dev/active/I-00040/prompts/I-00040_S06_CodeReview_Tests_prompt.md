# I-00040 S06 — Code review of S05 (tests)

**Work Item**: I-00040
**Step Being Reviewed**: S05 (tests-impl — guard reproduction + regression tests)
**Review Step**: S06
**Agent**: code-review-impl

## ⛔ Docker / Migrations off-limits

Standard rules.

## Input Files

- `ai-dev/active/I-00040/I-00040_Issue_Design.md`
- `ai-dev/active/I-00040/reports/I-00040_S05_Tests_report.md`
- All test files added/modified by S05
- `tests/CLAUDE.md`

## Output Files

- `ai-dev/active/I-00040/reports/I-00040_S06_CodeReview_Tests_report.md`

## Review Checklist

### 1. Reproduction test exists and is correct — CRITICAL

- [ ] `tests/integration/test_alembic_guard_integration.py::test_guard_fails_when_behind_one_revision` exists.
- [ ] It uses a real testcontainer (NOT a mock).
- [ ] It applies `alembic upgrade head`, captures `head_rev`, downgrades by one, captures `current_rev`.
- [ ] It asserts `pytest.raises(DBBehindHeadError)`.
- [ ] The match argument or post-raise inspection asserts that BOTH `head_rev` and `current_rev` appear in the message AND `make db-migrate` appears in the message.

### 2. Semantic correctness — CRITICAL (I003 LESSON)

- [ ] NO assertion is purely shape-based (`"key" in body`, `len(x) > 0`, `x is not None` without a follow-up specific-value check).
- [ ] Banner test asserts the EXACT string `Orch DB schema is behind head` (not "banner exists").
- [ ] Banner test asserts the EXACT string `make db-migrate`.
- [ ] Banner test asserts a SPECIFIC revision identifier appears.
- [ ] `_launch_item` test asserts `BatchItemStatus.setup_failed` (the enum value), not "status changed".
- [ ] `DaemonEvent` test asserts `event_metadata["phase"] == "alembic_guard"` (specific string), not "metadata exists".

### 3. Test isolation

- [ ] No shared state across tests (each test gets a fresh testcontainer or transaction).
- [ ] No `importlib.reload(orch.config)` (use `monkeypatch.delenv()` per project rule).
- [ ] No connection to the live DB on port 5433 — verify with grep.
- [ ] No `time.sleep` polling without a timeout.

### 4. Coverage of the three guard points

- [ ] Daemon startup mismatch: subprocess (or in-process) test asserts non-zero exit AND `CRITICAL: orch DB schema mismatch — ` in stderr.
- [ ] Dashboard create_app mismatch: `TestClient` test asserts banner markup AND 503 from a state-mutating endpoint.
- [ ] `_launch_item` mismatch: integration test asserts `setup_failed` + notes + DaemonEvent + no worktree directory created.

### 5. Operator override coverage

- [ ] `IW_CORE_SKIP_ALEMBIC_GUARD=true` in operator context: `assert_db_at_head` returns silently AND a WARNING log line is captured (e.g. via `caplog`).
- [ ] Same env var in `IW_CORE_AGENT_CONTEXT=true`: STILL raises.

### 6. Convention conformance

- [ ] Test files live in the right directories (unit / integration / dashboard).
- [ ] Test names start with `test_` and read like sentences.
- [ ] No `from __future__` missing where needed.
- [ ] No emoji in test docstrings or output.

### 7. Run results

- [ ] S05's report includes the output of running each test file. All pass.
- [ ] No tests are skipped, xfailed, or marked `@pytest.mark.skip` without a clear justification documented in the report.

### 8. False-positive / false-negative defenses

- [ ] At least one test deliberately asserts the GUARD DOES NOT FIRE when the DB is at head (`test_guard_passes_at_head`).
- [ ] At least one test deliberately asserts the BANNER IS ABSENT when the DB is at head.

## Output Report

Findings list with severity (CRITICAL / HIGH / MEDIUM / LOW / INFO), file:line, and a one-line verdict per item. End with overall verdict.

## Lifecycle Commands

```bash
uv run iw step-start I-00040 --step S06
mkdir -p ai-dev/active/I-00040/reports
uv run iw step-done I-00040 --step S06 --report ai-dev/active/I-00040/reports/I-00040_S06_CodeReview_Tests_report.md
```
