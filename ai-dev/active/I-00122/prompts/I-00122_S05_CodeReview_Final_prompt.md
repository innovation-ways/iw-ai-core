# I-00122_S05_CodeReview_Final_prompt

**Work Item**: I-00122 — db-start guard against empty-DB displacement
**Step**: S05
**Agent**: code-review-final-impl

---

## ⛔ Docker is off-limits

Read-only Docker introspection only. Do not change container/volume state and do
not run `./ai-core.sh db start/stop/restart` against the live DB.

## Input Files

- `uv run iw item-status I-00122 --json`.
- `ai-dev/active/I-00122/I-00122_Issue_Design.md` and `I-00122_Functional.md`.
- All step reports in `ai-dev/active/I-00122/reports/`.
- The full diff for the item: `ai-core.sh`, `.env.example`,
  `docs/IW_AI_Core_DB_Setup.md`, `tests/unit/test_db_start_guard.py`.

## Output Files

- `ai-dev/active/I-00122/reports/I-00122_S05_CodeReview_Final_report.md`.

## Context

Global review across all of I-00122's work. Confirm the item, as a whole,
prevents the empty-DB displacement and meets its acceptance criteria.

## Review Focus

1. **End-to-end correctness** — Trace the full `cmd_db start` path with the guard
   in place. Confirm: identity pinned + DB down ⇒ refuse + no bootstrap; no
   identity ⇒ dev bootstrap preserved; DB up ⇒ no-op. The `start-prod` recovery
   path is config-driven (`IW_CORE_DB_DATA_DIR`), uses `--restart=always`, and
   does not collide with the bootstrap container name.
2. **Reproduction test integrity** — `tests/unit/test_db_start_guard.py` targets
   the displacement (asserts the specific presence/absence of the `compose ... up`
   call), is hermetic (stub docker), and is correctly placed under `tests/unit/`.
3. **Acceptance criteria** — AC1 (bug fixed) and AC2 (regression test exists) are
   both satisfied. No acceptance criterion is mis-mapped onto an implementation
   step as a "full-suite must pass" gate (Verification Placement Rule).
4. **Scope discipline** — Only the four declared files (plus `ai-dev/active/**`)
   are modified. No hardcoded ports/paths/credentials anywhere. No unrelated
   refactors. No migrations.
5. **Docs/config consistency** — `.env.example` and `docs/IW_AI_Core_DB_Setup.md`
   accurately describe the guard and recovery path and stay consistent with
   `CLAUDE.md`'s "Live DB Setup" rules and the 2026-04-22 incident narrative.
6. **Residual risk** — Note any remaining displacement vectors the fix does NOT
   cover (e.g. a supervisor that calls the bootstrap compose directly, bypassing
   `ai-core.sh`), and whether the deferred backup-tooling Feature is referenced.

## Result Contract

```json
{
  "step": "S05",
  "agent": "code-review-final-impl",
  "work_item": "I-00122",
  "completion_status": "complete",
  "findings": [{"severity": "...", "file": "...", "issue": "...", "recommendation": "..."}],
  "approved": true,
  "notes": "Summarize residual risk and any follow-ups."
}
```
