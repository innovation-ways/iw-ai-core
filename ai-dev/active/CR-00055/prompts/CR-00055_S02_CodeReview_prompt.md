# CR-00055_S02_CodeReview_prompt

**Work Item**: CR-00055 -- Re-enable `pytest-randomly` by default via per-test PostgreSQL template-clone
**Step**: S02
**Agent**: code-review-impl

---

## Input Files

- `ai-dev/active/CR-00055/CR-00055_CR_Design.md` -- Source of truth for scope + ACs.
- `ai-dev/active/CR-00055/reports/CR-00055_S01_Backend_report.md` -- S01's report.
- `docs/research/R-00077-pytest-randomly-isolation-strategy.md` -- Strategy rationale (Appendix B documents the WAL_LOG gotcha and the `_pgtestdb_setup` re-export gotcha).
- The git diff vs main of every file in the design's "Impacted Paths" section.

## Output Files

- `ai-dev/active/CR-00055/reports/CR-00055_S02_CodeReview_report.md` -- Review report.

## Context

You are reviewing S01's implementation of CR-00055. The strategy is per-test PostgreSQL template-clone via `pgtestdbpy`. Two gotchas from the spike work surface as MUST-VERIFY items in this review (without them the suite either runs 3× slower OR is entirely unrunnable for dashboard tests).

## Review Checklist

### CRITICAL — verify the two perf/correctness hinges

1. **WAL_LOG override on `pgtestdbpy.QRY_DB_CLONE`.** `pgtestdbpy>=0.0.1` hardcodes `STRATEGY=FILE_COPY` in its query template; on this codebase's schema FILE_COPY is **~10× slower** than the WAL_LOG default (~310 ms per clone vs ~25 ms — the difference between a ~28-min sweep and a ~10-min sweep). The override must be present in `tests/integration/conftest.py`, inside `_pgtestdb_setup`, **before** entering `pgtestdbpy.templates()`. Grep:
   ```bash
   grep -n "pgtestdbpy.QRY_DB_CLONE" tests/integration/conftest.py
   ```
   Must return a line that assigns a clone query WITHOUT `STRATEGY=FILE_COPY` (i.e. `'CREATE DATABASE "{db_name}" WITH TEMPLATE "{template}" OWNER "{user}"'`). If absent or with FILE_COPY still in the string, this is a CRITICAL finding — S09 will overrun its 1 200 s budget.

2. **`_pgtestdb_setup` re-exported from `tests/dashboard/conftest.py`.** Without this, every dashboard test fails at fixture resolution with `fixture '_pgtestdb_setup' not found`. The spike's v1 sweep had 549 such errors before the re-export was added. Grep:
   ```bash
   grep -n "_pgtestdb_setup" tests/dashboard/conftest.py
   ```
   Must appear in the `from tests.integration.conftest import (...)` block alongside `_db_test_connection`, `db_engine`, `db_session`, `db_session_factory`, `pg_container`, `test_project`. If absent, this is a CRITICAL finding — S09 will fail with hundreds of fixture errors.

### Pre-review gate

Run before scoring:
```bash
make lint
make format-check
```

Both must report zero new violations.

### Scope discipline

- AC1: `grep -n 'no:randomly' pyproject.toml` returns nothing. `--strict-markers` still present. `pgtestdbpy>=0.0.1` added to `[dependency-groups] dev`. `uv.lock` regenerated.
- Files modified are exactly the set in the design's "Impacted Paths". No production code touched (orch/, dashboard/ outside `tests/dashboard/conftest.py`, executor/, bin/, scripts/). No migrations. No Makefile / .github changes.

### Fixture implementation

