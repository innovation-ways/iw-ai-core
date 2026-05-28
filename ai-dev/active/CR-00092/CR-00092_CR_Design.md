# CR-00092: Column-docs baseline scrub — add `doc=` to every `Column` in `orch/db/models.py`, delete the baseline file, and flip `check-column-docs` from warn-first to blocking

**Type**: Change Request
**Priority**: Medium
**Reason**: Pay down the 450-entry cleanup backlog frozen by CR-00085's baseline, and graduate the DB-column documentation gate from warn-first burn-in to a real blocking gate so `docs/IW_AI_Core_Database_Schema.md` stays honest from now on.
**Created**: 2026-05-28
**Status**: Draft

---

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.)

## ⛔ Migrations: agents generate, daemon applies

This CR adds NO migration. `doc=` on a SQLAlchemy Column is ORM-side metadata only — it does not change the SQL DDL, the schema, or any runtime value. The daemon will NOT need to apply anything.

## Description

Add a one-line `doc="..."` argument to every `Column(...)` declaration in `orch/db/models.py` that the CR-00085 scanner currently allows through `orch/db/column_docs_baseline.txt` (450 entries across 40 model classes); after the scrub is complete, regenerate the baseline (confirm empty) and delete the baseline file outright; flip the `check-column-docs` gate from warn-first (`|| true`) to blocking in `make quality` and in `.github/workflows/test-quality.yml`.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules.

Two project-specific rules dominate this CR:

- `DaemonEvent.metadata` is named `event_metadata` in Python because SQLAlchemy reserves `metadata` — the SQL column name (`metadata`) is what the scanner reports. The `doc=` argument lives on the `Column(...)` declaration regardless of the python attribute alias.
- The authoritative source for column meaning is `docs/IW_AI_Core_Database_Schema.md` (§ per-table DDL with column comments). This CR sources descriptions from there where possible and infers from column name/type/usage when the schema doc is silent — it does NOT edit the schema doc.

## Current Behavior

CR-00085 (merged 2026-05-24) shipped `scripts/check_db_column_docs.py`, which walks `Base.registry.mappers → mapper.local_table.columns` and reports every SQLAlchemy `Column` declaration that lacks a `doc=` argument. To land the scanner without first writing descriptions for ~450 columns, CR-00085 froze the existing set as a cleanup-backlog baseline at `orch/db/column_docs_baseline.txt` (header comment: "this is a *cleanup backlog*, not an accept-list"). The gate `make check-column-docs` is wired into:

- `make quality` — via `@$(MAKE) check-column-docs || true` (Makefile:101).
- `.github/workflows/test-quality.yml`'s `lint-typecheck` job — via `- run: make check-column-docs || true` (line 32).

Both surfaces are warn-only: a new undocumented column added today does NOT block the merge — it surfaces as a non-failing warning in the gate output. As a result, undocumented columns can (and do) accumulate.

The baseline currently contains **450 entries** across 40 model classes in `orch/db/models.py`. Top-heaviest classes: `WorkItem` (33), `StepRun` (28), `ProjectDoc` (21), `BatchItem` (21), `WorkflowStep` (20). No entries live in `orch/db/migrations/versions/**` (the scanner only walks live SQLAlchemy mappers; migration-file `Column()` calls are not introspected — out of scope here).

## Desired Behavior

After this CR ships:

- Every `Column(...)` declaration in `orch/db/models.py` carries a `doc="..."` argument with a one-line description (sourced from `docs/IW_AI_Core_Database_Schema.md` where available; inferred from column name/type/usage otherwise).
- `orch/db/column_docs_baseline.txt` is deleted from the tree.
- `scripts/check_db_column_docs.py --baseline /dev/null` exits 0 on `main`.
- `make quality` and `.github/workflows/test-quality.yml` invoke `make check-column-docs` without `|| true` — any future `Column(...)` added without a `doc=` argument blocks the gate.
- `docs/IW_AI_Core_Testing_Strategy.md` §5 records the gate as blocking; `ai-dev/work/TESTS_ENHANCEMENT.md` §8 row 4.5.followup is marked DONE with this CR's ID.

