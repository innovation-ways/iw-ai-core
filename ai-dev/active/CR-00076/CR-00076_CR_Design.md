# CR-00076: Data-Layer Test Module — Migrations, FTS, DB Identity

**Type**: Change Request
**Priority**: Medium
**Reason**: Phase 3 item 3.6 of the Testing Enhancement Plan — hard-won data-layer invariants (FTS-trigger requirement, per-worktree migration-revision skew, DB-identity pin) are documented as rules in `CLAUDE.md` but are not all formally asserted by tests. The I-00075 / I-00076 incidents exposed a revision-skew failure that went undetected until a worktree's compose stack died; this CR consolidates the coverage and formalises that failure as a regression test so a recurrence is caught by the suite.
**Created**: 2026-05-21
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt — this CR's new tests use the existing testcontainer `db_session` fixture and nothing else.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. **This item leaves migrations unchanged** — it tests migrations, it does not add one. No new Alembic migration file may be created.

## Description

Consolidate the project's data-layer test coverage into a formal package `tests/integration/data_layer/` with three new modules: an FTS-trigger invariant that generalises existing FTS coverage to every `tsvector` column; a revision-skew regression test that reproduces the I-00075 / I-00076 failure class; and a DB-identity invariant test that exercises the `orch/db/identity.py` fingerprint and `IW_CORE_EXPECTED_INSTANCE_ID` pin. A `make data-layer-check` convenience target aggregates the new module with the existing `migration-check`. No production code is touched.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Relevant: the data-layer invariants (FTS-trigger requirement, revision-skew detection, DB-identity pin) are documented in `CLAUDE.md`; the existing `tests/integration/test_migrations_round_trip.py` (run by `make migration-check`) and `tests/integration/test_db_identity_integration.py` and `tests/integration/test_work_items_functional_doc_fts.py` provide prior art. This CR is part of the phased plan in `ai-dev/work/TESTS_ENHANCEMENT.md` (item 3.6). Read `tests/CLAUDE.md` and `skills/iw-ai-core-testing/SKILL.md` before implementing.

## Current Behavior

- The FTS-trigger requirement (the `tsvector` columns must be populated and refreshed by their database triggers) is documented in `tests/CLAUDE.md` and `CLAUDE.md` but is only partially exercised. `tests/integration/test_work_items_functional_doc_fts.py` covers the `work_items` `tsvector` columns; there is no single test that asserts the invariant across **all** `tsvector` columns (it omits `project_docs.content_search`).
- The per-worktree-DB revision-skew failure mode — a worktree DB stamped at revision X while the repo's migration files lack revision X, causing `alembic upgrade head` to die — is described in `CLAUDE.md` (I-00075 / I-00076 diagnosis) but is not asserted by any test. The failure is only discovered when a compose stack actually dies.
- `orch/db/identity.py` and the `IW_CORE_EXPECTED_INSTANCE_ID` pin are tested by `tests/integration/test_db_identity_integration.py`, but the coverage is not consolidated into a formal data-layer module and the invariant boundaries are not documented explicitly.
- There is no `make data-layer-check` convenience target; the caller must know to run `make migration-check` and the separate integration tests individually.

## Desired Behavior

