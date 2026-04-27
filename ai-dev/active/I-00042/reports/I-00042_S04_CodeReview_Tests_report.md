# I-00042 S04 Code Review — Tests

**Reviewed Step**: S03 (Tests)
**Reviewer**: CodeReview agent (S04)
**Date**: 2026-04-27
**File Under Review**: `tests/integration/test_batch_item_status_enum_drift.py`

---

## Verdict: PASS

Zero CRITICAL, HIGH, or MEDIUM (fixable) findings. The test is correctly
structured, semantically sound, falsifiable, and follows all project conventions.

---

## Findings Table

| # | Severity | File | Line(s) | Category | Description |
|---|----------|------|---------|----------|-------------|
| — | — | — | — | — | No findings |

No issues were found. The table is intentionally empty.

---

## Checklist Review

### 1. Semantic Correctness

PASS. The test asserts specific values by name:

- Line 101: `assert "migration_invalid" in pg_labels`
- Line 102: `assert "migration_rolled_back" in pg_labels`
- Line 107-108: subset check `{e.value for e in BatchItemStatus} - pg_labels` with a
  named-value failure message.

These are the exact checks required. The test does not rely on counts or structural
shape alone.

### 2. Drift Direction

PASS. The drift check is one-directional: Python ⊆ PG. Strict equality is not asserted.
The docstring on the test function explicitly documents that PG may have extra orphan
labels (e.g. `awaiting_review`, `discarded` from CR-00019) without causing a failure.
This matches the requirement.

### 3. Fixture Binding

PASS. The test uses a private `migrated_engine` fixture (module-scoped) that is
backed by its own private `pg_container` fixture, also module-scoped. Neither fixture
uses or shadows the session-scoped `db_engine` from `tests/integration/conftest.py`.
The module docstring explains why the shared `db_engine` is intentionally not used.

- `get_db_url()` is not called.
- `orch.config` is not imported.
- Port 5433 is not referenced anywhere.
- DB is not mocked.

The `psycopg2://` → `psycopg://` URL replacement is present on line 58-59 (matches
CLAUDE.md rule and `tests/CLAUDE.md` rule 5).

The `IW_CORE_DB_*` env vars are scoped inside `pytest.MonkeyPatch.context()` (lines
62-73), which tears them down at module scope — credentials do not leak to other
modules. This matches the pattern from `tests/integration/test_iw_core_instance_migration.py`.

### 4. Falsifiability

PASS. The RED proof in the S03 report shows the test failing with:

```
AssertionError: assert 'migration_invalid' in {'completed', 'executing', 'failed',
'merged', 'merging', 'migration_rebase_failed', ...}
```

This confirms the test is structurally incapable of passing without the I-00042
migration being on disk and applied by `alembic upgrade head`. The assertion message
names the missing value, which is informative for future maintenance.

Independent verification: I confirmed this by inspecting the Alembic migration chain.
The `migrated_engine` fixture calls `command.upgrade(cfg, "head")`, which will traverse
all migrations from the empty DB. If `bd4ed52cad71` is absent from the versions
directory, the two labels are never added and line 101 fails. The test is truly
falsifiable.

### 5. Style and Conventions

PASS.

- Module docstring present at file level, explaining the WHY of the private fixture
  (lines 1-17).
- Imports at top of file (lines 19-30), with `TYPE_CHECKING` guard for the `Engine`
  annotation.
- Test function name `test_pg_batch_item_status_enum_includes_i_00042_labels` follows
  `test_<scenario>_<outcome>` convention.
- Raw SQL uses `text("...")` (lines 91-97), not f-strings or string concatenation.
- No class-based test grouping (file correctly uses plain functions).
- `from __future__ import annotations` present (line 19).
- `BatchItemStatus` is used with a comprehension `{e.value for e in BatchItemStatus}`
  — correct, since `enum.Enum` has no `.values` attribute.

### 6. Scope

PASS. The file contains exactly one test function, scoped exclusively to
`batch_item_status` drift. No tests for other enums or unrelated functionality.

---

## Test Verification Results

| Check | Result |
|-------|--------|
| `uv run pytest tests/integration/test_batch_item_status_enum_drift.py -v` | 1 passed, 0 failed (4.39s) |
| `uv run ruff check tests/integration/test_batch_item_status_enum_drift.py` | All checks passed |
| `make test-unit` | 1759 passed, 2 skipped, 0 failed (12.81s) |

---

## Result Contract

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "I-00042",
  "step_reviewed": "S03",
  "verdict": "pass",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "1 integration test passed (alembic-built schema, private pg_container); 1759 unit passed, 0 failed; lint clean",
  "notes": "Test is structurally sound: private testcontainer + alembic upgrade head, semantic value assertions, one-directional subset drift check, env var scoping via MonkeyPatch.context(). RED->GREEN proof in S03 report is consistent with the test logic."
}
```
