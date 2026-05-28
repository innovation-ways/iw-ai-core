# CR-00093: Register all test-enhancement Makefile suites as launchable dashboard cards

**Type**: Change Request
**Priority**: Medium
**Reason**: Close the dashboard launcher gap left by Phases 0–4 of the test-enhancement initiative. Every new suite (smoke, e2e, properties, perf, chaos, visual, contract-fuzz, security-module, mutation, …) was shipped as a Makefile target and wired into CI but never registered with the dashboard's Tests / Quality launcher — so the operator can't trigger them from the UI.
**Created**: 2026-05-28
**Status**: Draft

---

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.)

## ⛔ Migrations: agents generate, daemon applies

This CR adds NO migration. `project.config` is a JSONB column populated by `project_registry.py` on SIGHUP — the data shape doesn't change, only the contents of the JSONB blob do.

## Description

Extend `.iw-orch.json`'s `test_config.categories` block with 21 new test-suite cards (smoke, properties, properties-deep, quarantine, flake-detect, cli-contract, isolation, security-module, data-layer, route-sweep, contract-fuzz, e2e-smoke, e2e, perf and three sub-targets, daemon-chaos-smoke, daemon-chaos-full, visual-regression, test-assertions) and the `quality_config.categories` block with 9 new quality-gate cards (check-column-docs, security-secrets, security-sast, security-deps, diff-coverage, mutation-check, mutation-audit, dead-code, dep-check). After `./ai-core.sh daemon reload` (SIGHUP), the daemon's `project_registry.py` syncs the new entries into `project.config` JSONB and the existing dashboard route handlers + `build_category_cards()` helper render them as cards under their group sections — with zero Python changes.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Key facts that shape this CR:

- The Tests page (`dashboard/routers/tests.py:_get_test_config()`) and Quality page (`dashboard/routers/quality.py`) read `project.config['test_config']` / `quality_config` JSONB from the `Project` row.
- `project.config` is populated by `orch/daemon/project_registry.py:_read_iw_orch_json(repo_root)`, which reads the project's `.iw-orch.json` at the repo root. `projects.toml` is the daemon-side registry of WHICH projects exist; per-project config (test categories, quality categories, browser_verification env, alembic settings, etc.) lives in `.iw-orch.json`.
- The dashboard's `build_category_cards()` helper (`dashboard/routers/_run_helpers.py`) handles arbitrary `group` strings and `bundle: bool` / `e2e_stack: bool` flags — no Python change is needed to render new categories.
- `dashboard/routers/tests.py:_find_running_e2e_stack_test()` enforces that only one `e2e_stack=true` category may run at a time (shared docker ports). Confirmed implementation iterates all categories with `e2e_stack=true` — it scales naturally to ≥2 such categories.

## Current Behavior

The dashboard's Tests page shows three cards: `unit`, `integration`, `all`. The Quality page shows four: `lint`, `format`, `typecheck`, `all-quality`. The operator who wants to run any other suite (smoke, e2e, properties, perf, chaos, visual, mutation, contract-fuzz, security-module, data-layer, cli-contract, isolation, route-sweep, quarantine, flake-detect, check-column-docs, security-secrets, security-sast, security-deps, diff-coverage, dead-code, dep-check, test-assertions, mutation-audit, daemon-chaos-full) MUST shell into the project root and invoke the Makefile target directly. The dashboard offers no visibility into these suites' existence — they appear neither as cards nor in the live-run log nor in the Allure-results table. CI runs them on PR / push / nightly, but operators can't trigger an ad-hoc run from the UI, can't see prior `TestRun` rows for them in the Runs tab, and can't pull up Allure HTML reports for the ones that produce Allure output.

This is purely a registry gap. The Makefile targets all exist, the route handlers already iterate `categories` generically, and the underlying `TestRun` / `launch_test_run` machinery is agnostic to the category name (the `command` field is shelled out verbatim).

## Desired Behavior

After this CR + daemon SIGHUP:

