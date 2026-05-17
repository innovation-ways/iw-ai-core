# CR-00055 S02 Code Review Report

**Work Item**: CR-00055 — Re-enable `pytest-randomly` by default via per-test PostgreSQL template-clone
**Step**: S02 (code-review-impl)
**Date**: 2026-05-16
**Reviewer Agent**: code-review-impl
**Status**: COMPLETE

---

## Pre-Review Gate Results

| Gate | Command | Result |
|------|---------|--------|
| `make lint` | `ruff check . + check_templates.py` | PASS — zero violations |
| `make format-check` | `ruff format --check .` | PASS — 724 files already formatted |

---

## Files Changed (vs `main`)

All changed files match the design's "Impacted Paths" list exactly. No unexpected production code or migration files found.

| File | Status |
|------|--------|
| `pyproject.toml` | Modified — `pgtestdbpy>=0.0.1` added to dev deps; `-p no:randomly` removed from `addopts`; comment block rewritten |
| `uv.lock` | Updated — `pgtestdbpy` appears 5 times as expected |
| `tests/integration/conftest.py` | Modified — full fixture chain rewrite |
| `tests/dashboard/conftest.py` | Modified — `_pgtestdb_setup` added to re-exports |
| `tests/integration/test_oss_migration.py` | Modified — teardown added |
| `tests/integration/test_project_oss_job_migration.py` | Modified — teardown added |
| `tests/integration/test_db_identity_integration.py` | Modified — autouse fixture + quarantine added |
| `tests/integration/test_pending_migration_log_migration.py` | Modified — quarantine added |
| `tests/integration/db/test_i_00062_migration.py` | Modified — quarantine added |
| `tests/CLAUDE.md` | Modified — §7 flipped to default-on |
| `docs/IW_AI_Core_Testing_Strategy.md` | Modified — §3 + §9 flipped |
| `skills/iw-ai-core-testing/SKILL.md` | Modified — §2 flipped |
| `.claude/skills/iw-ai-core-testing/SKILL.md` | Modified — synced |
| `ai-dev/work/TESTS_ENHANCEMENT.md` | Modified — §5, item 1.4, §11 updated |

Note: `ai-dev/active/CR-00056/` files appear as deletions in `git diff --stat main` because the worktree was branched before those files were added to `main`. This is expected branch-divergence behavior, not scope creep.

---

## CRITICAL Check Results

### 1. WAL_LOG Override on `pgtestdbpy.QRY_DB_CLONE`

```
tests/integration/conftest.py:253
```

```python
pgtestdbpy.QRY_DB_CLONE = (
    'CREATE DATABASE "{db_name}" WITH TEMPLATE "{template}" OWNER "{user}"'
)
```

**PASS** — `STRATEGY=FILE_COPY` is absent from the override string. The override is set inside `_pgtestdb_setup` BEFORE `pgtestdbpy.templates(config, migrator)` is entered. PostgreSQL 15+ defaults to WAL_LOG strategy, so this drops the ~310 ms/clone `FILE_COPY` overhead to ~25 ms/clone.

The word `FILE_COPY` appears only in a comment at line 246 explaining why the override is necessary.

### 2. `_pgtestdb_setup` Re-exported from `tests/dashboard/conftest.py`

```
tests/dashboard/conftest.py:17
```

```python
from tests.integration.conftest import (  # noqa: F401
    _db_test_connection,
    _pgtestdb_setup,
    db_engine,
    db_session,
    db_session_factory,
    pg_container,
    test_project,
)
```

**PASS** — `_pgtestdb_setup` is present in the re-export block alongside all other required fixtures.

---

## AC1 Scope Discipline Check

| Check | Result |
|-------|--------|
| `grep 'no:randomly' pyproject.toml` → nothing in `addopts` | PASS — only in historical comment at line 154 |
| `--strict-markers` present in `addopts` | PASS — line 156 |
| `pgtestdbpy>=0.0.1` in `[dependency-groups] dev` | PASS — line 101 |
| `uv.lock` regenerated | PASS — 5 `pgtestdbpy` entries |
| No production code touched (`orch/`, `dashboard/`, `executor/`, `bin/`, `scripts/`) | PASS |
| No migrations | PASS |
| No Makefile / .github changes | PASS |