- A consolidated data-layer test package `tests/integration/data_layer/` (with `__init__.py`) holds three new modules:
  1. **`test_fts_trigger_invariant.py`** — for every `tsvector` column (there are three: `work_items.design_doc_search`, `work_items.functional_doc_search`, `project_docs.content_search`), INSERT a row and then UPDATE a searchable field, and assert the `tsvector` column is populated and refreshed by the database trigger. The `db_session` fixture's template DB already installs all three FTS function+trigger pairs via `alembic upgrade head` (see `tests/integration/conftest.py`). The test generalises `test_work_items_functional_doc_fts.py` — it does not replace that file but extends the same invariant to every `tsvector` column.
  2. **`test_migration_revision_skew.py`** — reproduces the I-00075 / I-00076 failure class as a regression test: a testcontainer DB whose `alembic_version` row points at a revision ID **absent from the repo's migration graph**, against which `alembic upgrade head` is run and asserted to fail with the characteristic resolution error (`Can't locate revision identified by '<rev>'`). This pins the failure mode so a regression — or a change in the error signature — is caught by the suite. No skew-detection guard exists in the codebase and **this CR adds none** (it is test-only); the module documents and pins the failure, it does not assert early detection. Alembic is only invoked from this dedicated migration test; any downgrade targets a specific revision ID, never `-1` (per `tests/CLAUDE.md` rule 4a).
  3. **`test_db_identity_invariants.py`** — exercises `orch/db/identity.py`: when the instance fingerprint matches `IW_CORE_EXPECTED_INSTANCE_ID`, connections proceed; when it mismatches, the system refuses. Builds on `test_db_identity_integration.py` — does not replace it.
- A **`make data-layer-check`** convenience target runs `make migration-check` plus `uv run pytest tests/integration/data_layer/ -v --no-cov`, so one command exercises the entire data-layer gate.
- Tests land under `tests/integration/` so the existing **`integration-tests` daemon QV gate** (`make test-integration`) runs them automatically — **no new canonical QV gate** is introduced.
- If any new test surfaces a genuine data-layer bug in the current codebase, it is recorded as a failing reproduction marked `xfail` with a filed Incident — never fixed in-CR (this CR is strictly test-only).
- At S01 time, `docs/IW_AI_Core_Testing_Strategy.md` (§3/§5/§9), `skills/iw-ai-core-testing/SKILL.md`, and `ai-dev/work/TESTS_ENHANCEMENT.md` (item 3.6 DONE + §11 changelog) are updated.

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `tests/integration/` | FTS, identity, and migration tests scattered across individual files | + consolidated `data_layer/` sub-package with 3 focused modules |
| `tests/integration/conftest.py` | Shared integration fixtures | Possibly extended with data-layer-specific seed helpers |
| `Makefile` | `migration-check` exists; no `data-layer-check` | + `data-layer-check` aggregating `migration-check` + `data_layer/` module |
| `docs/IW_AI_Core_Testing_Strategy.md` | Does not describe the consolidated data-layer module | Updated (§3 / §5 / §9) |
| `skills/iw-ai-core-testing/SKILL.md` | Does not note the data-layer package | Updated + synced |
| `ai-dev/work/TESTS_ENHANCEMENT.md` | Item 3.6 = TODO (partly done) | Marked DONE (CR-00076) with §11 changelog |

### Breaking Changes

- None. This CR adds tests, a Makefile target, and doc updates. No production code, no API, no schema, no behaviour change.

### Data Migration

- None. No schema change, no migration file, nothing to reverse.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | backend-impl | Data-layer package + 3 test modules; `make data-layer-check`; strategy-doc + skill + plan updates | — |
| S02 | code-review-impl | Per-agent review of S01 | — |
| S03 | code-review-final-impl | Global cross-agent review of all work | — |
| S04 | qv-gate | `lint` → `make lint` | — |
| S05 | qv-gate | `assertions` → `make test-assertions` | — |
| S06 | qv-gate | `format` → `make format-check` | — |
| S07 | qv-gate | `typecheck` → `make type-check` | — |
| S08 | qv-gate | `unit-tests` → `make test-unit` | — |
| S09 | qv-gate | `integration-tests` → `make test-integration` (runs the new data-layer module) | — |
| S10 | qv-gate | `diff-coverage` → `make diff-coverage` | — |
| S11 | qv-gate | `security-secrets` → `make security-secrets` | — |
| S12 | self-assess-impl | Self-assessment via the `iw-item-analyze` skill | — |

Agent slugs: `backend-impl`, `code-review-impl`, `code-review-final-impl`, `qv-gate`, `self-assess-impl`.

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: None — no migration file is added. Tests use testcontainer DBs only.

### API Changes

- **New endpoints**: None
- **Modified endpoints**: None
- **Removed endpoints**: None

### Frontend Changes

- **New components**: None
- **Modified components**: None
- **Removed components**: None

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `CR-00076_CR_Design.md` | Design | This document |
| `CR-00076_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for the orchestrator |
| `prompts/CR-00076_S01_Backend_prompt.md` | Prompt | S01 implementation instructions |
| `prompts/CR-00076_S02_CodeReview_prompt.md` | Prompt | S02 per-agent review instructions |
| `prompts/CR-00076_S03_CodeReview_Final_prompt.md` | Prompt | S03 final cross-agent review instructions |
| `prompts/CR-00076_S12_SelfAssess_prompt.md` | Prompt | S12 self-assessment instructions |

Reports are created during execution in `ai-dev/work/CR-00076/reports/`.

### Files created/modified by the implementation

