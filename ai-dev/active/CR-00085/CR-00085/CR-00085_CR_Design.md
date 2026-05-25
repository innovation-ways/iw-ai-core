# CR-00085: DB-column documentation gate — every SQLAlchemy column on every model must have a description; CI check fails on undocumented columns

**Type**: Change Request
**Priority**: Medium
**Reason**: Keep `docs/IW_AI_Core_Database_Schema.md` honest — schema doc drifts whenever a migration adds a column and nobody updates the doc. A small CI gate that fails the build when a new SQLAlchemy column lacks a description prevents drift at the source (model declaration), mirroring InnoForge's analogue. Tracker item: TESTS_ENHANCEMENT.md Phase 4 row 4.5.
**Created**: 2026-05-24
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt. This CR adds no Docker usage; the new gate is pure-Python AST/introspection.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. **This item adds no migrations.** The scanner inspects existing SQLAlchemy model classes — it does not change the schema. Migration lock is N/A.

## Description

Introduce a "DB-column documentation gate" — a static introspection script (`scripts/check_db_column_docs.py`) that walks every SQLAlchemy `Column` declaration on every ORM model and fails the build when a column lacks a description (priority: SQLAlchemy `Column(..., doc="...")`, falling back to an entry in an allowlist baseline). The gate ships with a frozen baseline of today's undocumented columns (`orch/db/column_docs_baseline.txt`) so it fires only on **new** violations — identical structural pattern to CR-00046's assertion-scanner kit (`scripts/check_test_assertions.py` + `tests/assertion_free_baseline.txt`). Plumbed into `make check-column-docs`, folded into `make quality` (warn-first via `|| true` during burn-in), and surfaced in `.github/workflows/test-quality.yml`'s `lint-typecheck` job.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules — especially:

- The critical rule that `DaemonEvent.metadata` is renamed to `event_metadata` in Python because SQLAlchemy reserves the `metadata` attribute name on the declarative base. The scanner must walk model attributes (or use `Mapper.columns`) rather than introspect via the python attribute name, otherwise it will both miss the renamed column and trip over `Base.metadata`.
- The full list of model files under `orch/` — confirmed primary file is `orch/db/models.py`; the scanner must also pick up any other module that defines `Mapper`-bound classes (use a `grep -l 'from sqlalchemy' orch/` sweep when discovering candidate files, but the SQLAlchemy `registry` / `Base.registry.mappers` introspection is the **authoritative** source — never trust grep alone).

## Current Behavior

- `orch/db/models.py` defines roughly 30+ ORM classes (WorkItem, Batch, BatchItem, StepRun, DocGenerationJob, CodeIndexJob, DaemonEvent, Project, …) and several hundred individual `Column(...)` declarations. The vast majority have no `doc=` kwarg.
- `docs/IW_AI_Core_Database_Schema.md` is hand-maintained narrative documentation that lists tables, columns, and their meaning. There is no mechanical link between the model declarations and this doc — a developer can add a column in a migration + model declaration and forget to update the schema doc, and nothing flags it. Cumulative drift accumulates silently over time.
- No gate exists today to detect undocumented columns. `make quality` runs `lint + format + typecheck + test-assertions + dead-code + dep-check`; no column-doc check is in the chain. `.github/workflows/test-quality.yml`'s `lint-typecheck` job runs `make lint`, `make test-assertions`, `make format-check`, `make typecheck`, `make dead-code`, and `make dep-check` — no column-doc step.

## Desired Behavior

- A new `scripts/check_db_column_docs.py` script introspects every column on every SQLAlchemy mapper reachable from `orch.db.models.Base` (and any other declared base if present). For each column it checks, in priority order:
  1. The column declaration carries a non-empty `doc=` argument (`Column(..., doc="...")`).
  2. The column's fully-qualified name (`models.WorkItem.id`) appears in `orch/db/column_docs_baseline.txt` — the cleanup-backlog allowlist.
