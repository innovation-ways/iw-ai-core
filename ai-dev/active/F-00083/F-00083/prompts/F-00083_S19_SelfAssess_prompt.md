# F-00083_S19_SelfAssess_prompt

**Work Item**: F-00083 -- Dashboard AI Assistant — OpenCode-backed chat panel (v1)
**Step**: S19
**Agent**: SelfAssess

---

## ⛔ Docker is off-limits

(Standard policy. Read-only introspection — `docker ps`, `docker logs` — is allowed.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. You analyse, you do not modify migrations or the live DB.)

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var (canonical source — set by the executor).
- **Worktree logs** — `.worktrees/F-00083/ai-dev/logs/` — run logs, fix-cycle logs.
- **Item reports dir** — `ai-dev/work/F-00083/reports/` — existing step reports (secondary evidence only).

## Output Files

- `ai-dev/work/F-00083/reports/F-00083_self_assess_report.md` — Human-readable narrative analysis.
- `ai-dev/work/F-00083/reports/F-00083_self_assess_findings.json` — Structured findings JSON.

## Context

You are running the self-assessment step for **F-00083 — Dashboard AI Assistant**. This is a moderate-sized feature (19 steps, ~17 files across backend/api/frontend/tests, plus 7 per-page template edits). The project has `self_assess=true` in `projects.toml`. Use the `iw-item-analyze` skill (loaded from `.opencode/skills/iw-item-analyze/` or `.claude/skills/iw-item-analyze/`) — do NOT re-implement the analysis procedure inline.

This step is **soft** — failure does NOT block the item from merging. Produce the best report you can even if the analysis is partial.

## Focus Areas (FR-specific cues)

The most useful self-assess signals for this work item:

1. **Regression-guard fix-cycle leakage** — how many fix-cycles touched `dashboard/templates/chat/**` or `dashboard/static/chat/**` (the existing Code Q&A chat) inadvertently before being reverted? Each one is a signal that the prompts didn't emphasize the regression guard hard enough. If this happened ≥2 times, recommend that the design's invariant 1 be promoted to a CRITICAL find pattern earlier in the review chain.
2. **Permission.asked spike skipped?** — did S02's report include a verbatim captured `permission.asked` payload from a real `opencode serve` (per the pre-step spike instruction)? Or did the implementer skip the spike and use the documented shape? If skipped, did S08's review notice it? This is a prompt-template improvement signal — if the spike is the right answer, the S02 prompt should require it as a blocking precondition.
3. **DOM id collisions** — were any of the new `chat-assistant-` ids accidentally named `chat-` (colliding with the existing Code chat)? Each one is a signal that automated linting (e.g., a script that greps for unprefixed ids in new files) would have caught the issue cheaper.
4. **Ctrl+/ vs Cmd+\ collision** — did S18's regression guard catch any browser-level keybinding collision that earlier reviews missed? If so, what's the cheapest way to surface that at S06 (pre-implementation) instead?
5. **Scope creep** — did `scope.allowed_paths` need amending mid-flight? Each amendment is a signal that the design missed a file the implementer legitimately needed. Or that the implementer drifted. Distinguish the two.
6. **Test thrash on Boundary Behavior rows** — did any of the boundary-row tests (especially the runtime-crash and tab-refresh ones) fail intermittently? Flakiness in those tests is a sign of either insufficient mocking or genuine race conditions in the runtime/relay code.
7. **Browser-verification stack** — did S18 succeed, or did the worktree-compose configuration not include the `opencode` binary? If the latter, file the gap as a follow-up CR for the worktree-compose configuration, AND check if the workflow-manifest's pre-flight check (return 503 if runtime unavailable) caught it gracefully or crashed.
8. **Cross-item pattern with CR-00053** — both items are part of the same conceptual surface (CR-00053 added `--idempotency-key` to `iw next-id`; F-00083 uses chat sessions that may retry tool calls). Did either side's review surface a need for the other's behaviour that wasn't documented?
9. **Pi-portability** — did the relay layer actually stay runtime-agnostic, or did OpenCode-specific assumptions leak into `relay_manager.py` / `filters.py`? Reading the diff with that lens.

## Soft-Step Semantics

This step's failure does NOT block merge. If `iw-item-analyze` cannot complete, write a stub report explaining why and a `findings: []` JSON.

## Subagent Result Contract

```json
{
  "step": "S19",
  "agent": "self-assess-impl",
  "work_item": "F-00083",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/work/F-00083/reports/F-00083_self_assess_report.md",
    "ai-dev/work/F-00083/reports/F-00083_self_assess_findings.json"
  ],
  "preflight": {"format": "skipped:no-code-changes", "typecheck": "skipped:no-code-changes", "lint": "skipped:no-code-changes"},
  "tests_passed": true,
  "test_summary": "skipped: no tests for analysis step",
  "blockers": [],
  "notes": "Analysis completed; findings written to two output files."
}
```
