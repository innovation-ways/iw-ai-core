# CR-00058_S07_CodeReview_Final_prompt

**Work Item**: CR-00058 — Configurable per-project scope-overlap gate with block/allow policy
**Step**: S07 (code-review-final-impl)

---

## ⛔ Docker is off-limits

Standard policy.

## ⛔ Migrations: agents generate, daemon applies

No migrations expected. Flag any migration file as CRITICAL.

## Input Files

- `ai-dev/active/CR-00058/CR-00058_CR_Design.md`
- All step reports: S01–S06
- All files under `scope.allowed_paths`
- The full diff vs `main` for the worktree
- Runtime step state via `uv run iw item-status CR-00058 --json`

## Output Files

- `ai-dev/active/CR-00058/reports/CR-00058_S07_CodeReview_Final_report.md`
- Findings file: `ai-dev/active/CR-00058/reports/CR-00058_S07_CodeReview_Final_findings.json`

## Review Focus (cross-agent integration)

1. **End-to-end policy round-trip**: `.iw-orch.json` → `project_registry._parse_overlap_gate` → `ProjectConfig.overlap_{block,allow}_patterns` → `batch_manager._process_batch` → `scope_overlap.find_blocking_items` → `DaemonEvent` row → `dashboard/routers/batches.py` → template pill. Trace this path end-to-end and confirm there's no drift between layers (field names, event metadata keys, glob list shape).
2. **Default-preservation invariant**: a project that adopts no `overlap_gate` block has byte-equivalent behaviour to pre-CR (modulo new `item_overlap_allowed_by_policy` events — which should be zero for the default-config case). Cross-check S02's `test_default_policy_holds_source_overlap_across_batches`.
3. **Audit trail completeness**: every policy decision is observable. Held → `item_held_for_scope` (one per blocking item per poll, as today). Released-by-policy → `item_overlap_allowed_by_policy` (one per launch decision, as new design says).
4. **F-00076 contract tests** (`tests/integration/test_f_00076_scope_extraction_round_trip.py`, `tests/integration/test_f_00076_gate_performance.py`) are not regressed. If they require updates to pass with the new kw-only signature, that's allowed but should be flagged as MEDIUM if the diff isn't minimal.
5. **No silent expansion of `scope.allowed_paths`**. The manifest's `allowed_paths` is the contract; any modified file outside it is a CRITICAL scope violation.
6. **Documentation matches code**. Decision-tree narrative in `docs/IW_AI_Core_Daemon_Design.md` matches the actual `find_blocking_items` + emit-event control flow; `.iw-orch.json` example matches the default constants in `scope_overlap.py`.
7. **Operator UX preserved on every failure path**: malformed config → warning + default, not a crash. Missing project (raceable with SIGHUP) → graceful degradation, not a crash.
8. **No dead code**: if `is_test_path` is no longer used in `scope_overlap`, confirm it's still imported by `batch_planner.py` (the other documented consumer). If neither uses it, it's dead.

## Severity Guidance

- **CRITICAL**: policy drift between layers, default-policy regression, scope violation, audit-event missing in a path that should emit.
- **HIGH**: doc/code divergence on the schema, integration-test gap on a documented AC, F-00076 contract regression.
- **MEDIUM**: redundant DB roundtrips, style drift from neighboring modules, missing operator-guidance note.
- **LOW**: naming, comment polish.

## Subagent Result Contract

```json
{
  "step": "S07",
  "agent": "code-review-final-impl",
  "work_item": "CR-00058",
  "completion_status": "complete",
  "findings": [],
  "files_reviewed": [],
  "preflight": {"format": "skipped:review-only", "typecheck": "skipped:review-only", "lint": "skipped:review-only"},
  "tests_passed": true,
  "test_summary": "skipped: review step",
  "tdd_red_evidence": "n/a — review-only step",
  "blockers": [],
  "notes": ""
}
```