| File | Action | Purpose |
|------|--------|---------|
| `tests/integration/data_layer/__init__.py` | Create | Package marker |
| `tests/integration/data_layer/test_fts_trigger_invariant.py` | Create | FTS-trigger invariant across all FTS-bearing tables |
| `tests/integration/data_layer/test_migration_revision_skew.py` | Create | Per-worktree-DB revision-skew detection (I-00075 / I-00076 class) |
| `tests/integration/data_layer/test_db_identity_invariants.py` | Create | DB-identity fingerprint and pin invariants |
| `tests/integration/conftest.py` | Modify (if needed) | Shared data-layer-specific seed helpers |
| `tests/fixtures/**` | Create (if needed) | Shared seed helpers for the data-layer modules |
| `Makefile` | Modify | `data-layer-check` target, `.PHONY` |
| `docs/IW_AI_Core_Testing_Strategy.md` | Modify | Document the data-layer module (§3 / §5 / §9) |
| `skills/iw-ai-core-testing/SKILL.md` | Modify | Note the data-layer package + how to extend it |
| `.claude/skills/iw-ai-core-testing/SKILL.md` | Modify | Synced copy (`iw sync-skills --force iw-ai-core-testing`) |
| `ai-dev/work/TESTS_ENHANCEMENT.md` | Modify | Mark item 3.6 DONE; §11 changelog |

## Acceptance Criteria

### AC1: FTS-trigger invariant covers all tsvector columns

```
Given the testcontainer db_session fixture (its template DB installs all FTS
     triggers via alembic upgrade head)
When tests/integration/data_layer/test_fts_trigger_invariant.py runs
Then for every tsvector column — work_items.design_doc_search,
     work_items.functional_doc_search, project_docs.content_search — an INSERT
     followed by an UPDATE causes that tsvector column to be populated and refreshed
And the test is parametrized one case per tsvector column so a failure names
     the offending column
And the existing test_work_items_functional_doc_fts.py remains untouched and
     still passes (this CR extends, it does not replace)
```

### AC2: Revision-skew failure class is pinned by a regression test

```
Given a testcontainer DB whose alembic_version row points at a revision ID
     that is absent from the repo's migration graph
When tests/integration/data_layer/test_migration_revision_skew.py runs
     alembic upgrade head against that DB
Then the upgrade fails with the characteristic resolution error
     ("Can't locate revision identified by '<rev>'") — reproducing the
     I-00075 / I-00076 failure mode
And the test asserts on that specific error (not a bare pytest.raises) so a
     regression or an error-signature change is caught
And no skew-detection guard is added — this CR adds no production code; any
     Alembic downgrade in the test targets a specific revision ID, never -1
```

### AC3: DB-identity invariant tests cover match and mismatch paths

```
Given orch/db/identity.py and the IW_CORE_EXPECTED_INSTANCE_ID pin
When tests/integration/data_layer/test_db_identity_invariants.py runs
Then the match path (fingerprint matches the expected pin) is asserted to allow
     connections to proceed
And the mismatch path (fingerprint differs from the expected pin) is asserted to
     cause the system to refuse the connection
And the existing test_db_identity_integration.py remains untouched and still passes
```

### AC4: make data-layer-check aggregates the new module and the existing migration-check

```
Given the Makefile
When make data-layer-check runs
Then it invokes make migration-check (tests/integration/test_migrations_round_trip.py
     via its own make target)
And it runs uv run pytest tests/integration/data_layer/ -v --no-cov
And both commands must pass for the target to succeed
And the existing make migration-check target is untouched and still runs standalone
```

### AC5: No new migration file; existing migration-check and round-trip tests unaffected

```
Given the repository at the end of S01
When git diff origin/main -- orch/db/migrations/ is inspected
Then it is empty — no new migration file has been created
And make migration-check still passes (test_migrations_round_trip.py unchanged)
And no file outside scope.allowed_paths has been modified
```

### AC6: Every new test can fail; docs, skill, and plan updated and synced

```
Given the data-layer test package
When S01 completes
Then each of the three new test modules has a tdd_red_evidence entry: a deliberate-break
     demonstration (e.g. dropping an FTS trigger and confirming the FTS test fails;
     pointing the DB's alembic_version at a valid head so the upgrade succeeds and
     confirming the skew test fails; faking a fingerprint match and confirming the
     identity mismatch test fails) followed by a revert
And docs/IW_AI_Core_Testing_Strategy.md describes the data-layer module (§3 / §5 / §9)
And skills/iw-ai-core-testing/SKILL.md notes the data-layer package and how to extend it
And .claude/skills/iw-ai-core-testing/SKILL.md is byte-identical to its master
     (iw sync-skills --force iw-ai-core-testing was run)
And ai-dev/work/TESTS_ENHANCEMENT.md marks item 3.6 DONE with a §11 changelog entry
```

## Rollback Plan

