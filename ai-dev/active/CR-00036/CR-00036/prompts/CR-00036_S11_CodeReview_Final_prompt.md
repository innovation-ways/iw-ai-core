# CR-00036_S11_CodeReview_Final_prompt

**Work Item**: CR-00036 -- Batch-level auto_merge toggle with operator-approved manual merge
**Review Step**: S11 (Final Review)
**Implementation Steps Reviewed**: S01..S10

---

## ⛔ Docker is off-limits / ⛔ Migrations: agents generate, daemon applies

Standard policies. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `ai-dev/active/CR-00036/CR-00036_CR_Design.md`
- All step reports: `ai-dev/work/CR-00036/reports/CR-00036_S*_*_report.md`
- All files listed across the implementation reports' `files_changed`.

## Output Files

- `ai-dev/work/CR-00036/reports/CR-00036_S11_CodeReview_Final_report.md`

## Context

You are performing the **final cross-agent review** of ALL implementation work for CR-00036. Per-agent reviews have already passed; your job is to catch cross-cutting issues — places where two layers built by different agents fail to integrate.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

NEW violations → CRITICAL findings.

## Review Checklist

### 1. Completeness vs Design Doc

For each numbered "Desired Behavior" item (1-12) and each of AC1..AC10, AC11a, AC11b:
- Locate the implementing code (file + symbol).
- Locate the test that covers it.
- Flag any gap as a `missing_requirements` entry.

Pay special attention to "Desired Behavior" item 10 (worktree lifecycle / stall-checker exemption): verify either (a) a code-level exemption was added, or (b) the S03 report's `stall_audit` notes that no auto-fail path exists today and the doc note suffices. Silent omission of this verification is a HIGH finding.

### 2. Cross-Agent Consistency

- The new state name `awaiting_merge_approval` is spelled identically in the migration, ORM enum, BatchManager gate, `_merge_status`, and templates. ANY casing/spelling drift is CRITICAL.
- The new endpoint URL `/actions/item/{item_id}/approve-merge` is spelled identically in the route definition, the action button macro, and the tests. Mismatches silently no-op.
- `auto_merge` (snake_case) is the column, the dataclass field, the form key, the CLI flag (`--auto-merge`), and the projects.toml key. Drift here breaks one of the layers silently.
- The dashboard `_merge_status` returns `"awaiting_approval"` (without the `_merge_` prefix) — the templates compare against this exact string. Confirm the templates use the same string.

### 3. Integration Points

- Project default flows from projects.toml → `ProjectConfig.auto_merge_default` → `iw batch-create` resolution → `Batch.auto_merge` column → `BatchManager` gate → dashboard rendering. Trace the value end-to-end and assert no layer drops it.
- The "create batch from selection" route also passes through the project default. Verify both batch-creation paths (CLI and dashboard) are wired.
- `process_merge_queue` is **unchanged**. Confirm via diff against `main` — any modification is a HIGH finding because the design explicitly forbids it.

### 4. Test Coverage (Holistic)

- The end-to-end test (`test_merge_queue_auto_merge_gate.py`) exercises the gate from BatchManager through to merge_queue without mocking the gate logic itself.
- All AC items (AC1..AC10, AC11a, AC11b) have at least one test.
- The `BatchItemStatus` enum is exhaustively tested wherever it's iterated.

### 5. Architecture Compliance

- Routers stay thin (delegate to `orch/services/...`). No business logic in `dashboard/routers/actions.py`.
- DaemonEvent metadata uses `event_metadata` (Python attribute) everywhere.
- No new direct DB writes outside the service layer for the approve-merge path.

### 6. Documentation Coherence

- `docs/IW_AI_Core_Database_Schema.md`, `docs/IW_AI_Core_CLI_Spec.md`, and `docs/IW_AI_Core_Daemon_Design.md` all describe the new feature consistently. Inconsistencies between docs are HIGH findings (operators rely on whichever doc they read first).

### 7. Security

- No new auth bypass — `approve-merge` follows the same auth model as `restart-merge`.
- No injection vector via the new form fields (Form parsing is type-checked).

## Test Verification (NON-NEGOTIABLE)

Run the **full** test suite — both unit AND integration AND dashboard:

```bash
make test-unit && make test-integration && make test-dashboard
```

If integration tests fail, this is a CRITICAL finding.

## Severity Levels

| Severity | Examples |
|----------|----------|
| CRITICAL | State-name drift across layers; URL spelling mismatch; gate bypassed by some path; failing tests |
| HIGH | `process_merge_queue` modified; doc inconsistency; project default not flowing through one entry point |
| MEDIUM (fixable) | Suboptimal pattern, redundant query, weak test |
| LOW | Style nitpick |

## Review Result Contract

```json
{
  "step": "S11",
  "agent": "CodeReview_Final",
  "work_item": "CR-00036",
  "steps_reviewed": ["S01", "S02", "S03", "S04", "S05", "S06", "S07", "S08", "S09", "S10"],
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit, Y integration, Z dashboard, 0 failed",
  "missing_requirements": [],
  "notes": ""
}
```
