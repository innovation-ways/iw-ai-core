# F-00085_S25_SelfAssess_prompt

**Work Item**: F-00085 -- Auto-Merge Resolver — Observability + Per-Project Control
**Step**: S25
**Agent**: SelfAssess

---

## ⛔ Docker is off-limits

Standard policy. Read-only `docker ps` / `docker inspect` permitted.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This analysis step performs NO database mutations.

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var.
- **Worktree logs** — `.worktrees/F-00085/ai-dev/logs/`.
- **Item reports dir** — `ai-dev/active/F-00085/reports/`.

## Output Files

- `ai-dev/active/F-00085/reports/F-00085_self_assess_report.md`
- `ai-dev/active/F-00085/reports/F-00085_self_assess_findings.json`

## Context

You are running the self-assessment for **F-00085 — Auto-Merge Resolver Observability + Per-Project Control**. Use the **`iw-item-analyze` skill** to produce the standard two-output deliverable.

## F-00085-Specific Focus Areas

In addition to the standard `iw-item-analyze` checks (agent thrash, tool failures, prompt gaps, manifest issues), pay specific attention to:

1. **Multi-layer cross-cut**: this Feature touches Database → Pipeline → Backend → API → Frontend layers in sequence (S01 → S04 → S06 → S08 → S10). Look for cross-layer prompt gaps that caused fix cycles: did S06 / S08 / S10 each have enough info about their upstream's contract, or did they thrash trying to reverse-engineer it?

2. **Browser verification readiness**: S24 requires multiple e2e fixture files (`001_phase0_for_test_project.py`, `002_phase1_with_runtime.py`, `003_seeded_events.py`, `004_refuse_list_events.py`). Did S24 have to write all of these mid-flight, or did one of S13 / S15's reviews flag the need ahead of time? If the operator had to fight ENV_DATA_MISSING multiple times, that's a prompt gap to flag.

3. **F-00084 backward compatibility**: did any fix cycle break F-00084's existing tests? The `merge_queue.py` edit in S06 is the highest-risk diff for that — flag if `tests/integration/test_auto_merge_phase1.py` (from F-00084) regressed at any step.

4. **Refuse-list defence-in-depth verification**: the Settings UI excludes disabled runtimes from the dropdown, AND the API re-validates. Was this dual layer actually tested in S13/S24, or did one of them get implicitly skipped?

5. **Phase 2/3 reservation**: the CHECK constraint (S01), API validation (S08), and UI dropdown (S10) all refuse phase=2/3. Did any cycle attempt to soften this (e.g., "phase 2 is reserved" was changed to a warning instead of a 400)? If so, flag.

6. **JSONB metadata size**: F-00084's Invariant 5 caps event metadata at 256 KB. F-00085's diff viewer reads from the same metadata. Did anything in S08/S10 try to bypass the cap (e.g., by accepting truncated content silently)?

7. **`auto_merge_config_invalid` event spam**: S06's resolve_project_config emits this event when a per-project row points at a disabled runtime — but only on state transitions. Did the implementation actually track state transitions, or does it spam an event every merge?

8. **Token-cost arithmetic**: AC8 has explicit numbers ($0.06 per event with claude-sonnet-4-6, 10K input + 2K output). Did the test for AC8 use exact-match assertions or a `pytest.approx` (which would be wrong for a $-value derived from integer token counts)?

## Soft-Step Semantics

Failure does NOT block merge. Produce a usable report regardless.

## Subagent Result Contract

```json
{
  "step": "S25",
  "agent": "self-assess-impl",
  "work_item": "F-00085",
  "completion_status": "complete",
  "files_changed": [
    "ai-dev/active/F-00085/reports/F-00085_self_assess_report.md",
    "ai-dev/active/F-00085/reports/F-00085_self_assess_findings.json"
  ],
  "preflight": {
    "format": "skipped:no-code-changes",
    "typecheck": "skipped:no-code-changes",
    "lint": "skipped:no-code-changes"
  },
  "tests_passed": true,
  "test_summary": "skipped: no tests for analysis step",
  "blockers": [],
  "notes": "F-00085 ships observability + control. Focus on multi-layer cross-cut prompt completeness; backward compat with F-00084; defence-in-depth on disabled runtime."
}
```
