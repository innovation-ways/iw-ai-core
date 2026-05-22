# CR-00078_S20_SelfAssess_prompt

**Work Item**: CR-00078 -- Per-batch ignore overlap & force-start
**Step**: S20
**Agent**: self-assess-impl

---

## ⛔ Docker is off-limits
(Read-only docker introspection is allowed.)

## ⛔ Migrations: agents generate, daemon applies
Analysis step only.

## Input Files

- Item id: `$IW_ITEM_ID` (= `CR-00078`).
- Worktree logs: `.worktrees/CR-00078/ai-dev/logs/`.
- Step reports: `ai-dev/active/CR-00078/reports/`.
- Related: `ai-dev/active/CR-00077/reports/` — to understand whether the modal partial extension preserved CR-00077's contract.

## Output Files

- `ai-dev/active/CR-00078/reports/CR-00078_self_assess_report.md`
- `ai-dev/active/CR-00078/reports/CR-00078_self_assess_findings.json`

## Focus areas

Use the **`iw-item-analyze`** skill. When it produces findings, ensure the analysis covers:

1. **Daemon hook isolation** — Did the helper stay pure (no DB import)? Did the `batch_manager.py` diff stay confined to the existing F-00076 block (~30 lines), or did the implementation creep into adjacent code paths?
2. **AC5 cross-batch isolation** — Was `test_per_batch_isolation` actually two distinct batches, or did the implementation cut a corner? Confirm by inspecting the test source via the report.
3. **CR-00077 partial reuse** — Did the modal partial extension preserve the Esc/backdrop/× handlers, the `{% if empty %}` branch, and the script tag? Or did the extension drift?
4. **Idempotency cost** — Did any fix cycle trace back to a misunderstanding of `INSERT ... ON CONFLICT DO NOTHING` (e.g. forgetting the audit event must still fire on conflict)? If so, propose a workflow finding ("idempotent endpoints — audit events must fire regardless of insert outcome").
5. **300s-window inheritance** — Was the 300s window from CR-00077 reused via a shared constant, or duplicated as a literal in `ignore-all`? Duplication = MEDIUM finding.
6. **Migration round-trip** — Was `make migration-check` clean on first try, or did the autogen need manual FK touch-ups? If the latter, propose a documentation finding for the schema-design pattern.
7. **`ignored_by` placeholder** — Is the TODO present and discoverable? If auth lands later, will the swap be a single-file edit?

## Soft-Step Semantics

Failure does NOT block merge. Produce a stub report if the analysis can't complete.

## Subagent Result Contract

```json
{
  "step": "S20",
  "agent": "self-assess-impl",
  "work_item": "CR-00078",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/active/CR-00078/reports/CR-00078_self_assess_report.md",
    "ai-dev/active/CR-00078/reports/CR-00078_self_assess_findings.json"
  ],
  "preflight": {"format": "skipped:no-code-changes", "typecheck": "skipped:no-code-changes", "lint": "skipped:no-code-changes"},
  "tests_passed": true,
  "test_summary": "skipped: analysis step",
  "blockers": [],
  "notes": "Analysis completed; findings written to two output files."
}
```
