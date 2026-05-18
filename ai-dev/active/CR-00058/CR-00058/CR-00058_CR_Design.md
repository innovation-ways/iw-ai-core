# CR-00058: Configurable per-project scope-overlap gate with block/allow policy

**Type**: Change Request
**Priority**: Medium
**Reason**: The F-00076 cross-batch overlap gate is currently unconditional. With auto-merge in Phase-1 dry-run (R-00076 / `ai-dev/active/AUTO_MERGE_RESOLUTION.md`), the gate prevents legitimate parallel work even where the future merge-resolution risk is low. Operators need a per-path knob to relax the gate without flipping it off blanket-wise, plus observability events to audit policy effects.
**Created**: 2026-05-17
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

This CR **does not** add or modify any Alembic migration. The new policy lives in the existing `Project.config` JSONB column.

## Description

Today `orch/daemon/batch_manager._process_batch` calls `scope_overlap.find_blocking_items()` with every candidate item's `WorkItem.impacted_paths`; any overlap with an in-flight item in the same project (across batches) holds the candidate, regardless of how risky the overlap actually is. We will make the gate per-project configurable via a new `overlap_gate` block in `.iw-orch.json`, supporting `block_on_overlap` and `allow_on_overlap` glob lists. Per-conflicting-glob allow precedence means a glob that matches both lists does not block.

## Project Context

Read `CLAUDE.md`, `orch/CLAUDE.md`, and `orch/daemon/scope_overlap.py` for the current behavior. Read `ai-dev/active/AUTO_MERGE_RESOLUTION.md` and `docs/research/R-00076-llm-automated-merge-resolution.md` for the motivation.

## Current Behavior

`orch/daemon/scope_overlap.py:find_blocking_items()` is invoked at every daemon poll for every pending batch item. It returns the list of in-flight items that overlap the candidate's `impacted_paths`. If the list is non-empty, `batch_manager._process_batch` skips the launch without consuming a `max_parallel` slot and emits one `item_held_for_scope` `DaemonEvent` per blocking item per poll cycle.

`scope_overlap` has one hardcoded exclusion: paths matching `is_test_path()` (anchored `tests/`, `test/`, `__tests__/`, or containing `conftest`, `.test.`, `.spec.`) are stripped from both sides before intersection. There is no other operator-visible knob. Two source files in the same parent directory are also flagged via `_same_parent` sibling matching.

Real example (currently active): `CR-00057` is held in `BATCH-00112` because:
- `CR-00057.impacted_paths` includes `dashboard/static/chat_assistant/chat.js` and `orch/daemon/project_registry.py`.
- `I-00087.impacted_paths` includes `dashboard/static/chat_assistant/chat.js`.
- `I-00088.impacted_paths` includes `orch/daemon/project_registry.py`.

Both source-file overlaps are exact matches; neither side is a test path; the gate fires unconditionally. CR-00057 has waited ~30 min so far across multiple poll cycles.

## Desired Behavior

`.iw-orch.json` accepts a new (optional) `overlap_gate` block:

```jsonc
{
  "overlap_gate": {
    "block_on_overlap": ["**/*"],
    "allow_on_overlap": [
      "tests/**",
      "test/**",
      "__tests__/**",
      "**/*conftest*",
      "**/*.test.*",
      "**/*.spec.*"
    ]
  }
}
```

