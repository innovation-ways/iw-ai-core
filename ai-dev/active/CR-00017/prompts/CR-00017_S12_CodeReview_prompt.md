# CR-00017_S12_CodeReview_prompt

**Work Item**: CR-00017 — Daemon-only migration application
**Step Being Reviewed**: S11 (tests-impl)
**Review Step**: S12

---

## Input Files

- `ai-dev/active/CR-00017/CR-00017_CR_Design.md`
- `ai-dev/active/CR-00017/reports/CR-00017_S11_Tests_report.md`
- All files in S11's `files_changed`
- `tests/CLAUDE.md`

## Output Files

- `ai-dev/active/CR-00017/reports/CR-00017_S12_CodeReview_report.md`

## Review Checklist

### 1. No live-DB leaks
- Zero references to `5433` or `localhost:5433` or `IW_CORE_DB_PORT` in test bodies.
- Every test uses testcontainer fixtures.
- psycopg v3 URL replacement present everywhere.

### 2. Coverage matrix (CRITICAL)
Confirm AC1–AC10 are all exercised:
- AC1: agent-context guard — unit test (guard permutations) + integration test (CLI exit 2).
- AC2: dry-run rejects broken migration.
- AC3: happy path through apply.
- AC4: apply fails → rollback succeeds; apply fails → rollback fails → frozen.
- AC5: frozen blocks merges; operator unfreeze resumes; agent cannot unfreeze.
- AC6: multi-head rejected.
- AC7: CLI exit codes match canonical values.
- AC8: coverage test has R2 marker.
- AC9: (manual verification via smoke — not automated).
- AC10: existing `make check` green (no regression).

Any AC without a corresponding test → HIGH severity.

### 3. Guard permutation test
- `IW_CORE_AGENT_CONTEXT` values tested: `"true"` triggers; `"TRUE"`, `"1"`, `""`, unset, `"false"` do NOT trigger.
- This semantic is documented in the test file and/or in a module-level comment in `safe_migrate.py`.

### 4. Frozen-queue tests
- Freeze/unfreeze round-trip.
- Agent-context unfreeze refusal.
- Ack reason persisted in daemon_events.
- Frozen state actually blocks merges (not just sets a flag).

### 5. Coverage test extension
- R2 marker check added.
- Original R1 check still present and passing.
- Parametrization still shows per-file failure ids.

### 6. Mutation verification
- S11 report documents a mutation test: remove R2 marker from one file → coverage test fails with that file's name.
- File was restored.

### 7. Subprocess env test
- `test_agent_env_propagates_to_subprocess` actually uses a subprocess stub (not just asserts env mutation in the current process).
- Env cleanup after test.

### 8. Test speed
- Unit tests fast (<5s total).
- Integration tests reasonable (<60s each; Ryuk teardown not starving).

### 9. No destructive live-DB operations
- No test stops/starts/removes the production `postgres` container.
- No test writes to `/opt/postgres/data`.

## Severity Grading

CRITICAL / HIGH / MEDIUM / LOW. Fix in place.

## Subagent Result Contract

Standard code-review JSON.

## Lifecycle commands

```bash
uv run iw step-start CR-00017 --step S12
uv run iw step-done CR-00017 --step S12 --report ai-dev/active/CR-00017/reports/CR-00017_S12_CodeReview_report.md
```