- The scanner emits one violation line per undocumented column not in the baseline. Exit 0 if zero new violations; exit 1 otherwise. Provides `--write-baseline <path>` for the initial seeding and any future intentional rebaseline.
- `make check-column-docs` runs the scanner with the committed baseline. It is wired into `make quality` via `|| true` (warn-first burn-in policy — a follow-up CR flips it blocking once the baseline is small enough that the failure surface is meaningful).
- `.github/workflows/test-quality.yml`'s `lint-typecheck` job gets one new step: `make check-column-docs || true` (warn-first, same as `make dead-code` and `make dep-check` today).
- A library-form test (`tests/orch/db/test_column_docs.py`) imports the scanner module and asserts: (a) RED — running it with an empty baseline reports at least one violation against the current `orch/db/models.py` (proves the scanner works); (b) GREEN — running it with the committed `orch/db/column_docs_baseline.txt` reports zero new violations; (c) the scanner correctly handles the `DaemonEvent.event_metadata` / `DaemonEvent.__table__.c.metadata` rename and does not crash on `Base.metadata`.
- The schema doc itself (`docs/IW_AI_Core_Database_Schema.md`) is **NOT** edited in this CR — the doc is the **outcome** the gate enforces over time as new columns get documented, not a deliverable of the gate itself.

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `scripts/` directory | Has `check_test_assertions.py`, `check_templates.py`, `arch_check.py` | Adds `check_db_column_docs.py` (mirroring the assertion-scanner shape) |
| `orch/db/` | Has `models.py`, `session.py`, `identity.py`, `safe_migrate.py`, `live_db_guard.py` | Adds `column_docs_baseline.txt` — cleanup backlog, identical pattern to `tests/assertion_free_baseline.txt` |
| `tests/orch/db/` | Does not exist as a test package | Created with `__init__.py` + `test_column_docs.py` |
| `Makefile` `quality` target | `lint + format-check + typecheck + test-assertions + dead-code + dep-check` | Adds `check-column-docs` (warn-first via `|| true` during burn-in) |
| `.github/workflows/test-quality.yml` `lint-typecheck` job | Six `run:` steps (lint, test-assertions, format-check, typecheck, dead-code, dep-check) | Adds one warn-first step: `make check-column-docs \|\| true` |
| `docs/IW_AI_Core_Testing_Strategy.md` §5 (Quality gates) | Lists 20+ gates | Adds one row: "DB-column documentation gate" → `make check-column-docs` |
| `docs/IW_AI_Core_Testing_Strategy.md` §9 (Known gaps & roadmap) | Phase 4 row 4.5 is ❌ TODO | Phase 4 row 4.5 → ✅ |
| `skills/iw-ai-core-testing/SKILL.md` + `.claude/skills/iw-ai-core-testing/SKILL.md` | No column-doc section | New section documenting the gate, the `doc=` requirement on new columns, and the "scrub the baseline incrementally; do not silence by adding to it" pattern |
| `ai-dev/work/TESTS_ENHANCEMENT.md` §8 row 4.5 | TODO | ✅ DONE with CR-00085 + date + new follow-up tracker row for the incremental scrub |

### Breaking Changes

- None. The gate is **warn-first** for the entire burn-in period (`|| true` in both `make quality` and the GH workflow). Existing developer workflow is unaffected — the gate only emits informational output until a follow-up CR flips it blocking.
- No model declarations are edited. No public API changes. No CLI changes.

### Data Migration

- None. No database schema change. No data is read or modified.
- Reversibility: trivial — revert the commit; the scanner is a standalone script with no runtime hooks.

## Implementation Plan

### Agents and Execution Order