- **Defaults preserve today's behavior.** If `overlap_gate` is absent, the daemon synthesises `{block_on_overlap: ["**/*"], allow_on_overlap: [test patterns above]}` — the test patterns make the previously implicit `is_test_path` strip explicit and self-documenting. Strict matching against source files is unchanged.
- **Allow takes precedence per conflicting glob.** After `find_blocking_items` returns the list of conflicting globs (from the candidate's side), each glob is filtered: a glob that matches any `allow_on_overlap` pattern is dropped. If the filtered list is empty, the candidate is allowed to launch.
- **Observability.** When a launch goes through that the default-strict policy would have held, the daemon emits one `item_overlap_allowed_by_policy` `DaemonEvent` (per launch decision, not per poll cycle) with metadata listing the matched allow patterns and the in-flight items it overlapped with. The existing `item_held_for_scope` event continues to fire for items still held.
- **Dashboard.** The batch detail and queue pages already surface `item_held_for_scope` reasons via `dashboard/routers/batches.py:74-149`. We extend that surface to also show "allowed by policy" decisions (e.g. an info-tone pill on the item row) so operators see when the policy is actively releasing items.
- **"Depends on" graph is untouched.** Cross-item dependencies continue to be enforced via `execution_group` ordering in `batch_manager._process_batch`. This CR changes only the F-00076 path.

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `orch/daemon/scope_overlap.py` | `find_blocking_items(candidate, in_flight)`; hardcoded test-strip via `is_test_path` | `find_blocking_items(candidate, in_flight, *, block_patterns, allow_patterns)`; hardcoded strip removed; default callers must pass policy. `is_test_path` kept as a public helper for callers that want to compose defaults. |
| `orch/daemon/project_registry.py` | `ProjectConfig` exposes `scope_gate_enabled` (merge-time, separate concept), no overlap policy | New `overlap_block_patterns: list[str]` and `overlap_allow_patterns: list[str]` fields on `ProjectConfig`; parsed from `iw_config["overlap_gate"]` with validation and warning-on-malformed |
| `orch/daemon/batch_manager.py` | `_process_batch` calls `scope_overlap.find_blocking_items(candidate_paths, in_flight_scopes)` | Reads policy from `self.project_config` (already injected via `BatchOrchestrator.__init__`); passes patterns into `find_blocking_items`; emits `item_overlap_allowed_by_policy` event when a launch would have been blocked by the default policy but the project policy released it |
| `dashboard/routers/batches.py` | `_held_reasons_for_items()` queries `item_held_for_scope` events | Also queries `item_overlap_allowed_by_policy` events; returns a record per item indicating held vs allowed-by-policy with the matched patterns |
| `dashboard/templates/fragments/batch_items_rows.html` (+ queue/batch detail partials as applicable) | Shows held-reason pill when present | Shows new info-tone "policy allowed" pill when applicable; tooltip names the patterns |
| `tests/unit/daemon/test_scope_overlap.py` | Existing cases pin current intersection behavior | New cases: explicit-defaults (with test patterns) equivalent to old `is_test_path` strip; allow-only filter; block + allow precedence; empty-after-filter; glob edge cases (anchor, sibling). Existing positional `find_blocking_items(candidate, in_flight)` calls updated to the new kw-only signature. |
| `tests/integration/daemon/test_overlap_gate_policy.py` *(new)* | n/a | End-to-end: project A configured strict, project B configured permissive on `tests/**` and `docs/**`; assert held vs released; assert events; mirror CR-00057-style real source-file overlap |
| `tests/integration/daemon/test_batch_manager_scope_gate.py` | Calls `find_blocking_items(candidate, in_flight)` positionally at line 161 | Updated to pass `block_patterns=` / `allow_patterns=` kw-only; no behavioral change expected |
| `tests/integration/test_f_00076_gate_performance.py` | Calls `find_blocking_items(candidate, in_flight)` positionally at lines 89/104/118 | Updated to pass `block_patterns=` / `allow_patterns=` kw-only; perf assertion unchanged |
| `tests/integration/daemon/__init__.py` | Missing | Created (empty) so the new test file is importable under all pytest collection modes |
| `tests/dashboard/test_batches_router.py` *(new)* | n/a | Router test covering the `policy_allowed` record shape and the held-precedence rule (sibling to existing `tests/dashboard/test_*_router.py` files) |
| `docs/IW_AI_Core_Daemon_Design.md` | Documents `is_test_path` strip | Documents new `overlap_gate` block, default values, decision tree, observability events |
| `docs/IW_AI_Core_Architecture.md` | Brief mention of F-00076 gate | Brief mention of per-project policy |
| `.iw-orch.json` (this repo) | No `overlap_gate` block | Add an `overlap_gate` block equivalent to the new default (explicit-default form) so operators see the shape; the file is in scope so the change ships in the same merge |

### Breaking Changes

None at the public interface:

- `.iw-orch.json` keys are optional; missing keys yield the new default (which preserves today's behavior).
- `scope_overlap.find_blocking_items` signature changes (new required kw-only params). All in-tree call sites are updated in the same PR. There are no external callers of this private module.

### Data Migration

None. `Project.config` is already JSONB; the new key surfaces on the next daemon SIGHUP reload (`./ai-core.sh daemon reload`). Reversible: removing the `overlap_gate` block + SIGHUP reverts to the synthesized default.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | backend-impl | `scope_overlap.py` (signature + allow-precedence filter, drop hardcoded `is_test_path` strip), `project_registry.py` (parse + validate `overlap_gate`), `batch_manager.py` (read policy, emit `item_overlap_allowed_by_policy`). TDD unit tests for `scope_overlap` and `project_registry` parsing | — |
| S02 | tests-impl | Integration test: two batches with overlapping source-file paths, one project strict / one permissive; assert events + status transitions | — |
| S03 | frontend-impl | Extend `dashboard/routers/batches.py` reason builder + templates to surface allowed-by-policy pill | — |
| S04 | template-impl | Update `docs/IW_AI_Core_Daemon_Design.md` (config keys, decision tree, events), brief mention in `docs/IW_AI_Core_Architecture.md`, add explicit `overlap_gate` block in this repo's `.iw-orch.json`, help partial copy | — |
| S05 | code-review-impl | Per-agent review of S01..S04 | — |
| S06 | code-review-fix-impl | Address CRITICAL/HIGH findings from S05 | — |
| S07 | code-review-final-impl | Cross-agent final review | — |
| S08 | code-review-fix-final-impl | Address final-review CRITICAL/HIGH findings | — |
| S09 | qv-gate | `make lint` | — |
| S10 | qv-gate | `make format` | — |
| S11 | qv-gate | `make typecheck` | — |
| S12 | qv-gate | `make test-unit` | — |
| S13 | qv-gate | `make allure-integration` | — |
| S14 | qv-browser | Browser verification — held pill, allowed-by-policy pill, default no-regression | — |
| S15 | self-assess-impl | iw-item-analyze post-execution analysis (soft) | — |

### Database Changes

- **New tables**: None.
- **Modified tables**: None (Project.config JSONB key only).
- **Migration notes**: None.

### API Changes

- **New endpoints**: None.
- **Modified endpoints**: None. (The dashboard reads new event metadata via existing `/batches/...` page render path.)
- **Removed endpoints**: None.

### Frontend Changes

- **New components**: None.
- **Modified components**: Held-reason pill in `dashboard/templates/fragments/batch_items_rows.html` (and adjacent queue/batch-detail partials if they share the snippet) — additional `policy-allowed` tone case, tooltip lists matched allow patterns.
- **Removed components**: None.

## File Manifest

All files for this work item live under `ai-dev/active/CR-00058/`.

| File | Type | Purpose |
|------|------|---------|
| `CR-00058_CR_Design.md` | Design | This document |
| `CR-00058_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/CR-00058_S01_Backend_prompt.md` | Prompt | S01 backend implementation |
| `prompts/CR-00058_S02_Tests_prompt.md` | Prompt | S02 integration tests |
| `prompts/CR-00058_S03_Frontend_prompt.md` | Prompt | S03 dashboard surfacing |
| `prompts/CR-00058_S04_Template_prompt.md` | Prompt | S04 docs + config |
| `prompts/CR-00058_S05_CodeReview_prompt.md` | Prompt | S05 per-agent review |
| `prompts/CR-00058_S06_CodeReview_FIX_prompt.md` | Prompt | S06 review fixes |
| `prompts/CR-00058_S07_CodeReview_Final_prompt.md` | Prompt | S07 final cross-agent review |
| `prompts/CR-00058_S08_CodeReview_FIX_Final_prompt.md` | Prompt | S08 final review fixes |
| `prompts/CR-00058_S14_BrowserVerification_prompt.md` | Prompt | S14 browser verification |
| `prompts/CR-00058_S15_SelfAssess_prompt.md` | Prompt | S15 self-assessment |

Reports are created during execution in `ai-dev/active/CR-00058/reports/`.

## Acceptance Criteria

### AC1: Defaults preserve current behavior on a project with no `overlap_gate` block

```
Given a project whose .iw-orch.json has no overlap_gate block
And two in-flight items in different batches whose impacted_paths overlap on a source file
When the daemon evaluates a pending batch item whose impacted_paths overlap on the same source file
Then the candidate is held
And an item_held_for_scope DaemonEvent is emitted with the overlapping globs
And no item_overlap_allowed_by_policy event is emitted
```

### AC2: Defaults preserve test-path strip semantics

```
Given a project whose .iw-orch.json has no overlap_gate block
And an in-flight item whose impacted_paths contains a tests/** glob shared with the candidate
When the daemon evaluates the candidate
Then the candidate is launched
And no item_held_for_scope event is emitted for the test-path overlap
```

### AC3: Per-project allow pattern releases an otherwise-blocked candidate

```
Given a project whose .iw-orch.json overlap_gate.allow_on_overlap includes "docs/**"
And an in-flight item modifying docs/Foo.md
When the daemon evaluates a pending candidate modifying docs/Bar.md (sibling overlap)
Then the candidate is launched
And one item_overlap_allowed_by_policy DaemonEvent is emitted referencing the matched allow pattern
```

### AC4: Allow precedence is per conflicting glob (not all-or-nothing)

```
Given a project whose overlap_gate.allow_on_overlap = ["docs/**"]
And an in-flight item modifying both docs/X.md and orch/foo.py
When the daemon evaluates a candidate modifying both docs/Y.md and orch/foo.py
Then the candidate is held by orch/foo.py
And the held event metadata lists orch/foo.py as the remaining conflicting glob
And the docs/** overlap is NOT counted toward the held reason
```

### AC5: SIGHUP-driven reload picks up policy edits without restart

```
Given the daemon is running with the default overlap_gate policy
When the operator adds "tests/**" to allow_on_overlap in .iw-orch.json
And triggers ./ai-core.sh daemon reload (SIGHUP)
Then the next poll cycle uses the new policy
And no item launched before the reload is affected
```

### AC6: Dashboard surfaces both held-reason and allowed-by-policy pills

```
Given a project with a non-default overlap_gate policy
And one item held by scope overlap on a source file
And one item launched whose overlap was released by an allow pattern
When the operator opens the batch detail page
Then the held item row shows the existing held-reason pill
And the launched item row shows a new info-tone "policy allowed" pill listing the matched pattern(s)
And no new console errors appear
```

## Rollback Plan

- **Database**: N/A — no schema changes.
- **Code**: Revert the CR-00058 squash-merge commit. The previous `find_blocking_items` signature is restored; all in-tree callers revert together.
- **Data**: No data loss. `Project.config['overlap_gate']` is ignored by the prior code path; remove it on next `.iw-orch.json` edit + SIGHUP if desired.

## Dependencies

- **Depends on**: None.
- **Blocks**: None. (A future CR can wire this policy to the executor/auto_merge.toml allowlist to keep them in sync — explicitly out of scope here.)

## Impacted Paths

The cross-batch gate enforces these as `WorkItem.impacted_paths`; the merge-time scope gate enforces the manifest mirror in `scope.allowed_paths`. Test paths are listed but ignored by the cross-batch gate per F-00076 — do NOT omit them.

- `orch/daemon/scope_overlap.py`
- `orch/daemon/batch_manager.py`
- `orch/daemon/project_registry.py`
- `dashboard/routers/batches.py`
- `dashboard/templates/fragments/batch_items_rows.html`
- `dashboard/templates/_partials/help/batches.html`
- `dashboard/templates/_partials/help/queue.html`
- `dashboard/templates/_partials/help/batch_detail.html`
- `dashboard/static/styles.css`
- `tests/unit/daemon/test_scope_overlap.py`
- `tests/unit/daemon/test_project_registry_overlap_gate.py`
- `tests/integration/daemon/__init__.py`
- `tests/integration/daemon/test_overlap_gate_policy.py`
- `tests/integration/daemon/test_batch_manager_scope_gate.py`
- `tests/integration/test_f_00076_gate_performance.py`
- `tests/dashboard/test_batches_router.py`
- `docs/IW_AI_Core_Daemon_Design.md`
- `docs/IW_AI_Core_Architecture.md`
- `.iw-orch.json`

## TDD Approach

- **Unit tests** (`tests/unit/daemon/test_scope_overlap.py`):
  - `test_default_policy_blocks_source_overlap` — block_patterns=["**/*"], allow_patterns=[] → blocks source overlap.
  - `test_default_policy_with_test_allows_releases_tests` — block_patterns=["**/*"], allow_patterns=[the test patterns] → tests/** overlap not blocking (equivalent to old `is_test_path` strip).
  - `test_allow_takes_precedence_per_conflicting_glob` — overlap of two globs, one allowlisted, one not → only the non-allowlisted glob remains in the result.
  - `test_allow_releases_full_overlap` — every conflicting glob matches an allow pattern → empty result, candidate launches.
  - `test_sibling_directory_overlap_respects_allow` — two files in same dir, dir matches allow → no block.
  - `test_anchor_containment_respects_allow` — `dashboard/**` allowed; both sides under `dashboard/` → no block.
  - `test_unparseable_block_pattern_treated_as_no_match` — graceful degradation, warning logged.
  - `test_empty_block_patterns_means_no_gating` — `block_on_overlap=[]` → never blocks regardless of overlap.
- **Unit tests** (`tests/unit/daemon/test_project_registry_overlap_gate.py` *or extend existing*):
  - `test_parse_valid_overlap_gate` — full block returned via `ProjectConfig`.
  - `test_parse_missing_block_synthesises_default` — absent key → default block=`["**/*"]`, allow=test patterns.
  - `test_parse_malformed_block_warns_and_defaults` — non-list values → warning + default.
  - `test_parse_non_string_pattern_dropped` — list with mixed types → drop non-strings, warn.
- **Integration test** (`tests/integration/daemon/test_overlap_gate_policy.py`):
  - Two batches across two projects with overlapping source paths; one project strict (default), one permissive. Assert `BatchItem.status` transitions, `DaemonEvent` rows, and that no in-flight item is killed mid-launch by policy changes (we only check on launch decision).
- **Updated tests**:
  - Existing `tests/unit/daemon/test_scope_overlap.py` cases that relied on the implicit `is_test_path` strip must now pass the equivalent allow patterns explicitly (or use a thin default-factory helper exposed by `scope_overlap`). No behavioral regression.
  - `tests/integration/test_f_00076_scope_extraction_round_trip.py` — verify still passes; no changes expected.
  - `tests/integration/test_f_00076_gate_performance.py` — verify still passes; pattern matching adds at most a constant factor per conflicting glob.

## Notes

- **Naming**: the new config key is `overlap_gate` (not `scope_gate`) to avoid confusion with the existing `scope_gate_enabled` flag, which is a separate concept (merge-time enforcement of `scope.allowed_paths`, added after I-00034). Both exist; this CR does not touch the merge-time gate.
- **Re-evaluating the default**: per `ai-dev/active/AUTO_MERGE_RESOLUTION.md`, we should re-examine whether to ship a looser default after Phase 2 (auto-merge with verification gate) has 4+ weeks of green data on its allowlist. That decision is explicitly deferred and not part of this CR.
- **Future work** (separate CR, not blocking): auto-derive `allow_on_overlap` from `executor/auto_merge.toml`'s allowlist so the two stay in sync.
- **Observability event metadata**: `item_overlap_allowed_by_policy.metadata` should include `{candidate_item_id, in_flight_item_ids, matched_allow_patterns, dropped_block_globs}` so dashboards can render the pill without re-running the classifier.
- **Concurrency note**: a candidate that is released by policy but later collides at merge time is exactly the scenario the merge-time `scope_gate_enabled` flag exists for. Operators relaxing `overlap_gate` should consider enabling `scope_gate_enabled` symmetrically. We will document this guidance in `docs/IW_AI_Core_Daemon_Design.md` without forcing the coupling in code.
