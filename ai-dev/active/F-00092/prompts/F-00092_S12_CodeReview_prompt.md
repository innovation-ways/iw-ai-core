# F-00092_S12_CodeReview_prompt

**Work Item**: F-00092 — Tier-1 orchestration DB backups
**Step**: S12
**Agent**: code-review-impl

---

## ⛔ Docker is off-limits

Read-only Docker introspection only. Verify tests use testcontainers, never 5433.

## Input Files

- `uv run iw item-status F-00092 --json`.
- `ai-dev/active/F-00092/F-00092_Feature_Design.md`.
- Reports + diffs for S08 (Jobs UI), S09 (CLI + ai-core.sh), S10 (docs), S11 (tests).

## Output Files

- `ai-dev/active/F-00092/reports/F-00092_S12_CodeReview_report.md`.

## Review Checklist (cite file:line)

**S08 — Jobs UI**
1. `DbBackupJob` mapped into the aggregator like the other sources; renders in the
   jobs view; Jinja2 `format` filter is `%`-style (no `str.format`).

**S09 — CLI + ai-core.sh**
2. `iw db-backup {create,list,prune,restore}` registered and matches click
   conventions; `create` works without the daemon (AC2); `restore` refuses prod
   without `--allow-prod`. `ai-core.sh` wrappers added; `bash -n ai-core.sh` passes;
   changes compose cleanly with I-00122's `ai-core.sh` edits.

**S10 — docs**
3. README + CLAUDE + DB-Setup updated; new restore guide present and complete
   (safe restore, in-place swap, globals-first, identity handling, RTO, ⚠️ same-disk
   limitation). CLAUDE.md carries the agents-must-not-touch-backup-dir rule. Config
   var names + CLI commands in docs MATCH the implemented code.

**S11 — tests**
4. Integration round-trip genuinely restores into a SECOND cluster and asserts
   role-exists + matching **specific** row counts (not shape). Manual-exempt prune,
   catch-up, prod-restore guard, integrity-fail, and config-disable are all covered.
   Dashboard render test asserts the specific backup row. Correct test placement
   (unit/integration/dashboard) per `tests/CLAUDE.md`; no live-DB usage.

**Cross-cutting**
5. No hardcoded ports/paths/creds (Invariant 7). Every Boundary Behavior row maps
   to a test. Self_assess remains the final manifest step.

## Result Contract

```json
{
  "step": "S12",
  "agent": "code-review-impl",
  "work_item": "F-00092",
  "completion_status": "complete",
  "findings": [{"severity": "...", "file": "...", "issue": "...", "recommendation": "..."}],
  "approved": true,
  "notes": ""
}
```