> **Step-granularity rule**: each implementation step targets one cohesive concern (one module or closely-related file group). This CR has two implementation steps — S01 introduces the scanner + baseline + RED-first test (one cohesive concern: the new gate's machinery), and S02 wires it into Make/CI/docs/skill/tracker (one cohesive concern: integrating the gate's surfaces). Splitting them this way matches the canonical "scanner + baseline + gate" three-piece kit pattern (CR-00046, CR-00072, CR-00075).

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | backend-impl | Scanner script + baseline file + RED-first library-form test | — |
| S02 | backend-impl | Makefile target + `make quality` integration + GH workflow step + strategy doc updates (§5 + §9) + skill section (master + `.claude/` copy) + tracker §8 + new follow-up row | — |
| S03 | code-review-impl | Per-agent review of S01 | — |
| S04 | code-review-final-impl | Cross-step / global review of S01+S02 | — |
| S05..S12 | qv-gate | The canonical 8 QV gates: lint, assertions, format, typecheck, unit-tests, integration-tests, diff-coverage, security-secrets | — |
| S13 | self-assess-impl | SelfAssess (project flag `self_assess = true`) | — |

Agent slugs in use: `backend-impl`, `code-review-impl`, `code-review-final-impl`, `qv-gate`, `self-assess-impl` (canonical names from `skills/iw-workflow/SKILL.md`).

### Database Changes

- **New tables**: None.
- **Modified tables**: None.
- **Migration notes**: None — no migration.

### API Changes

- **New endpoints**: None.
- **Modified endpoints**: None.
- **Removed endpoints**: None.

### Frontend Changes

- **New components**: None.
- **Modified components**: None.
- **Removed components**: None.

## File Manifest

All files for this work item live under `ai-dev/active/CR-00085/`:

| File | Type | Purpose |
|------|------|---------|
| `CR-00085_CR_Design.md` | Design | This document |
| `CR-00085_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/CR-00085_S01_Backend_prompt.md` | Prompt | S01 — scanner + baseline + RED-first test |
| `prompts/CR-00085_S02_Backend_prompt.md` | Prompt | S02 — Makefile + CI + docs + skill + tracker |
| `prompts/CR-00085_S03_CodeReview_prompt.md` | Prompt | S03 — review S01 |
| `prompts/CR-00085_S04_CodeReview_Final_prompt.md` | Prompt | S04 — cross-step global review |
| `prompts/CR-00085_S13_SelfAssess_prompt.md` | Prompt | S13 — self-assessment via `iw-item-analyze` |

QV gate steps (S05–S12) carry `gate` + `command` fields in the manifest and have no per-step prompt file (executor reads the canonical contract from `iw-workflow`).

Reports are created during execution in `ai-dev/work/CR-00085/reports/`.

## Acceptance Criteria

### AC1: Scanner detects undocumented columns

```
Given orch/db/models.py contains columns without doc= arguments
When `uv run python scripts/check_db_column_docs.py --baseline /dev/null`
Then exit code is 1 (violations present)
And stdout lists at least one violation in the form `<module>.<Class>.<column_name>: missing description`
```

### AC2: Scanner handles SQLAlchemy reserved-name rename

```
Given orch/db/models.py defines DaemonEvent.event_metadata (the python attribute renamed from the reserved `metadata`)
When the scanner walks all mappers reachable from Base
Then it considers the SQL column name (`metadata`) — not the python attribute name (`event_metadata`) — when emitting violations
And it does NOT crash on Base.metadata (the SQLAlchemy MetaData object on the declarative base)
And the scanner's full run produces no Python exception
```

### AC3: Baseline freezes today's debt

```
Given orch/db/column_docs_baseline.txt is committed listing every undocumented column on the current main
When `make check-column-docs` is run on an unchanged tree
Then exit code is 0
And the scanner reports zero NEW violations beyond the baseline
And the exact baseline entry count is recorded in the S01 report's evidence section
```

### AC4: Baseline rejects new violations

```
Given the baseline is frozen at today's undocumented columns
When a hypothetical new column without doc= is added to any mapped class
Then `make check-column-docs` exits 1
And the new column's FQN appears in the violations output
```

### AC5: Makefile + CI integration (warn-first)