- The dashboard's Tests page shows the existing 3 cards plus 21 new ones, grouped under `backend` (the heaviest group: smoke, properties, properties-deep, quarantine, flake-detect, cli-contract, isolation, security-module, data-layer, route-sweep, contract-fuzz), `e2e` (e2e-smoke, e2e), `perf` (perf, perf-daemon, perf-rag, perf-routes), `chaos` (daemon-chaos-smoke, daemon-chaos-full), `visual` (visual-regression), and `quality` (test-assertions).
- The dashboard's Quality page shows the existing 4 cards plus 9 new ones, grouped under `docs` (check-column-docs), `security` (security-secrets, security-sast, security-deps), `coverage` (diff-coverage, mutation-check, mutation-audit), and `hygiene` (dead-code, dep-check).
- `e2e` and `e2e-smoke` cards carry `e2e_stack: true` so launching one while the other is running surfaces a "stack already in use" warning instead of colliding on docker ports.
- The two heaviest suites (`mutation-audit` and `daemon-chaos-full`) carry a prose warning in their `description` field noting expected wall-clock — but stay launchable per operator choice ("maximum transparency").
- Clicking any new card produces a `TestRun` row (`run_type='test'` or `'quality'`) with the corresponding Makefile command, identical to today's `unit` / `lint` / etc. cards.
- `ai-dev/work/TESTS_ENHANCEMENT.md` §8 gains a row recording "dashboard launcher surface = DONE" so the tracker reflects the closed gap.

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `.iw-orch.json` `test_config.categories` | 3 entries (unit, integration, all) | 24 entries (3 existing + 21 new) |
| `.iw-orch.json` `quality_config.categories` | 4 entries (lint, format, typecheck, all-quality) | 13 entries (4 existing + 9 new) |
| `project.config['test_config']` JSONB (live DB row for `iw-ai-core`) | mirrors current 3-entry block | mirrors new 24-entry block after SIGHUP |
| `project.config['quality_config']` JSONB | mirrors current 4-entry block | mirrors new 13-entry block after SIGHUP |
| Tests page (Launch tab) | 3 cards under 2 groups (backend, suites) | 24 cards under 6 groups (backend, suites, e2e, perf, chaos, visual, quality) |
| Quality page (Launch tab) | 4 cards under 2 groups (style, suites) | 13 cards under 6 groups (style, suites, docs, security, coverage, hygiene) |
| `ai-dev/work/TESTS_ENHANCEMENT.md` §8 | No row tracking the launcher gap | New row recording dashboard surface = DONE (CR-00093) |

### Breaking Changes

- None. Existing 7 cards stay byte-identical. The `Project` row's `config` JSONB shape is unchanged (still a TOML-flavoured dict under `test_config.categories` / `quality_config.categories`); only the contents grow.

### Data Migration

- Not required. `project_registry.py` overwrites the JSONB blob on SIGHUP; no schema change, no row touched besides the single `Project` row for `iw-ai-core`.

## Implementation Plan

### Agents and Execution Order

