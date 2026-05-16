# F-00084_S17_SelfAssess_prompt

**Work Item**: F-00084 — LLM-Assisted Merge Conflict Resolution (Phase 0 + Phase 1 dry-run)
**Step**: S17
**Agent**: SelfAssess

---

## ⛔ Docker is off-limits

Standard policy. Read-only `docker ps` / `docker inspect` permitted.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This analysis step performs NO database mutations.

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var.
- **Worktree logs** — `.worktrees/F-00084/ai-dev/logs/`.
- **Item reports dir** — `ai-dev/active/F-00084/reports/`.

## Output Files

- `ai-dev/active/F-00084/reports/F-00084_self_assess_report.md` — Human-readable narrative analysis.
- `ai-dev/active/F-00084/reports/F-00084_self_assess_findings.json` — Structured findings JSON.

## Context

You are running the self-assessment for **F-00084 — LLM-Assisted Merge Conflict Resolution (Phase 0 + Phase 1 dry-run)**.

Invoke the **`iw-item-analyze` skill** (auto-discovered via `.claude/skills/iw-item-analyze/SKILL.md`) to produce the standard two-output deliverable. Do NOT re-implement the analysis procedure.

## F-00084-Specific Focus Areas

In addition to the standard `iw-item-analyze` checks (agent thrash, tool failures, prompt gaps, manifest issues), pay specific attention to:

1. **Did any step run a real LLM call as part of testing?** This Feature mocks the LLM at the Python boundary; if any QV gate or fix cycle accidentally hit a real API endpoint, that's a finding to surface.

2. **Did S03's TDD RED evidence show genuine ImportError-style failure** (the new module didn't exist yet), or did it show NotImplementedError / AssertionError (which would mean the test was written against an existing-but-broken module)? Both are acceptable but they indicate different TDD discipline.

3. **Did any S03 fix-cycle attempt to satisfy a test by altering production code rather than fixing the test or surfacing the contract gap?** Tests-impl steps (S06) explicitly forbid silent prod-code edits to make tests pass; cross-check S03's fix-cycle prompts for any patterns where S06's tests drove uncomfortable S03 code paths.

4. **Was the Phase 0 invariant violated at any point during the build?** Search S03 + S06 logs for any record of `step_executor.sh` being invoked with `step_type=auto_merge_resolve` during the CI runs — there should be exactly ZERO real invocations because tests mock at the Python boundary.

5. **Did the bash/Python marker round-trip cause any cross-step retries?** If S05's first cross-agent review identified marker-format mismatches, that's a prompt-template gap (S01 and S03 should have agreed on the marker schema up front).

6. **Did any QV gate observe an unexpected DaemonEvent emission during its run?** Phase 0 default behaviour should be invisible to QV gates running on the worktree; if any gate emitted `merge_auto_resolution_*` events for this very item's worktree, that's a defect to flag (the resolver should not target its own work item).

## Soft-Step Semantics

Failure does NOT block merge. Produce a usable report regardless.

## Subagent Result Contract

```json
{
  "step": "S17",
  "agent": "self-assess-impl",
  "work_item": "F-00084",
  "completion_status": "complete",
  "files_changed": [
    "ai-dev/active/F-00084/reports/F-00084_self_assess_report.md",
    "ai-dev/active/F-00084/reports/F-00084_self_assess_findings.json"
  ],
  "preflight": {
    "format": "skipped:no-code-changes",
    "typecheck": "skipped:no-code-changes",
    "lint": "skipped:no-code-changes"
  },
  "tests_passed": true,
  "test_summary": "skipped: no tests for analysis step",
  "blockers": [],
  "notes": "F-00084 ships Phase 0 default-on (no operator-visible change). Findings focus on dry-run-discipline invariants and bash↔Python marker round-trip."
}
```
