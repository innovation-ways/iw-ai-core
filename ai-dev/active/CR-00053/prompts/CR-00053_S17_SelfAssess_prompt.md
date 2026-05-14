# CR-00053_S17_SelfAssess_prompt

**Work Item**: CR-00053 -- Idempotent `iw next-id` via `--idempotency-key` flag
**Step**: S17
**Agent**: SelfAssess

---

## ⛔ Docker is off-limits

(Standard policy. Read-only introspection — `docker ps`, `docker logs` — is allowed.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. You analyse, you do not modify migrations or the live DB.)

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var (canonical source — set by the executor).
- **Worktree logs** — `.worktrees/CR-00053/ai-dev/logs/` — run logs, fix-cycle logs.
- **Item reports dir** — `ai-dev/work/CR-00053/reports/` — existing step reports (secondary evidence only).

## Output Files

- `ai-dev/work/CR-00053/reports/CR-00053_self_assess_report.md` — Human-readable narrative analysis.
- `ai-dev/work/CR-00053/reports/CR-00053_self_assess_findings.json` — Structured findings JSON.

## Context

You are running the self-assessment step for **CR-00053** — a small, single-purpose CR that adds an `--idempotency-key` flag to `iw next-id`. The project has `self_assess=true` in `projects.toml`, so this step runs by default. Use the `iw-item-analyze` skill (loaded from `.opencode/skills/iw-item-analyze/` or `.claude/skills/iw-item-analyze/`) — do NOT re-implement the analysis procedure inline.

This step is **soft** — failure does NOT block the item from merging. Produce the best report you can even if the analysis is partial.

## What to Look For (CR-specific cues)

Because this CR is intentionally small and well-scoped, the most useful self-assess signals are:

1. **TDD RED evidence quality on S03**. The backend step must include a real `tdd_red_evidence` line citing the test id and the failure type (`TypeError`, `AssertionError`). If it says `"red"` or `"failed"` with no detail, flag as a process-improvement opportunity for the prompt template.
2. **Migration round-trip behavior on S02**. Did `make migration-check` pass first try, or did it need a fix-cycle? Partial unique indexes are the classic autogenerate gap; if S01 needed a fix-cycle to add `postgresql_where`, that's a prompt-improvement signal — the S01 prompt should call this out more loudly.
3. **Scope-creep detection on S07**. The CR's `scope.allowed_paths` is short and specific. Any S07 finding about files modified outside the list is a signal about either (a) the allowed_paths being too restrictive or (b) an implementer drifting.
4. **Concurrent-INSERT race test reliability**. The trickiest test in `tests/unit/test_id_allocations.py` is `test_concurrent_same_key_retries_and_returns_winner`. If S03 or S07 had to retry this test multiple times for flakiness, it's a signal about either the test fixture or the retry logic — capture it.
5. **Cross-CR pattern**. Compare with CR-00052 (the prior CR's audit-table-as-deliverable pattern) and CR-00051 (security gates). Are there recurring fix-cycle causes we can pre-empt in templates?

## Soft-Step Semantics

This step's failure does NOT block merge. If `iw-item-analyze` cannot complete (e.g., logs unreadable), write a stub report explaining why and a `findings: []` JSON.

## Subagent Result Contract

```json
{
  "step": "S17",
  "agent": "self-assess-impl",
  "work_item": "CR-00053",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/work/CR-00053/reports/CR-00053_self_assess_report.md",
    "ai-dev/work/CR-00053/reports/CR-00053_self_assess_findings.json"
  ],
  "preflight": {
    "format": "skipped:no-code-changes",
    "typecheck": "skipped:no-code-changes",
    "lint": "skipped:no-code-changes"
  },
  "tests_passed": true,
  "test_summary": "skipped: no tests for analysis step",
  "blockers": [],
  "notes": "Analysis completed; findings written to two output files."
}
```