```
Given S02 has wired `make check-column-docs` into `make quality` via `|| true` and into `.github/workflows/test-quality.yml`'s `lint-typecheck` job via `|| true`
When `make quality` is run on an unchanged tree
Then it exits 0 (warn-first burn-in policy honoured)
And when the same is run with an intentionally added undocumented column, `make quality` still exits 0 (warn-first) but stdout shows the violation line(s)
```

### AC6: RED-first test pins the contract

```
Given `tests/orch/db/test_column_docs.py` imports the scanner's library entrypoint
When `uv run pytest tests/orch/db/test_column_docs.py -v` is run
Then all tests pass
And the suite includes at least:
  - a RED test that passes an empty baseline and asserts violations > 0
  - a GREEN test that passes the committed baseline path and asserts violations == 0
  - a regression test that the scanner does not crash on `DaemonEvent.event_metadata` / `Base.metadata`
```

### AC7: Docs + skill + tracker updates

```
Given S02 updates the testing-strategy doc, skill, and tracker
When the merge lands
Then docs/IW_AI_Core_Testing_Strategy.md §5 has a new row for "DB-column documentation gate" → `make check-column-docs`
And docs/IW_AI_Core_Testing_Strategy.md §9 row 4.5 is ✅
And skills/iw-ai-core-testing/SKILL.md (and the synced .claude/ copy) gains a section explaining the doc= requirement on new columns AND the baseline-scrub-incrementally pattern (analogous to the assertion-scanner section)
And ai-dev/work/TESTS_ENHANCEMENT.md §8 row 4.5 marks ✅ with CR-00085 + date and a new tracker row (e.g. `CR-00085-followup-column-docs-scrub`) records the incremental cleanup follow-up
```

### AC8: Scope discipline

```
Given the allowed_paths list in workflow-manifest.json
When git diff is taken against main at merge time
Then no files outside the allowed_paths list are modified
And specifically `orch/db/models.py` is NOT edited (column-doc scrub is the follow-up CR's job)
And no Alembic migration files are added or modified
```

## Rollback Plan

- **Database**: N/A — no migration, no schema change.
- **Code**: Revert the merge commit. The scanner is a standalone script with no import-side effects on production code paths; reverting cleanly removes it without leaving runtime residue. The baseline file disappears with the revert.
- **Data**: No data loss possible — the gate is read-only static introspection.

## Dependencies

- **Depends on**: None. Leaf CR — independent of CR-00080, CR-00081, I-00109, I-00110, I-00111. No coupling to migration-lock holders.
- **Blocks**: None. The follow-up incremental scrub CR (filed as a tracker row, not allocated yet) consumes this CR's baseline file but is out of scope here.

## Impacted Paths

The cross-batch launch-time gate uses this list to detect overlap with in-flight items (F-00076). The merge-time scope gate enforces the allow-list at commit.

- `scripts/check_db_column_docs.py`
- `orch/db/column_docs_baseline.txt`
- `tests/orch/db/__init__.py`
- `tests/orch/db/test_column_docs.py`
- `Makefile`
- `.github/workflows/test-quality.yml`
- `docs/IW_AI_Core_Testing_Strategy.md`
- `skills/iw-ai-core-testing/**`
- `.claude/skills/iw-ai-core-testing/**`
- `ai-dev/work/TESTS_ENHANCEMENT.md`

(Files explicitly out of scope — i.e. that the merge-time scope gate must reject — are listed in the `## Notes` section below to keep this section parser-clean.)

## TDD Approach

