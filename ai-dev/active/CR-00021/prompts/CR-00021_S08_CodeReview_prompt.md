# CR-00021_S08_CodeReview_prompt

**Work Item**: CR-00021 -- Rebase alembic down_revision at merge time
**Step Being Reviewed**: S07 (tests-impl)
**Review Step**: S08

---

## ⛔ Docker is off-limits

Testcontainer fixtures only. Read-only docker introspection fine. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

Do NOT run `alembic upgrade/downgrade/stamp` against the live DB. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- `ai-dev/active/CR-00021/CR-00021_CR_Design.md` — Design (AC1–AC7 drive the coverage map)
- `ai-dev/active/CR-00021/reports/CR-00021_S07_Tests_report.md` — S07 test implementation report
- `tests/unit/daemon/test_migration_rebase.py`, `tests/unit/daemon/test_migration_pipeline.py`, `tests/unit/daemon/test_safe_migrate.py`, `tests/unit/daemon/test_merge_queue.py`
- `tests/integration/test_parallel_migrations.py`, `tests/integration/test_migration_rebase_conflict.py`
- `tests/CLAUDE.md` — testing conventions

## Output Files

- `ai-dev/active/CR-00021/reports/CR-00021_S08_CodeReview_report.md` — review report

## Context

Review S07's test suite. The central question: does each Acceptance Criterion (AC1-AC7) from the design have at least one test that fails without the CR-00021 code, and does the test's assertions prove the AC's stated outcome — not just a proxy?

## Review Checklist

### 1. AC coverage map — explicit in the review report

For each of AC1–AC7, list:
- Test name(s) that cover it.
- Whether the test asserts the AC's exact outcome (file content, DB row contents, enum status value, linear alembic chain).
- Whether a proxy is used where a real assertion should be.

| AC | Test | Proxy or real? |
|----|------|----------------|
| AC1 | `test_rewrite_single_migration_stale_down_revision` | real — asserts file content, git log, Rewrite list |
| AC2 | `test_no_op_when_down_revision_matches_main_head` | ... |
| AC3 | `test_multiple_migrations_preserve_internal_chain` | ... |
| AC4 | `test_rebase_conflict_returns_migration_rebase_failed` | ... |
| AC5 | `test_dry_run_uses_worktree_migrations_*` | ... |
| AC6 | `test_parallel_migrations*` | ... |
| AC7 | `test_migration_rebase_conflict*` | ... |

### 2. No DB mocking in integration

- `tests/integration/test_parallel_migrations.py` and `tests/integration/test_migration_rebase_conflict.py` use `pg_engine` fixture?
- No `MagicMock(Session)` or `create_engine("sqlite:///:memory:")` in integration tests?
- Unit tests may mock subprocess / DB, integration must not.

### 3. Testcontainer compliance

- URL replacement `psycopg2://` → `psycopg://` applied?
- `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` run after `create_all()` where required? (CR-00021 does not touch FTS tables, but any testcontainer that builds the full schema needs this.)
- No `importlib.reload(orch.config)`; uses `monkeypatch.delenv` instead?

### 4. Fixture isolation

- Each test gets a fresh schema OR a rolled-back transaction (match project pattern)?
- Scratch git repos created with `tmp_path` (auto-cleanup), not a shared directory?
- Tests don't leak state — running in any order produces the same result?

### 5. Assertion strength

- `test_rewrite_single_migration_stale_down_revision`: asserts the file's `down_revision` line is **exactly** `"revB"` (not just "contains"); asserts a git commit was added (HEAD SHA changed); asserts the commit message starts with `"chore(migration-rebase)"`.
- `test_multiple_migrations_preserve_internal_chain`: asserts revB2's file is **unchanged** bytewise after rebase.
- `test_parallel_migrations` (AC6): asserts **linear** alembic chain (not just "some chain"); asserts both columns exist in the live testcontainer schema; asserts both batch items end with `status='merged'`.
- `test_migration_rebase_conflict` (AC7): asserts the dry-run failure reason references the duplicate-column DB error; asserts main's git HEAD is byte-equal to batch-A's merge commit SHA; asserts `process_merge_queue` accepts another batch after the failure.

### 6. Coverage of failure paths

- `test_rebase_conflict_returns_migration_rebase_failed`: asserts worktree HEAD is restored (`git rebase --abort` evidence, not just `result.success=False`).
- `test_fetch_failure`: asserts the specific error path (remote unreachable / missing), not a generic failure.

### 7. Unit vs integration split

- Tests requiring a DB live in `tests/integration/` OR are marked `@pytest.mark.integration` per project convention?
- True unit tests (subprocess mocked / fixture repos only) live in `tests/unit/daemon/`?
- Any tests doing BOTH DB + real git subprocess → clearly labeled and justified?

### 8. Regression tests

- Existing callers of `run_pre_merge_dry_run(batch_id)` (no worktree_path) still covered by backward-compat tests?
- `_write_migration_log` callers with `phase='dry_run'` / `'apply'` / `'rollback'` still work with `old_revision=None`?

### 9. Test naming

- Names describe the scenario and the expected outcome?
- No `test_1`, `test_basic`, `test_it_works` — must be specific.

### 10. Deterministic content

- Migration revision IDs in test fixtures are hard-coded (`"rev1"`, `"revA"`, `"revB"`) not autogenerated hashes — so assertions remain stable?
- Timestamps come from frozen time or are compared with tolerance, not exact match (unless the test clock is controlled)?

## Test Verification (NON-NEGOTIABLE)

1. Run `make test-unit` AND `make test-integration` yourself — both must pass
2. Run `make lint` / `make format` / `make typecheck` — must pass
3. Report accurately with separate unit + integration counts

## Severity Levels

| Severity | Meaning |
|----------|---------|
| **CRITICAL** | An AC has zero real coverage (only proxies), DB mocking in integration tests, tests that leak state |
| **HIGH** | Assertions too weak (existence without content check), missing testcontainer URL rewrite, failure paths not tested |
| **MEDIUM (fixable)** | Helper duplication across integration files, weak test names, missing regression check on backward-compat call sites |
| **MEDIUM (suggestion)** | Could extract a fixture, could parametrise |
| **LOW** | Formatting, docstring polish |

## Review Result Contract

```json
{
  "step": "S08",
  "agent": "code-review-impl",
  "work_item": "CR-00021",
  "step_reviewed": "S07",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "ac_coverage|db_mocking|testcontainer|isolation|assertion_strength|failure_paths|regression|naming",
      "file": "tests/...",
      "line": 42,
      "description": "",
      "suggestion": ""
    }
  ],
  "ac_coverage_map": {
    "AC1": "test_rewrite_single_migration_stale_down_revision",
    "AC2": "...",
    "AC3": "...",
    "AC4": "...",
    "AC5": "...",
    "AC6": "...",
    "AC7": "..."
  },
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "unit X passed; integration Y passed; 0 failed",
  "notes": ""
}
```