A future incremental follow-up CR may upgrade `check-column-docs` to a 9th canonical daemon QV gate (see Notes for the known trade-off); this CR explicitly does NOT add that gate.

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `orch/db/models.py` (40 model classes, ~2906 lines) | 0 columns with `doc=` | 450 columns gain `doc="..."` |
| `orch/db/column_docs_baseline.txt` | 450-entry cleanup backlog (file exists) | Deleted |
| `Makefile` `quality` target | `@$(MAKE) check-column-docs \|\| true` | `@$(MAKE) check-column-docs` (no `\|\| true`) |
| `.github/workflows/test-quality.yml` `lint-typecheck` job | `- run: make check-column-docs \|\| true` | `- run: make check-column-docs` |
| `docs/IW_AI_Core_Testing_Strategy.md` §5 (gate table) | Gate row marked warn-first / burn-in | Gate row marked blocking |
| `ai-dev/work/TESTS_ENHANCEMENT.md` §8 row 4.5.followup | TODO | DONE — CR-00092 (2026-05-28) |

### Breaking Changes

- None. `doc=` on a SQLAlchemy `Column` is ORM-side metadata — no schema change, no migration, no runtime behavior change, no API change, no UI change. The gate flip blocks NEW undocumented columns from landing in future CRs; existing code is by definition compliant after S04 finishes.

### Data Migration

- Not required. No schema change; no row touched.

## Implementation Plan

### Agents and Execution Order

> **Step-granularity rule**: each implementation step targets one cohesive concern. Per the operator's choice to split the scrub into per-class waves (smaller agent context windows, easier review), the scrub is partitioned across S01–S04 by model-class group; S04 also carries the gate flip + baseline removal + docs/tracker updates because they are mechanically coupled (the gate cannot be flipped until the baseline is empty).

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | database-impl | Wave 1 — heavyweights: `WorkItem` (33) + `StepRun` (28) + `ProjectDoc` (21) + `BatchItem` (21) = 103 columns | — |
| S02 | database-impl | Wave 2 — mid-size domain: `WorkflowStep` (20) + `DocGenerationJob` (19) + `CodeIndexJob` (18) + `TestRun` (17) + `Batch` (16) = 90 columns | — |
| S03 | database-impl | Wave 3 — OSS / chat / runtime: `OssFinding` (15) + `DocIndexJob` (15) + `ProjectOssJob` (13) + `PendingMigrationLog` (13) + `FixCycle` (12) + `OssScan` (11) + `ChatTab` (11) + `ChatSummarizationJob` (11) + `ChatConversation` (11) + `AgentRuntimeOption` (11) = 123 columns | — |
| S04 | database-impl | Wave 4 — remainder: all 21 small classes (`WorkItemEvidence`, `KeepAliveRun`, `Project`, `OssToolRun`, `OssFindingDetail`, `DaemonEvent`, `BatchOverlapIgnore`, `ProjectDocVersion`, `ChatMessage`, `TestHealthSnapshot`, `QvBaseline`, `MergeAutoVerdict`, `MigrationLock`, `KeepAliveSlot`, `IdAllocation`, `DocSectionGuide`, `AutoMergeProjectConfig`, `KeepAliveConfig`, `IwCoreInstance`, `DocTypeGuide`, `DocInstanceGuide`, `IdSequence`) = 134 columns + delete `orch/db/column_docs_baseline.txt` + flip Makefile `\|\| true` + flip GH workflow `\|\| true` + update strategy doc §5 + update tracker §8 row + add tracker §11 changelog entry | — |
| S05 | code-review-impl | Per-agent review of S01–S04 | — |
| S06 | code-review-final-impl | Global cross-step review covering all ACs | — |
| S07..S14 | QV Gates | lint, assertions, format, typecheck, unit-tests, integration-tests, diff-coverage, security-secrets | — |
| S15 | self-assess-impl | Self-assessment via iw-item-analyze | — |