- **Database**: Not applicable — no migration, no schema change.
- **Code**: Revert the squash-merge commit. The CR adds only tests, a Makefile target, and doc updates — reverting removes them cleanly with no residue.
- **Data**: No data loss on rollback — nothing in the CR writes to any persistent store.

## Dependencies

- **Depends on**: None functionally.
- **Shared-file serialization**: CR-00076 modifies `docs/IW_AI_Core_Testing_Strategy.md`, `skills/iw-ai-core-testing/**`, `.claude/skills/iw-ai-core-testing/**`, `ai-dev/work/TESTS_ENHANCEMENT.md`, and `tests/integration/conftest.py`, which are ALSO modified by CR-00072, CR-00073, CR-00074, and CR-00075 (the other Phase 3 testing CRs). These five CRs therefore **must NOT run in the same parallel batch** — the batch executor must serialize them (one at a time) to avoid merge conflicts on those shared files.
- **Blocks**: None.

## Impacted Paths

- `tests/integration/data_layer/**`
- `tests/integration/test_work_items_functional_doc_fts.py`
- `tests/integration/conftest.py`
- `tests/fixtures/**`
- `Makefile`
- `docs/IW_AI_Core_Testing_Strategy.md`
- `skills/iw-ai-core-testing/**`
- `.claude/skills/iw-ai-core-testing/**`
- `ai-dev/work/TESTS_ENHANCEMENT.md`

## TDD Approach

This is a test-infrastructure CR — the new tests *are* the deliverable, so classic RED-GREEN does not apply to production code. The "every test must be able to fail" requirement is satisfied differently:

- **FTS-trigger invariant — prove it can fail.** Before reporting completion, S01 must demonstrate the test catches a regression: temporarily `DROP` one FTS trigger from the test's DB (e.g. `DROP TRIGGER trg_work_items_fts ON work_items`), run `test_fts_trigger_invariant.py`, confirm that column's parametrized case fails because the tsvector is not refreshed, then revert. The captured failing output is recorded as `tdd_red_evidence`.
- **Revision-skew regression — prove it can fail.** Temporarily point the testcontainer DB's `alembic_version` at a valid head revision (instead of an absent one), run `test_migration_revision_skew.py`, confirm the test fails because `alembic upgrade head` succeeds and the expected `Can't locate revision` error is not raised, then revert.
- **DB-identity invariants — prove they can fail.** Temporarily remove the mismatch branch's refusal logic (or mock the fingerprint to always match), run `test_db_identity_invariants.py`, confirm the mismatch case fails, then revert.
- **Unit tests**: None — there is no pure logic to unit-test; the deliverable is integration-level data-layer tests.
- **Integration tests**: the three new modules under `tests/integration/data_layer/`. All use the testcontainer `db_session` fixture; none touch the live DB.
- **Updated tests**: None — no existing test changes behaviour. If a new test surfaces a genuine data-layer bug, it is `xfail`-ed with a filed Incident (AC6), not fixed.

## Notes

- **Extends, does not replace.** `test_migrations_round_trip.py` and `make migration-check` remain the canonical migration-round-trip gate. The new `test_migration_revision_skew.py` adds a different check (reproducing the revision-skew failure mode) and does not duplicate or replace the round-trip test.
- **Risk — a new test surfaces a genuine data-layer bug on `main`.** Expected and acceptable. AC6's `xfail` + Incident mechanism absorbs it so the CR can merge; each genuine bug gets a filed Incident so it is tracked.
- **Alembic invocation rules.** `tests/CLAUDE.md` rule 4a: Alembic is only invoked from dedicated migration tests; downgrade must target a specific revision ID, never `-1`. The revision-skew test must obey this.
- **FTS column discovery.** The implementer must enumerate every `tsvector` column by inspecting `orch/db/models.py` at implementation time — note `work_items` carries two (`design_doc_search` and `functional_doc_search`). The set may grow after this CR merges — new `tsvector` columns should be covered by adding them to the parametrized case list.
- **No skew guard.** There is no automated revision-skew guard in the codebase (`orch/daemon/migration_rebase.py` is the CR-00021 down-revision rewriter, not a skew detector). The CR's stated goal is satisfied by a regression test that reproduces and pins the I-00075 / I-00076 failure — not by early detection. Building a runtime skew guard would be production code and is explicitly out of scope.
- **Out of scope**: fixing any data-layer bug the new tests find; adding a runtime revision-skew guard (production code); changing `test_db_identity_integration.py` or `test_work_items_functional_doc_fts.py`; porting the layer to sibling repos; adding a new canonical QV gate.