---

## Fixture Implementation Checks

### `_migrate_template` (non-fixture helper)

- Applies `OSS_ENUMS_SQL` + `BATCH_ITEM_STATUS_SQL` via SQLAlchemy before alembic: PASS
- Calls `_run_alembic_upgrade(cfg)`: PASS
- Calls `Base.metadata.create_all(template_engine)` after alembic: PASS
- Disposes engine in `finally`: PASS
- FTS triggers: The `work_items_fts_update` trigger is installed by the initial alembic migration (`a1b2c3d4e5f6_initial_schema.py`), which runs via `_run_alembic_upgrade`. The subsequent `Base.metadata.create_all` is a no-op (all tables already exist). FTS coverage satisfied through alembic migration path. PASS

### `_pgtestdb_setup` (session-scoped)

- `Config` built from container superuser URL: PASS
- `Migrator` uses `db_name="iwcore_template"`, `user="iwcore_test"`, `password="iwcore_test"`: PASS
- WAL_LOG `QRY_DB_CLONE` override set before `pgtestdbpy.templates()`: PASS
- Yields `(config, migrator)`: PASS

### `db_engine` (function-scoped — default, no explicit scope)

- Calls `pgtestdbpy.clone(config, migrator)`: PASS
- Monkeypatches all 5 env vars (`IW_CORE_DB_HOST/PORT/NAME/USER/PASSWORD`): PASS
- Creates SQLAlchemy engine on `postgresql+psycopg://` URL: PASS
- Yields engine; disposes on teardown: PASS

### `_db_test_connection` (simplified)

- Opens connection: PASS
- Yields connection: PASS
- Closes on teardown: PASS
- No outer transaction: PASS

### `db_session`, `db_session_factory`, `test_project`, `cli_get_session`

- All present and API-compatible: PASS
- `db_session` uses `sessionmaker(bind=_db_test_connection)`: PASS

---

## Carry-Forward Teardowns

### `TestOssMigrationDowngrade::test_downgrade_drops_tables`

At `tests/integration/test_oss_migration.py:832`:
```python
# CR-00055 / R-00077: this module shares a session-scoped oss_engine.
# Re-apply the migration SQL so the schema is restored for any test
# that runs after this one under -p randomly.
with oss_engine.connect() as conn:
    conn.execute(text(MIGRATION_SQL))
    conn.commit()
```

**PASS** — `# CR-00055 / R-00077:` comment present; placed after assertions, before end of test.

### `TestProjectOssJobMigrationDowngrade::test_downgrade_drops_table`

At `tests/integration/test_project_oss_job_migration.py:549`:
```python
# CR-00055 / R-00077: this module shares a session-scoped oss_job_engine.
# Re-apply the migration SQL so the schema is restored for any test
# that runs after this one under -p randomly.
with oss_job_engine.connect() as conn:
    conn.execute(text(MIGRATION_SQL))
    conn.commit()
```

**PASS** — `# CR-00055 / R-00077:` comment present; placed correctly.

---

## `_restore_iw_core_instance_row` Autouse Fixture

At `tests/integration/test_db_identity_integration.py:125-156`:

- `@pytest.fixture(autouse=True)`: PASS (function-scoped, runs before every test in the module)
- Takes `migrated_engine: Engine` as parameter: PASS
- Checks `pg_tables` for `iw_core_instance`: PASS
- Runs `alembic upgrade head` if table missing: PASS
- `INSERT INTO iw_core_instance … WHERE NOT EXISTS`: PASS
- Docstring references R-00077 / CR-00055: PASS

Note: Scope is function (default) not "module-scoped". This is correct — the fixture needs to run before EVERY test because `test_daemon_startup_refuses_on_missing_row` DELETEs the row, leaving it absent for the next test. Function-scoped autouse is the right design.

---

## Quarantine Checks (exactly 3)

