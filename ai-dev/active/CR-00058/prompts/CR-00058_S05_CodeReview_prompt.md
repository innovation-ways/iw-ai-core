# CR-00058_S05_CodeReview_prompt

**Work Item**: CR-00058 — Configurable per-project scope-overlap gate with block/allow policy
**Step Being Reviewed**: S01 (backend-impl), S02 (tests-impl), S03 (frontend-impl), S04 (template-impl)
**Review Step**: S05 (code-review-impl)

---

## ⛔ Docker is off-limits

Standard policy. Read-only review work; no docker mutation.

## ⛔ Migrations: agents generate, daemon applies

No migrations expected in this CR. Flag any migration file under `orch/db/migrations/versions/**` as CRITICAL scope violation.

## Input Files

- `ai-dev/active/CR-00058/CR-00058_CR_Design.md` — the contract
- `ai-dev/active/CR-00058/reports/CR-00058_S01_Backend_report.md`, S02, S03, S04 reports
- All files listed under `scope.allowed_paths` in `workflow-manifest.json`
- Runtime step state via `uv run iw item-status CR-00058 --json`

## Output Files

- `ai-dev/active/CR-00058/reports/CR-00058_S05_CodeReview_report.md` with findings JSON
- Findings file: `ai-dev/active/CR-00058/reports/CR-00058_S05_CodeReview_findings.json`

## Review Focus

### Correctness (CRITICAL/HIGH)

1. **Allow precedence is per conflicting glob, not all-or-nothing.** Concretely: when candidate overlaps in-flight on `{docs/X.md, orch/foo.py}` and `allow_on_overlap=["docs/**"]`, the candidate must remain *held* by `orch/foo.py`. Trace `scope_overlap.find_blocking_items` and assert this in code reading; cross-reference S01's unit test `test_allow_takes_precedence_per_conflicting_glob` and S02's integration test `test_per_conflicting_glob_precedence`.
2. **Default policy preserves old `is_test_path` semantics.** Without `overlap_gate` in `.iw-orch.json`, `find_blocking_items` must behave identically to the pre-CR module — confirm via S01's `test_default_policy_with_test_allows_releases_tests`.
3. **`item_overlap_allowed_by_policy` fires once per launch decision, not per poll cycle.** Verify the emit is placed *before* `_launch_item` and is gated by the actual launch path (not the held branch). Confirm no duplicate emits when a single candidate overlaps multiple in-flight items.
4. **Dependency graph unaffected.** `execution_group` ordering must not be reachable through any new code path — the policy only affects the overlap branch.
5. **Event metadata is complete and accurate.** `matched_allow_patterns` lists the patterns that actually matched; `dropped_globs` lists the globs that were filtered out; `in_flight_item_ids` is the set that the *default* policy would have flagged.
6. **`scope_overlap.find_blocking_items` is now kw-only for the new params.** Every in-tree caller passes them; no positional regression.

### Configuration parsing (HIGH)

7. **Default synthesis.** When `overlap_gate` is missing, defaults come from the constants in `scope_overlap.py`. When one side is malformed and the other is valid, only the malformed side falls back to default — verify with S01's `test_partial_block_uses_default_for_missing_side`.
8. **Defensive parsing.** Non-list, non-string entries are dropped with warnings — daemon never raises on malformed config.

### Frontend (MEDIUM/HIGH)

9. **Pill rendering.** `policy_allowed` pill is visually distinct from `held` and exposes matched patterns via tooltip. No new console errors.
10. **Held precedence over policy-allowed for the same item.** If both event types exist within the window, render only `held`.
11. **Single combined DaemonEvent query.** Router doesn't add an extra round-trip per item.

### Tests (MEDIUM)

12. **Real testcontainer DB, no mocks** in the integration test (`tests/CLAUDE.md` rule).
13. **FTS DDL applied** if any schema rebuild happens in the new file.
14. **Tests assert DB state**, not just function return values, for the policy-allowed event row.
15. **TDD RED evidence** is present and not a fixture/import error.

### Scope discipline (HIGH)

16. **No file modifications outside `scope.allowed_paths`.** Cross-check `git diff --name-only main...HEAD` against the manifest scope list.
17. **`is_test_path` retained for `batch_planner.py`** — do not remove the public helper just because the gate no longer uses it directly.

### Documentation (MEDIUM)

18. **`docs/IW_AI_Core_Daemon_Design.md`** documents the new keys, decision tree, both event types, and SIGHUP semantics. Operator guidance paragraph about pairing with `scope_gate_enabled` present.
19. **`.iw-orch.json`** in this repo has the explicit default block (operator-facing example) — JSON valid.

## Severity Guidance

- **CRITICAL**: incorrect allow precedence, default-policy regression, event over/under-emission, dependency-graph short-circuit.
- **HIGH**: scope violation, missing event metadata field, malformed config crash, pill rendering breakage.
- **MEDIUM**: doc omissions, test-quality concerns that don't affect correctness, accessibility gaps.
- **LOW**: stylistic, naming, minor comment polish.

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "code-review-impl",
  "work_item": "CR-00058",
  "completion_status": "complete",
  "findings": [
    {"id": "F1", "severity": "CRITICAL|HIGH|MEDIUM|LOW", "file": "path:line", "issue": "...", "recommendation": "..."}
  ],
  "files_reviewed": [],
  "preflight": {"format": "skipped:review-only", "typecheck": "skipped:review-only", "lint": "skipped:review-only"},
  "tests_passed": true,
  "test_summary": "skipped: review step",
  "tdd_red_evidence": "n/a — review-only step",
  "blockers": [],
  "notes": ""
}
```
