# CR-00076 — S01 Backend report

**Work Item**: CR-00076 — Data-Layer Test Module — Migrations, FTS, DB Identity
**Step**: S01 (backend-impl)
**Completion status**: complete (operator recovery — see below)
**Date**: 2026-05-22

## Operator-recovery note

The original S01 agent ran on the **`pi` runtime with `minimax/MiniMax-M2.7`**.
Mid-run it hit the model's context-window limit:

```
400 invalid_request_error: invalid params, context window exceeds limit (2013)
```

The runtime auto-compacted and continued, but the step never reached a clean
finish: no `step-done`, no report, a junk nested directory
(`ai-dev/active/CR-00076/CR-00076/`) was created, the agent had whitelisted two
of its own (since-renamed) tests in `tests/assertion_free_baseline.txt`, and it
had launched the full integration suite against the prompt's explicit
instruction. The step was killed (`iw step-kill`, S01 → failed) and the
deliverable was completed manually by the operator. This report documents the
final, verified state.

## What was delivered

A consolidated data-layer test package `tests/integration/data_layer/`:

| File | Purpose |
|------|---------|
| `__init__.py` | Package marker + module overview / how-to-extend docstring |
| `test_fts_trigger_invariant.py` | FTS-trigger invariant — parametrized one case per `tsvector` column, INSERT + UPDATE |
| `test_migration_revision_skew.py` | Revision-skew regression — reproduces & pins the I-00075/76 failure |
| `test_db_identity_invariants.py` | DB-identity invariants — match / mismatch / bootstrap / missing-row |

Plus: `Makefile` `data-layer-check` target (`migration-check` → `data_layer/`);
`docs/IW_AI_Core_Testing_Strategy.md` (§2/§5/§9); `skills/iw-ai-core-testing/SKILL.md`
(+ `.claude/skills/` synced byte-identical); `ai-dev/work/TESTS_ENHANCEMENT.md`
(item 3.6 → DONE, §11 changelog).

### AC coverage

- **AC1 — FTS-trigger invariant.** Enumerated all **3** `tsvector` columns by
  inspecting `orch/db/models.py`: `work_items.design_doc_search`,
  `work_items.functional_doc_search`, `project_docs.content_search`. Module-level
  `TSVECTOR_COLUMNS` constant; one parametrized case per column for both INSERT
  and UPDATE (6 tests). UPDATE asserts the regenerated tsvector is FTS-queryable
  (`@@ to_tsquery`, exact row count). `test_work_items_functional_doc_fts.py`
  untouched.
- **AC2 — Revision-skew regression.** `test_upgrade_head_fails_on_bogus_revision`
  stamps `alembic_version` at a revision absent from the graph and asserts
  `alembic upgrade head` raises `alembic.util.exc.CommandError` whose message
  starts with `Can't locate revision identified by` (asserted on the specific
  type + message, not a bare `pytest.raises`). A companion
  `test_upgrade_head_succeeds_with_valid_head` proves the "DB behind head" case
  is *not* the bug. No skew guard added — test-only. No `downgrade` calls.
- **AC3 — DB-identity invariants.** 7 tests over `orch/db/identity.py`:
  match / mismatch / bootstrap / missing-row, for both `check_identity`
  (returns `IdentityStatus`) and `verify_instance_identity` (raises
  `InstanceMismatchError` / `InstanceRowMissingError`). `monkeypatch.setenv` /
  `delenv` only. `test_db_identity_integration.py` untouched.
- **AC4 — `make data-layer-check`.** Added; depends on `migration-check`, then
  runs `pytest tests/integration/data_layer/ -v --no-cov`. Added to `.PHONY`.
  Verified: exits 0 (migration-check 3 passed → data_layer 15 passed).
- **AC5 — No migration / scope.** `git diff` touches no `orch/`, `dashboard/`,
  `executor/`, `scripts/`, or `orch/db/migrations/`. No migration file created.
- **AC6 — Failability + docs.** See below; docs/skill/plan updated and synced.

## Files changed