| Test | `order_dependent` | `xfail(strict=False)` | `# NOTE(P1-CR-C-followup-randomly):` |
|------|-------------------|----------------------|---------------------------------------|
| `TestMigrationRoundtrip::test_downgrade_drops_table_and_upgrade_recreates_with_new_uuid` | PASS (line 297) | PASS — `strict=False` with reason string (lines 298-305) | PASS (line 311) |
| `test_valid_enum_values_accepted` | PASS (line 157) | PASS — `strict=False` with reason string (lines 158-165) | PASS (line 167) |
| `TestI00062MigrationRoundTrip::test_re_upgrade_after_downgrade` | PASS (line 136) | PASS — `strict=False` with reason string (lines 137-145) | PASS (line 149) |

- All 3 reason strings name the leak source (module-scoped engine, specific behavior): PASS
- `strict=False` on all 3 (correct — they pass in "safe" order, so strict=True would xpass-fail): PASS
- `order_dependent` marker NOT re-registered in `pyproject.toml` (already present from CR-00048): PASS
- No `@pytest.mark.skip` or comment-outs: PASS
- All quarantined tests still run (not skipped): PASS

---

## `pyproject.toml` Comment Block

At lines 143-155:

- Describes default-on behaviour: PASS
- Reproduce recipe present (`--randomly-seed=<N>`): PASS
- CR-00048 historical note ("Earlier fallback (CR-00048)") preserved as one paragraph: PASS
- Disable recipe (`pytest -p no:randomly`) absent from comment block: **See MEDIUM finding M1**

---

## Doc Flips

### `tests/CLAUDE.md` §7

- Default-on stated: PASS
- Mechanism described (per-test template-clone, pgtestdbpy, IW_CORE_DB_* monkeypatch): PASS
- Reproduce recipe: PASS
- 4-seed sweep recipe: PASS
- Quarantine policy documented: PASS
- "Earlier fallback (CR-00048)" historical note: PASS
- Disable recipe absent from explicit step: **See LOW finding L1**

### `docs/IW_AI_Core_Testing_Strategy.md` §3

- "pytest-randomly — test-order randomisation (CR-00055, 2026-05-16 — default-on)" subsection: PASS
- Default-on prose with mechanism: PASS
- Reproduce recipe: PASS
- Quarantine policy: PASS
- "Earlier fallback (CR-00048)" historical note: PASS
- Fixture table (lines 125-129) still describes old session-scoped `db_engine` with rollback isolation: **See MEDIUM finding M2**

### `docs/IW_AI_Core_Testing_Strategy.md` §9

Row: `Test-order randomisation (pytest-randomly)`:
```
✅ (CR-00055, 2026-05-16) — default-on; integration suite robust to randomisation via per-test PostgreSQL template-clone (pgtestdbpy>=0.0.1; WAL_LOG strategy override ~10× faster than library default); IW_CORE_DB_* monkeypatched per-test for subprocess isolation; 4-seed sweep green (12345/67890/11111/42424); 3 module-scoped quarantines carried forward as xfail(strict=False). Earlier fallback (CR-00048, 2026-05-12): dep installed, off by default via -p no:randomly; superseded by CR-00055.
```

- Prefix starts with `✅ (CR-00055, 2026-05-16) — default-on; ...`: PASS
- "Earlier fallback (CR-00048)" historical note inline: PASS

### `skills/iw-ai-core-testing/SKILL.md` §2

- Default-on stated: PASS
- Mechanism: PASS
- Reproduce recipe: PASS
- "Earlier fallback (CR-00048)" historical note: PASS

---

## Skill Sync

```
diff -q skills/iw-ai-core-testing/SKILL.md .claude/skills/iw-ai-core-testing/SKILL.md
```

**PASS** — command produces no output; files are byte-identical.

---

## Plan + Changelog (`ai-dev/work/TESTS_ENHANCEMENT.md`)

| Requirement | Status |
|-------------|--------|
| §5 row `P1-CR-C-followup-randomly` — `DONE (CR-00055, 2026-05-16)` with strategy summary | PASS |
| Item 1.4 row — `✅ DONE (CR-00055, 2026-05-16)` (previously PARTIAL) | PASS |
| §11 changelog entry dated 2026-05-16 | PASS |
| §11 entry references CR-00055 | PASS |
| §11 entry references per-test template-clone strategy | PASS |
| §11 entry references WAL_LOG override | PASS |
| §11 entry references 1 autouse fixture + 2 teardowns + 3 quarantines | PASS |
| §11 entry references 4-seed verification numbers | PASS |
| §11 entry references R-00077 | PASS |

