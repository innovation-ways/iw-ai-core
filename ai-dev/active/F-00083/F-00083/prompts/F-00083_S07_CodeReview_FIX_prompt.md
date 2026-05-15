# F-00083_S07_CodeReview_FIX_prompt

**Work Item**: F-00083 -- Dashboard AI Assistant — OpenCode-backed chat panel (v1)
**Step**: S07
**Agent**: code-review-fix-impl

---

## ⛔ Docker is off-limits

(Standard policy.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy.)

## Input Files

- `ai-dev/active/F-00083/F-00083_Feature_Design.md` — Design (the source of truth for what's correct)
- `ai-dev/work/F-00083/reports/F-00083_S06_CodeReview_report.md` — findings (drives this step)
- S01–S05 step reports + files they touched

## Output Files

- `ai-dev/work/F-00083/reports/F-00083_S07_CodeReview_FIX_report.md`
- Updated source files as needed

## Context

Apply fixes for all **CRITICAL** and **HIGH** findings from S06. MEDIUM and LOW findings are at-your-discretion; fix when cheap, document deferred items.

The most consequential finding patterns to expect (based on the review checklist):

1. **Regression guard**: if S06 found any edit under `dashboard/templates/chat/**` or `dashboard/static/chat/**`, revert those files to their main-branch state immediately and re-port any genuinely needed changes into `dashboard/templates/chat_assistant/**` / `dashboard/static/chat_assistant/**` instead.
2. **DOM id collisions**: rename every new id to a `chat-assistant-` prefix.
3. **Permission-block deviations**: replace `.opencode/config.json`'s permission block with the verbatim R-00074 §5 form.
4. **Password leak**: remove any `logger.*` call that includes the password; replace with a redacted indicator.

## Requirements

1. For each CRITICAL/HIGH finding from S06:
   - Read the finding's file + line + evidence.
   - Apply the minimum fix that addresses the root cause.
   - Re-run any tests the fix touches (`uv run pytest <path> -v`).
2. If a finding is contested, document it in the report under `contested_findings` with rationale.
3. Run the standard pre-flight gates.
4. Verify `git diff --stat dashboard/templates/chat/ dashboard/static/chat/` is empty after fixes.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format`
2. `make typecheck`
3. `make lint`

## Test Verification

Targeted only — the test files exercised by the code you touched.

## Subagent Result Contract

```json
{
  "step": "S07",
  "agent": "code-review-fix-impl",
  "work_item": "F-00083",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["..."],
  "preflight": {"format": "ok|fixed", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "N passed, 0 failed (targeted reruns)",
  "tdd_red_evidence": "n/a — fix step",
  "blockers": [],
  "notes": "Addressed X CRITICAL, Y HIGH. Deferred Z MEDIUM/LOW. Contested findings: N (documented). Regression-guard post-fix: PASS."
}
```