Agent slug for the scrub steps is `database-impl` — every change touches `orch/db/models.py`. `tests-impl` is not needed: the scanner's library-form tests (`tests/orch/db/test_column_docs.py`, shipped by CR-00085) already prove the gate works; this CR only changes inputs to the scanner, not the scanner itself.

### Database Changes

- **New tables**: None.
- **Modified tables**: None (no schema change).
- **Migration notes**: No migration file is created or modified. `doc=` is SQLAlchemy ORM metadata and does not appear in generated DDL.

### API Changes

- **New endpoints**: None.
- **Modified endpoints**: None.
- **Removed endpoints**: None.

### Frontend Changes

- **New components**: None.
- **Modified components**: None.
- **Removed components**: None.

## File Manifest

All files for this work item live under `ai-dev/active/CR-00092/`:

| File | Type | Purpose |
|------|------|---------|
| `CR-00092_CR_Design.md` | Design | This document |
| `CR-00092_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/CR-00092_S01_Database_prompt.md` | Prompt | S01 wave 1 scrub instructions (4 heavyweight classes) |
| `prompts/CR-00092_S02_Database_prompt.md` | Prompt | S02 wave 2 scrub instructions (5 mid-size classes) |
| `prompts/CR-00092_S03_Database_prompt.md` | Prompt | S03 wave 3 scrub instructions (10 OSS/chat/runtime classes) |
| `prompts/CR-00092_S04_Database_prompt.md` | Prompt | S04 wave 4 scrub instructions (21 remainder classes) + baseline removal + gate flip + docs/tracker updates |
| `prompts/CR-00092_S05_CodeReview_prompt.md` | Prompt | Per-agent review |
| `prompts/CR-00092_S06_CodeReview_Final_prompt.md` | Prompt | Global cross-step review |
| `prompts/CR-00092_S15_SelfAssess_prompt.md` | Prompt | Self-assessment |

Reports are created during execution in `ai-dev/work/CR-00092/reports/`.

## Acceptance Criteria

### AC1: Every column in `orch/db/models.py` has `doc="..."`

```
Given the working tree at HEAD of this CR
When `uv run python scripts/check_db_column_docs.py --baseline /dev/null` is run
Then it exits 0 with no violations reported
```

### AC2: The baseline file is removed

```
Given the working tree at HEAD of this CR
When `git ls-files orch/db/column_docs_baseline.txt` is run
Then it returns nothing (the file no longer exists in the repo)
```

### AC3: `make check-column-docs` is blocking in `make quality`

```
Given a working tree where a new undocumented Column is added to any model in orch/db/models.py
When `make quality` is run
Then it exits non-zero with a check-column-docs violation in the output
```

### AC4: `make check-column-docs` is blocking in the GH workflow

```
Given .github/workflows/test-quality.yml at HEAD of this CR
When the file is grepped for "check-column-docs"
Then the matching line does NOT contain "|| true"
```

### AC5: `make quality` exits 0 on the unchanged tree

```
Given the working tree at HEAD of this CR (no synthetic regression introduced)
When `make quality` is run
Then it exits 0 (every existing column is documented; the scanner finds zero violations)
```

### AC6: Docs and tracker reflect the new gate status

```
Given the working tree at HEAD of this CR
When docs/IW_AI_Core_Testing_Strategy.md §5 (gate table) and ai-dev/work/TESTS_ENHANCEMENT.md §8 row 4.5.followup are read
Then the strategy doc row for check-column-docs is marked blocking AND the tracker row is marked DONE with this CR's ID + 2026-05-28
```

### AC7: Scope discipline — no production or schema-doc edits

```
Given the working tree at HEAD of this CR
When `git diff main...HEAD --name-only` is run
Then the only files reported are those in the File Manifest's Impacted Paths section
AND docs/IW_AI_Core_Database_Schema.md is NOT in the list
AND no file under orch/db/migrations/versions/ is in the list
AND no file outside orch/db/models.py, the baseline file, Makefile, the GH workflow, the strategy doc, or the tracker is in the list (apart from ai-dev/active/CR-00092/** and ai-dev/work/CR-00092/**, which are implicitly allowed)
```