---

## Scope Creep Check

| Prohibited Change | Status |
|------------------|--------|
| Production code touched (`orch/`, `dashboard/` outside dashboard conftest, `executor/`, `bin/`, `scripts/`) | NOT PRESENT — PASS |
| New behavioural tests added | NOT PRESENT — PASS |
| Test assertions weakened | NOT PRESENT — PASS |
| Makefile / .github / pre-commit / migrations changes | NOT PRESENT — PASS |
| `vulture` / `deptry` flipped to hard gates | NOT PRESENT — PASS |
| 4th quarantine added without justification | NOT PRESENT — PASS |

---

## Findings

### MEDIUM

#### M1 — `pyproject.toml` comment block missing explicit disable recipe
**File**: `pyproject.toml:143-155`
**Description**: The review checklist specifies the addopts comment block must include both the reproduce recipe (`pytest --randomly-seed=<N>`) and the disable recipe (`pytest -p no:randomly`). The reproduce recipe is present at line 153 (`uv run pytest tests/integration/ -p randomly --randomly-seed=<N> -q`). The disable recipe is absent. The note at line 154 mentions `-p no:randomly` historically ("Earlier fallback (CR-00048)") but does not present it as an explicit current-use instruction.
**Suggested fix**: Add one comment line:
```
# Disable randomisation for a single run:
#     uv run pytest tests/integration/ -p no:randomly
```
between the reproduce recipe and the CR-00048 historical note.

#### M2 — `docs/IW_AI_Core_Testing_Strategy.md` §3 fixture table still describes old isolation model
**File**: `docs/IW_AI_Core_Testing_Strategy.md:125-129`
**Description**: The "testcontainers Postgres" fixture bullet list was not updated to reflect CR-00055's changes:
- Line 126: "`db_engine` — **session-scoped**, schema created once via `Base.metadata.create_all()`, then the FTS DDL is applied (see below), reused across all tests." — stale; `db_engine` is now **function-scoped**, clones template per-test.
- Line 127: "`db_session` — ... each test runs in a transaction that is **rolled back** at teardown." — stale; isolation is now by clone-drop, not rollback.

The immediately following pytest-randomly subsection (line 131+) correctly describes the new model, but the bullet list above it contradicts it. This creates a misleading discrepancy for readers who may rely on the bullet list for quick reference.
**Suggested fix**: Update lines 126-127 to:
```
- `db_engine` — **function-scoped**, clones the session-scoped template (~25 ms via
  `CREATE DATABASE … TEMPLATE …` with WAL_LOG strategy) and yields a per-test engine;
  monkeypatches `IW_CORE_DB_*` env vars so `iw` CLI subprocesses inherit the clone.
- `db_session` — **function-scoped**, bound to the per-test clone; the entire clone is
  dropped at teardown (no rollback needed — each test has its own database).
```
Also add a new bullet for `_pgtestdb_setup`:
```
- `_pgtestdb_setup` — **session-scoped**, builds the migrated template DB once via
  `pgtestdbpy.templates()`; used by `db_engine` to create per-test clones.
```

### LOW

#### L1 — `tests/CLAUDE.md` §7 missing explicit disable recipe
**File**: `tests/CLAUDE.md` (pytest-randomly section)
**Description**: The review checklist specifies the pytest-randomly documentation must include a disable recipe (`pytest -p no:randomly`). The `tests/CLAUDE.md` §7 includes a reproduce recipe and a 4-seed sweep recipe, but no explicit instruction for how to disable randomisation for a specific run. The `-p no:randomly` pattern appears only in the "Earlier fallback (CR-00048)" note as a historical reference. A developer debugging a flaky test may want to disable randomisation temporarily and would benefit from an explicit recipe.
**Suggested fix**: Add a "Disable randomisation (temporarily):" subsection or a brief note:
```
**Disable randomisation for one run:**
uv run pytest tests/integration/ -p no:randomly
```

---

## Summary

