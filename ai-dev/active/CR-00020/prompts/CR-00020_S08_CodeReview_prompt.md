# CR-00020_S08_CodeReview_prompt

**Work Item**: CR-00020 -- Store work item evidences as BLOBs in the database
**Step Being Reviewed**: S07 (tests-impl)
**Review Step**: S08

---

## ⛔ Docker is off-limits
See `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies
See `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- `ai-dev/active/CR-00020/CR-00020_CR_Design.md` — ACs
- `ai-dev/active/CR-00020/reports/CR-00020_S07_Tests_report.md`
- All test files listed in S07's `files_changed`
- `tests/CLAUDE.md` — test policy

## Output Files

- `ai-dev/active/CR-00020/reports/CR-00020_S08_CodeReview_report.md`

## Review Checklist

### 1. AC coverage map

For each AC1-AC8, find the test(s) that cover it. Missing coverage for any AC = HIGH.

Produce an explicit map in the review report, e.g.:

| AC | Test(s) |
|----|---------|
| AC1 | `test_approve_ingests_pre_evidences` |
| AC2 | `test_step_done_ingests_post_evidences` |
| … | … |

### 2. Byte-identical content assertions

Every test that ingests a known file must verify the DB round-trips the exact bytes. `assert row.content == expected_bytes` or `assert hashlib.sha256(row.content).hexdigest() == expected_hash`. Just checking `size_bytes` is insufficient — it's caught a bug in I003 before (shape-only assertions).

### 3. No DB mocking (critical rule)

`grep -rn "mock\|Mock\|monkeypatch" tests/integration/test_evidences_cli.py tests/dashboard/test_evidences_db_source.py`. Any DB-session mocking is a CRITICAL finding per `tests/CLAUDE.md`.

### 4. No live-DB connection

No test connects to `localhost:5433` or reads `.env`'s production DB vars. Testcontainers only (via fixtures).

### 5. `importlib.reload(orch.config)` not used

`tests/CLAUDE.md` rule #2. `grep -n "importlib.reload" tests/…` — any hit is CRITICAL.

### 6. Oversize test semantics

The AC4 test MUST assert zero rows in the table AFTER the oversize ingest, and MUST assert the item status did NOT advance. If either assertion is missing, MEDIUM_FIXABLE.

### 7. No-cascade test is explicit

AC6 test deletes the `work_items` row via raw SQL (not ORM cascade-aware code) and re-queries. If the test uses `session.delete(item)` and relies on SQLAlchemy relationship config, the assertion may pass falsely — flag HIGH.

### 8. FS-fallback scope

AC7 test sets `bi.worktree_info['path']`. If the test runs with no BatchItem or no worktree path, it's not actually testing the fallback gate. Verify the fixture wiring.

Also verify the "pre has no fallback" test is present.

### 9. Test determinism

- Filenames are deterministic (no `uuid4` in the test's own file names unless the test also asserts by uuid)
- Content generation is deterministic (`b'x' * N` or a fixed byte string, not `os.urandom`)
- No sleeps or timing-dependent assertions

### 10. Cleanup / isolation

- Tests use `tmp_path` for FS scaffolding
- Each test creates its own work_item row; no shared mutable fixture state
- The FTS DDL + `create_all()` sequence is respected via the `pg_engine` fixture (no new fixtures that skip FTS)

### 11. Lint / format / typecheck

`make lint` / `make format` / `make typecheck` pass against the new test files.

## Severity Items to flag

- CRITICAL: DB mocking in integration/dashboard tier; live-DB connection; missing AC coverage
- HIGH: AC6 relies on ORM cascade behavior instead of raw DELETE; AC7 missing worktree wiring
- MEDIUM_FIXABLE: shape-only assertions (size only, no content check); non-deterministic content

## Review Result Contract

```json
{
  "step": "S08",
  "agent": "CodeReview",
  "work_item": "CR-00020",
  "step_reviewed": "S07",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "",
  "notes": "AC coverage map: <inline above>"
}
```