- **Unit/integration tests** (`tests/orch/db/test_column_docs.py`):
  - **RED test** — call the scanner's library entrypoint with an empty baseline string against the current models module; assert `len(violations) > 0`. This proves the scanner discovers real undocumented columns on `orch/db/models.py`. Record the exact violation count in the S01 report's `tdd_red_evidence`.
  - **GREEN test** — call the scanner with the committed baseline path; assert `len(new_violations) == 0`. This proves the baseline freezes today's debt.
  - **Reserved-name regression test** — assert the scanner walks `DaemonEvent`'s mapper and reports the SQL column name (`metadata`) when undocumented, and does not crash on `Base.metadata`.
  - **Add-a-new-column regression test** — synthesise a minimal model class in the test with a column lacking `doc=`, register it on a temporary `MetaData` or pass an explicit mapper list to the scanner, assert the scanner emits a violation for it. (Alternative: parametrize the scanner to accept an iterable of mappers rather than only `Base.registry.mappers` so the test can inject a synthetic mapper without polluting the real `Base`.)
  - **Baseline-write smoke test** — call the scanner with `--write-baseline <tmp_path>`, assert the file exists and parses back into the same violation set.
- **Updated tests**: None — this CR creates a new test file under a new test package. No existing test needs modification.
- **Coverage expectations**: The scanner's branches should clear the diff-coverage gate's ≈90% threshold on the new lines.

## Notes

**Explicitly NOT in scope** — the merge-time scope gate must reject any diff touching these files:

- `orch/db/models.py` — that is the follow-up scrub CR's responsibility, not this CR's.
- `orch/db/migrations/versions/**` — migrations carry their own column descriptions in `op.add_column` calls, but those are not the durable source the gate enforces; out of scope.
- `docs/IW_AI_Core_Database_Schema.md` — the doc the gate exists to keep honest, but editing it is the **outcome** the gate enforces over time, not a deliverable of this CR.

**Design risk — scanner overreach.** The scanner must walk SQLAlchemy mappers via the declarative registry, **not** by reflecting on the Python class `__dict__`. Reflecting on `__dict__` will trip over `Base.metadata`, miss the `event_metadata` rename, and produce noisy false positives on inherited columns. The canonical entrypoint is `Base.registry.mappers` → iterate `mapper.local_table.columns` (or `mapper.columns` if you want polymorphic-inherited columns included). The S01 prompt locks this approach in.

**Burn-in policy** — the gate ships warn-first (`|| true`) for the same reason CR-00050 / CR-00072 burn-in'd Semgrep / schemathesis: the baseline is large (expected dozens to hundreds), and we want the gate visible in `make quality` and the GH workflow output **before** anyone has done the scrub work. A follow-up CR (tracked as `CR-00085-followup-column-docs-scrub`) flips the `|| true` to blocking once the baseline is small enough that the failure surface is meaningful — same playbook as `P1-CR-D-followup-semgrep-block` and `P2-CR-A-followup-mutation-block`.

**Why no doc-schema edit here.** `docs/IW_AI_Core_Database_Schema.md` is the doc the gate exists to keep honest, but editing it is the **outcome** the gate enforces over time, not a deliverable of this CR. Including it in scope would conflate the cleanup work (a separate, larger CR) with the gate-introduction work (this CR). Mirrors how CR-00046 introduced the assertion scanner without strengthening any individual test — that work landed serially in CR-00081 weeks later.

**Comparison to CR-00046's scanner kit** — this CR is structurally identical:

| Concern | CR-00046 (assertion scanner) | CR-00085 (column-doc scanner) |
|--------|------------------------------|-------------------------------|
| Scanner script | `scripts/check_test_assertions.py` | `scripts/check_db_column_docs.py` |
| Baseline file | `tests/assertion_free_baseline.txt` | `orch/db/column_docs_baseline.txt` |
| Make target | `make test-assertions` | `make check-column-docs` |
| `make quality` integration | Hard gate (already in the chain) | Warn-first (`|| true`) during burn-in |
| GH workflow | Step in `lint-typecheck` job | Step in `lint-typecheck` job, warn-first |
| RED-first test | n/a (legacy item) | `tests/orch/db/test_column_docs.py` |
| Local opt-out | `# noqa: assertion-scanner` on `def` | Baseline allowlist entry |
| Follow-up scrub | CR-00081 (78 entries strengthened) | `CR-00085-followup-column-docs-scrub` (filed but not allocated) |

Mirroring this pattern lets reviewers reason by analogy and reduces the cognitive load on agents implementing the steps.