All CRITICAL checks pass. Both pre-review gates (`make lint`, `make format-check`) pass with zero violations. The WAL_LOG override is correctly placed, `_pgtestdb_setup` is re-exported, all 3 quarantines and 2 teardowns are properly structured, the `_restore_iw_core_instance_row` autouse fixture is correct, all 4 doc locations are flipped with CR-00048 historical notes, skill files are byte-identical, and `TESTS_ENHANCEMENT.md` updates are comprehensive.

Two MEDIUM findings and one LOW finding were identified, none blocking:
- **M1**: `pyproject.toml` comment block missing explicit disable recipe — one line fix.
- **M2**: `docs/IW_AI_Core_Testing_Strategy.md` §3 fixture table still describes old session-scoped `db_engine` and rollback isolation — three-bullet doc fix, no code change.
- **L1**: `tests/CLAUDE.md` §7 missing explicit disable recipe — one-line doc addition.

---

## Result Contract

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "CR-00055",
  "completion_status": "complete",
  "review_outcome": "pass_with_fixable",
  "findings_by_severity": {
    "critical": [],
    "high": [],
    "medium": [
      {
        "severity": "MEDIUM",
        "title": "pyproject.toml comment block missing explicit disable recipe",
        "file": "pyproject.toml:153-155",
        "description": "The addopts comment block has the reproduce recipe but not the disable recipe (pytest -p no:randomly). The review checklist requires both. The pattern appears only as a historical reference in the CR-00048 note, not as a current-use instruction.",
        "fix": "Add one comment line after the reproduce recipe: '# Disable: uv run pytest tests/integration/ -p no:randomly'"
      },
      {
        "severity": "MEDIUM",
        "title": "docs/IW_AI_Core_Testing_Strategy.md §3 fixture table stale after CR-00055",
        "file": "docs/IW_AI_Core_Testing_Strategy.md:125-129",
        "description": "Lines 126-127 still describe db_engine as session-scoped with Base.metadata.create_all() and db_session as using rollback isolation. Both are inaccurate post-CR-00055: db_engine is now function-scoped (per-test clone), and isolation is by clone-drop not rollback. The adjacent pytest-randomly subsection (line 131+) correctly describes the new model, creating a contradictory section.",
        "fix": "Update bullet points for db_engine and db_session to describe the per-test clone model; add a _pgtestdb_setup bullet."
      }
    ],
    "low": [
      {
        "severity": "LOW",
        "title": "tests/CLAUDE.md §7 missing explicit disable recipe",
        "file": "tests/CLAUDE.md (pytest-randomly section)",
        "description": "No explicit 'Disable randomisation: pytest -p no:randomly' recipe in the pytest-randomly section. Only present as a historical reference in the CR-00048 note.",
        "fix": "Add a brief 'Disable randomisation (temporarily):' recipe block after the 4-seed sweep."
      }
    ]
  },
  "files_reviewed": [
    "pyproject.toml",
    "uv.lock",
    "tests/integration/conftest.py",
    "tests/dashboard/conftest.py",
    "tests/integration/test_oss_migration.py",
    "tests/integration/test_project_oss_job_migration.py",
    "tests/integration/test_db_identity_integration.py",
    "tests/integration/test_pending_migration_log_migration.py",
    "tests/integration/db/test_i_00062_migration.py",
    "tests/CLAUDE.md",
    "docs/IW_AI_Core_Testing_Strategy.md",
    "skills/iw-ai-core-testing/SKILL.md",
    ".claude/skills/iw-ai-core-testing/SKILL.md",
    "ai-dev/work/TESTS_ENHANCEMENT.md"
  ],
  "blockers": [],
  "notes": "Both CRITICAL checks pass cleanly. The 4-seed sweep reported in S01 (all green at 0 failures, 0 errors, xfailed+xpassed=6 across all seeds) is consistent with the implementation reviewed. The two MEDIUM findings are documentation-only fixes that require no code or fixture changes; they do not affect test correctness or the WAL_LOG isolation mechanism. The LOW finding is a UX improvement for the docs. Recommend fixing M1 and M2 in a follow-up commit before merge, but they do not block S03 review or QV gates."
}
```