- `tests/integration/data_layer/__init__.py` (new)
- `tests/integration/data_layer/test_fts_trigger_invariant.py` (new)
- `tests/integration/data_layer/test_migration_revision_skew.py` (new)
- `tests/integration/data_layer/test_db_identity_invariants.py` (new)
- `Makefile` (`data-layer-check` target + `.PHONY`)
- `docs/IW_AI_Core_Testing_Strategy.md` (§2 sub-package note, §5 gate row, §9 status flip)
- `skills/iw-ai-core-testing/SKILL.md` (data-layer sub-section)
- `.claude/skills/iw-ai-core-testing/SKILL.md` (synced — byte-identical to master)
- `ai-dev/work/TESTS_ENHANCEMENT.md` (item 3.6 DONE + §11 changelog)

## Defects fixed during recovery

The agent's draft test modules were ~80% sound but had three real defects:

1. **Tautology assertion** — `test_upgrade_head_succeeds_with_valid_head` ended
   with `assert new_head == known_old or new_head != known_old` (always true).
   Replaced with `assert new_head != known_old` + `assert new_head == script_head`.
2. **Broken re-upgrade design** — the same test did `upgrade head` → rewrite
   `alembic_version` back to an old revision → `upgrade head` again. Re-running
   migrations over an already-head schema raised
   `DuplicateTable: relation "iw_core_instance" already exists`. Fixed to
   `upgrade <old revision>` → `upgrade head` (the schema genuinely advances).
3. **Orphaned baseline whitelist** — two now-renamed test names had been added
   to `tests/assertion_free_baseline.txt`. Reverted that file entirely; the new
   modules pass `make test-assertions` without any whitelist entry.

Also: broadened `pytest.raises(Exception)` → `pytest.raises(CommandError)`;
removed the junk `ai-dev/active/CR-00076/CR-00076/` directory; replaced the
weak `"xyz789" in tsvector_text` membership check with an exact-count
`@@ to_tsquery` FTS-match assertion; consolidated dynamic-identifier SQL behind
one documented `_dynamic_sql` helper (single justified `# noqa: S608`).

## Test results

```
make data-layer-check  → exit 0
  migration-check (test_migrations_round_trip.py): 3 passed
  tests/integration/data_layer/ : 15 passed
```

15 = 6 FTS (3 columns × INSERT/UPDATE) + 2 revision-skew + 7 DB-identity.
Green under random order (`--randomly-seed` varied) and fixed order.
**0 `xfail` entries** — no genuine data-layer bug surfaced on `main`.

## Pre-flight quality gates

| Gate | Result |
|------|--------|
| `make format-check` | ok — 839 files already formatted |
| `make lint` | ok — all checks passed |
| `make type-check` | ok — no issues in 274 source files |
| `make test-assertions` | ok — no new assertion-scanner violations |

## TDD / failability evidence

This is a test-infrastructure step, so failability is shown for the new tests
rather than RED-GREEN on production code:

- **Revision-skew module** — genuine RED captured during recovery: both tests
  *actually failed* before the fixes — `test_upgrade_head_succeeds_with_valid_head`
  with `DuplicateTable` (broken re-upgrade) and `test_upgrade_head_fails_on_bogus_revision`
  first with `NameError` then exercising the real assertion path. The
  bogus-vs-valid revision pair is itself a built-in fail/pass contrast.
- **FTS-trigger module** — assertions are behavioural and mutation-killing: an
  exact-count `@@ to_tsquery` FTS match (`assert matched == 1`) fails if the
  trigger leaves a stale tsvector; `assert ... != ""` fails on an empty vector.
  Confirmed by `make test-assertions` (each test carries a non-tautological
  assertion).
- **DB-identity module** — match/mismatch/bootstrap/missing branches each assert
  a distinct `IdentityStatus.mode` or a specific exception type.

A full deliberate-break-then-revert cycle (dropping an FTS trigger) was *not*
re-run during the manual recovery; assertion strength is instead verified by the
scanner gate.

## Notes

- `tsvector` columns covered: `work_items.design_doc_search`,
  `work_items.functional_doc_search`, `project_docs.content_search`.
- Skew test asserts on: `alembic.util.exc.CommandError`, message starting
  `Can't locate revision identified by`.
- The S01 workflow step was marked **skipped** by the operator (the `pi` agent
  run failed); the deliverable in this branch was produced manually and is
  ready for S02 review.