- `tests/integration/conftest.py`:
  - New `_migrate_template(url: str) -> None` callable applies OSS enums + `_run_alembic_upgrade` + `Base.metadata.create_all` ONCE against the template URL.
  - New session-scoped `_pgtestdb_setup(pg_container)` builds `pgtestdbpy.Config` from the container superuser URL, builds `pgtestdbpy.Migrator(..., user="iwcore_test", password="iwcore_test", db_name="iwcore_template", ...)`, applies the WAL_LOG `QRY_DB_CLONE` override, wraps `pgtestdbpy.templates(config, migrator)`, yields `(config, migrator)`.
  - `db_engine` is now **function-scoped** (not session-scoped). It calls `pgtestdbpy.clone()`, monkeypatches all 5 `IW_CORE_DB_HOST/PORT/NAME/USER/PASSWORD` env vars to the clone URL components, creates a SQLAlchemy engine on `postgresql+psycopg://...`, yields the engine, disposes on teardown.
  - `_db_test_connection` is simplified: `connection = db_engine.connect(); yield connection; connection.close()` — no outer transaction (the clone is dropped at teardown).
  - `db_session`, `db_session_factory`, `test_project`, `cli_get_session` API is preserved byte-for-byte (no signature changes, no behaviour changes from a caller's perspective).

### Carry-forward edits

- `tests/integration/test_oss_migration.py::TestOssMigrationDowngrade::test_downgrade_drops_tables` — re-applies `MIGRATION_SQL` at the end with a `# CR-00055 / R-00077:` comment.
- `tests/integration/test_project_oss_job_migration.py::TestProjectOssJobMigrationDowngrade::test_downgrade_drops_table` — same pattern.
- `tests/integration/test_db_identity_integration.py` — new module-level autouse `_restore_iw_core_instance_row` fixture (NOT class-scoped; takes `migrated_engine`; checks `pg_tables` for `iw_core_instance`, runs alembic upgrade head if the table is missing, then INSERT ... WHERE NOT EXISTS to ensure the row exists). Docstring references R-00077 / CR-00055.

### Quarantines (exactly 3)

All with `@pytest.mark.order_dependent` + `@pytest.mark.xfail(strict=False, reason="…")` + `# NOTE(P1-CR-C-followup-randomly):` tracking comment:

1. `tests/integration/test_db_identity_integration.py::TestMigrationRoundtrip::test_downgrade_drops_table_and_upgrade_recreates_with_new_uuid`
2. `tests/integration/test_pending_migration_log_migration.py::test_valid_enum_values_accepted`
3. `tests/integration/db/test_i_00062_migration.py::TestI00062MigrationRoundTrip::test_re_upgrade_after_downgrade`

Hard rules to verify:
- `strict=False` on every quarantine (strict=True would xpass-fail green runs — these tests pass in alphabetical order).
- `reason` string names the leak source (not just "order-dependent"); e.g. references `migrated_engine` being module-scoped + the specific data/schema leak.
- `# NOTE(P1-CR-C-followup-randomly):` tracking comment present (inside the test body's first line).
- The `order_dependent` marker is NOT re-registered in `pyproject.toml` (it's already there from CR-00048).
- No `@pytest.mark.skip`, no comment-outs. Quarantined tests must still run.

### `pyproject.toml` comment rewrite

The block above `addopts` must:
- Describe default-on behaviour.
- Include reproduce + disable recipes (`pytest --randomly-seed=<N>`, `pytest -p no:randomly`).
- Preserve the CR-00048 fallback context as a brief "Earlier fallback (CR-00048)" historical note (one paragraph; not silently deleted — that's a MEDIUM-fixable finding if missing).

### Doc flips (all 4 locations)

- `tests/CLAUDE.md` §7 ("pytest-randomly — test-order randomisation") — describes default-on + the mechanism (per-test template-clone via pgtestdbpy + IW_CORE_DB_* monkeypatch for subprocess inheritance) + historical-note paragraph.
- `docs/IW_AI_Core_Testing_Strategy.md` §3 subsection — same.
- `docs/IW_AI_Core_Testing_Strategy.md` §9 row "Test-order randomisation (`pytest-randomly`)" — flipped ⚠️ to ✅; prefix starts with `"✅ (CR-00055, 2026-05-16) — default-on; ..."`.
- `skills/iw-ai-core-testing/SKILL.md` §2 — same.

All four locations must preserve a brief "Earlier fallback (CR-00048)" historical note rather than silently deleting the prior prose. If any of the four omits the historical note, flag as MEDIUM-fixable.

### Skill sync

```bash
diff -q skills/iw-ai-core-testing/SKILL.md .claude/skills/iw-ai-core-testing/SKILL.md
```

Must produce no output (byte-identical) — verifies S01 ran `iw sync-skills --force iw-ai-core-testing`.

### Plan + changelog

`ai-dev/work/TESTS_ENHANCEMENT.md`:
- §5 row `P1-CR-C-followup-randomly` — DONE (CR-00055, 2026-05-16) with the strategy summary.
- Item 1.4 row — DONE (CR-00055, 2026-05-16) (was PARTIAL).
- §11 changelog entry dated 2026-05-16 — references CR-00055, the per-test template-clone strategy, the WAL_LOG override, the 1 autouse fixture + 2 teardowns + 3 quarantines, the 4-seed verification numbers, and R-00077.

Counts must be internally consistent (§11 claims match §5 claims match item 1.4 claims).

## Scope creep checks (REJECT if present)

- Production code touched (orch/, dashboard/ outside `tests/dashboard/conftest.py`, executor/, bin/, scripts/).
- New behavioural tests added (this CR fixes test-isolation; the existing suite is the proof).
- Test assertions weakened.
- Makefile / .github / pre-commit / migrations changes.
- `vulture` / `deptry` flipped to hard gates.
- Sibling project ports.
- Assertion baseline scrub.
- 4th quarantine added without justification (the spike was definitive — 3 quarantines).

## Subagent Result Contract

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "CR-00055",
  "completion_status": "complete",
  "review_outcome": "pass|pass_with_fixable|reject",
  "findings_by_severity": {
    "critical": [],
    "high": [],
    "medium": [],
    "low": []
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
  "notes": "WAL_LOG override verified present. _pgtestdb_setup re-export verified in dashboard conftest. 3 quarantines all with substantive reasons + tracking comments. All 4 doc locations flipped with historical-note pattern preserved. Skill in sync. Plan + changelog DONE with internally-consistent counts."
}
```

- `review_outcome`: `pass` (no findings), `pass_with_fixable` (only MEDIUM/LOW), or `reject` (any CRITICAL or HIGH).
- `findings_by_severity`: each list contains entries `{"severity": "...", "title": "...", "file": "path:line", "description": "...", "fix": "..."}`.

## Lifecycle Commands

```bash
uv run iw step-start CR-00055 --step S02
# ... review ...
uv run iw step-done CR-00055 --step S02 --report ai-dev/active/CR-00055/reports/CR-00055_S02_CodeReview_report.md
```