### AC8: Every test can fail — deliberate-break demonstration

```
Given the working tree at HEAD of this CR
When a single `doc=` argument is temporarily removed from any one column declaration in orch/db/models.py
Then `make check-column-docs` exits non-zero with that column's FQN in the violation output
AND restoring the `doc=` argument makes `make check-column-docs` exit 0 again
(Run in S04's report as evidence; reverted before completing the step.)
```

## Rollback Plan

- **Database**: N/A (no schema change, no migration).
- **Code**: Revert the merge commit. The previous state (`doc=`-less columns + 450-entry baseline + warn-first gate) is fully restored by a single revert; no shim, no feature flag.
- **Data**: No data loss possible — this CR touches no rows.

## Dependencies

- **Depends on**: CR-00085 (scanner + baseline + warn-first gate, merged 2026-05-24). The follow-up requires the scanner to exist.
- **Blocks**: None directly. Future CRs that add new columns to `orch/db/models.py` will be subject to the blocking gate, but that is the intended outcome, not a blocking dependency.

## Impacted Paths

- `orch/db/models.py`
- `orch/db/column_docs_baseline.txt`
- `Makefile`
- `.github/workflows/test-quality.yml`
- `docs/IW_AI_Core_Testing_Strategy.md`
- `ai-dev/work/TESTS_ENHANCEMENT.md`

## TDD Approach

This CR adds NO new behavioural tests — the scanner's library-form tests already exist (`tests/orch/db/test_column_docs.py`, shipped by CR-00085) and stay unchanged. The scrub is a content-only change to existing `Column(...)` declarations; the gate flip is a config-only change.

- **Unit tests**: None added. The existing `tests/orch/db/test_column_docs.py` covers the empty-baseline RED path; this CR's S04 simply causes that path to be exercised against the live tree.
- **Integration tests**: None added.
- **Updated tests**: None.

The TDD-equivalent for this CR is the AC8 deliberate-break-then-revert demonstration recorded in S04's report. In the Subagent Result Contract, every implementation step (S01–S04) uses `"tdd_red_evidence": "n/a — content-only doc= additions on existing Column declarations; no new behavioural tests"`.

## Notes

- **Known trade-off (gate surface)**: per operator's choice, `check-column-docs` stays folded into `make quality` rather than becoming a canonical daemon QV gate. The daemon's per-item merge gate runs `make lint`, NOT `make quality` — so a future CR that adds an undocumented column will pass the daemon merge gate but fail the post-merge GH `test-quality.yml` workflow. The GH workflow runs on both `pull_request` and `push` to `main`, so the failure surfaces loudly, but the merge has already happened by then. If undocumented-column slip-through becomes a real issue post-merge, a tiny follow-up CR can promote `check-column-docs` to a 9th canonical daemon QV gate (after `security-secrets`) — that change would touch `skills/iw-workflow/SKILL.md` and the design templates per the project's sync rules.
- **Sibling structural pattern**: CR-00081 (the assertion-scanner baseline scrub) is the closest precedent. CR-00081 strengthened 78 of CR-00046's baseline entries in a single CR; this CR scrubs 450 entries in four waves to keep each agent's context window manageable.
- **No skill sync**: this CR does not change any agent-facing rule (the `doc=` requirement on new columns was already in CR-00085's testing-skill section). `iw sync-skills` is NOT invoked.
- **Wave boundaries are mechanical**: each wave is "the next N classes in baseline-entry-count order, stopping when the wave is ~100 columns". The boundaries are listed in the Implementation Plan table; they are NOT renegotiated mid-CR.
- **Description sourcing rule (for S01–S04)**: when `docs/IW_AI_Core_Database_Schema.md` § for the target table contains a column description, use that verbatim (trimmed to one line). When the schema doc is silent on the column, write a one-line description inferred from (a) the column name, (b) the SQLAlchemy type and constraints, (c) usage of the python attribute in `orch/` and `dashboard/`. Do NOT edit the schema doc; do NOT write multi-line descriptions; do NOT add `# why` comments above column declarations.