> **Step-granularity rule**: each step targets one cohesive concern. This CR is small enough that the entire registry edit fits in one S01 step. Reviews / browser verification / QV gates are conventional.

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | backend-impl | Edit `.iw-orch.json` — extend `test_config.categories` with 21 new entries + `quality_config.categories` with 9 new entries; update `ai-dev/work/TESTS_ENHANCEMENT.md` §8 with a new tracker row. Sanity-check by invoking the registry-sync code path against a copy and confirming the parsed dict matches expectations. | — |
| S02 | code-review-impl | Per-agent review (JSON shape conformance, all 30 new categories present, every Makefile target referenced exists, `e2e_stack=true` on e2e + e2e-smoke only, `bundle=true` only on existing `all` / `all-quality`, heavy-suite warnings in description fields) | — |
| S03 | code-review-final-impl | Global cross-step review against AC1–AC7 | — |
| S04 | qv-gate | lint (`make lint` — covers `scripts/check_templates.py` which won't be hit, but the gate runs anyway) | — |
| S05 | qv-gate | format (`make format-check`) | — |
| S06 | qv-gate | typecheck (`make type-check`) | — |
| S07 | qv-gate | unit-tests (`make test-unit`) | — |
| S08 | qv-gate | integration-tests (`make test-integration` — includes the dashboard route-contract sweep from CR-00072 which covers the Tests / Quality pages) | — |
| S09 | qv-gate | diff-coverage (`make diff-coverage`) | — |
| S10 | qv-gate | security-secrets (`make security-secrets`) | — |
| S11 | qv-browser | Browser verification — render-only (count new cards, click one, confirm `TestRun` row appears) | — |
| S12 | self-assess-impl | Self-assessment via iw-item-analyze | — |

No `assertions` QV gate — the CR adds no test code. No `migration-check` — no migration.

### Database Changes

- **New tables**: None.
- **Modified tables**: `projects.config` JSONB on the `iw-ai-core` row, populated by daemon SIGHUP from the edited `.iw-orch.json`. No DDL change.
- **Migration notes**: No alembic migration file.

### API Changes

- **New endpoints**: None.
- **Modified endpoints**: None. The existing `POST /project/{id}/api/tests/launch/{category}` and equivalent quality endpoint already accept arbitrary category names; the new categories will hit those endpoints unchanged.
- **Removed endpoints**: None.

### Frontend Changes

- **New components**: None. The existing `tests.html` / `quality.html` pages + `tests_launch.html` / `quality_launch.html` fragments render all categories via `build_category_cards()`.
- **Modified components**: None.
- **Removed components**: None.

## File Manifest

All files for this work item live under `ai-dev/active/CR-00093/`:

| File | Type | Purpose |
|------|------|---------|
| `CR-00093_CR_Design.md` | Design | This document |
| `CR-00093_Functional.md` | Design | Human-facing summary |
| `workflow-manifest.json` | Manifest | Step definitions |
| `prompts/CR-00093_S01_Backend_prompt.md` | Prompt | Edit .iw-orch.json + tracker |
| `prompts/CR-00093_S02_CodeReview_prompt.md` | Prompt | Per-agent review |
| `prompts/CR-00093_S03_CodeReview_Final_prompt.md` | Prompt | Cross-step review |
| `prompts/CR-00093_S11_BrowserVerification_prompt.md` | Prompt | qv-browser render + click |
| `prompts/CR-00093_S12_SelfAssess_prompt.md` | Prompt | Self-assessment |

Reports created during execution under `ai-dev/work/CR-00093/reports/`.

## Acceptance Criteria

### AC1: Test categories complete

```
Given the worktree at HEAD of this CR
When `python -c "import json; d = json.load(open('.iw-orch.json')); print(len(d['test_config']['categories']))"` is run
Then it prints 24 (the existing 3 plus the 21 new test suites)
```

### AC2: Quality categories complete

```
Given the worktree at HEAD of this CR
When `python -c "import json; d = json.load(open('.iw-orch.json')); print(len(d['quality_config']['categories']))"` is run
Then it prints 13 (the existing 4 plus the 9 new quality gates)
```

### AC3: Every new category references a real Makefile target

```
Given the worktree at HEAD of this CR
When each new category's command is grepped against the project Makefile
Then every `make X` invocation resolves to an existing target (i.e. `grep -E "^X:" Makefile` finds the target line)
```

### AC4: e2e_stack flag scoped correctly

```
Given the worktree at HEAD of this CR
When the JSON is inspected
Then exactly `e2e` and `e2e-smoke` (and no other category) carry `e2e_stack: true`
AND no category outside the test_config block carries `e2e_stack`
```

### AC5: Existing entries untouched

```
Given the worktree at HEAD of this CR
When the existing 3 test categories (unit, integration, all) and 4 quality categories (lint, format, typecheck, all-quality) are compared byte-for-byte against `main`
Then they are byte-identical
```

### AC6: Tracker reflects the gap closure

```
Given the worktree at HEAD of this CR
When `ai-dev/work/TESTS_ENHANCEMENT.md` §8 is read
Then there is a new row recording "Dashboard launcher surface" with status DONE and link `CR-00093`
AND §11 has a new dated changelog entry at the top
```

### AC7: Browser verification — new cards render and one launches

```
Given the qv-browser step has run against the isolated E2E stack
When the Tests page is rendered
Then the page shows ≥21 new card entries (existing 3 + new 21 = ≥24 cards visible across groups)
AND the Quality page shows ≥9 new card entries (existing 4 + new 9 = ≥13 cards visible)
AND clicking a new card (e.g. `smoke`) returns a 2xx response
AND a corresponding TestRun row appears in the Runs tab
(Card-launch only — the suite does NOT need to complete during the qv-browser run.)
```

## Rollback Plan

- **Database**: N/A — no schema change.
- **Code**: Revert the merge commit. `project_registry.py` re-syncs `.iw-orch.json` to `project.config` on the next SIGHUP (or daemon restart), removing the new categories from the dashboard.
- **Data**: No data loss. Existing `TestRun` rows for `unit` / `integration` / `lint` / etc. are unaffected. Any `TestRun` rows created against new categories before rollback stay in the table (they show up under "category: <name>" — purely informational; the launch button for that category will be gone).

## Dependencies

- **Depends on**: All Phase 0–4 CRs/Features that shipped the Makefile targets being registered (CR-00046, CR-00047, CR-00048, CR-00050, CR-00051, CR-00052, CR-00059, CR-00060, CR-00061, CR-00072, CR-00073, CR-00074, CR-00075, CR-00076, CR-00082, CR-00083, CR-00085, F-00088, F-00089). All are merged.
- **Blocks**: None directly. CR-00080 (mutation-gate flip) and CR-00092 (column-docs scrub) ship independently; if CR-00092 deletes the baseline file before this CR ships, the `check-column-docs` Makefile recipe is updated by CR-00092 too — no coupling either way.

## Impacted Paths

- `.iw-orch.json`
- `ai-dev/work/TESTS_ENHANCEMENT.md`

## TDD Approach

This CR adds NO new behavioural tests — it's a config-only change to a JSONB-backed registry. The existing `tests/dashboard/test_route_contract_sweep.py` (CR-00072) sweeps every dashboard route and asserts `< 500`; it will exercise the Tests / Quality launch pages post-merge automatically.

- **Unit tests**: None added.
- **Integration tests**: None added.
- **Updated tests**: None.

The behavioural proof for this CR is the qv-browser step (S11), which renders the live pages, counts cards, clicks one, and confirms a `TestRun` row appears. In each implementation step's Subagent Result Contract, `tdd_red_evidence` uses the `"n/a — config-only registry edit; no new behavioural tests"` form.

## Notes

- **Daemon reload is operator's responsibility**: `project_registry.py` only re-reads `.iw-orch.json` on SIGHUP. After this CR merges, the operator runs `./ai-core.sh daemon reload` to surface the new cards. The CR's S01 verifies the sync code path works against a sandbox copy — it does NOT trigger a live SIGHUP. The browser verification step (S11) runs against the isolated E2E stack which spins up a fresh daemon reading the edited file from the worktree, so it sees the new cards without needing a SIGHUP on the production daemon.
- **Heavy-suite labels**: `mutation-audit` and `daemon-chaos-full` carry a wall-clock hint in their `description` field (`"~1h, intended for nightly CI"` and `"~minutes, full chaos matrix"` respectively). No prefix character in the `label` — the existing card UI doesn't render emoji-prefixed labels distinctly, so the warning lives in the description text that renders on the card.
- **Sibling projects out of scope**: this CR is `iw-ai-core`-only. Sibling projects (IW-AI-DEV, InnoForge, podforger, cv) have their own `.iw-orch.json` files and their own Makefile target sets — they can copy the pattern when ready. Recorded in tracker §8 follow-up note.
- **No new dashboard route, no new template change, no Python edit**: the registry-driven design from F-00078 (when test_config.categories was introduced) and CR-00086 (when the self-dashboarding panel was added) means every new category renders for free. This CR is the proof point that the registry abstraction was worth building.
- **`mutation-check`'s viability guard**: `make mutation-check` currently exits non-zero from the viability guard (M=0%, K=55 — CR-00080 OPEN). Operators clicking that card will see a failing TestRun row with the viability-guard reason in the log. That's correct behaviour — the card surfaces the gate's real state.
