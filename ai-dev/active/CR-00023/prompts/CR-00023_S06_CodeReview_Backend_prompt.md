# CR-00023_S06_CodeReview_Backend_prompt

**Work Item**: CR-00023 — Make iw item-status the runtime source of truth for step list and per-step runtime info
**Step**: S06
**Agent**: code-review-impl

---

## Input Files

- `ai-dev/active/CR-00023/CR-00023_CR_Design.md` — design (AC1)
- `ai-dev/active/CR-00023/reports/CR-00023_S05_Backend_report.md` — S05's report
- `orch/cli/item_commands.py:527-` — modified `item_status`
- `docs/IW_AI_Core_CLI_Spec.md` — updated (if S05 found and updated the section)

## Output Files

- `ai-dev/active/CR-00023/reports/CR-00023_S06_CodeReview_Backend_report.md`

## Review Checklist

### Per-step JSON shape (AC1)
- [ ] All 12 keys are present per step entry: `step_id`, `step_number`, `label`, `agent_label`, `opencode_agent`, `type`, `step_type`, `step_label`, `status`, `description`, `prompt_file`, `command`, `gate`, `timeout_secs`
- [ ] Existing keys (`step_id`, `label`, `type`, `status`) are PRESERVED — adding `agent_label`/`step_type` next to them is correct (back-compat aliases)
- [ ] NULL DB columns serialize as JSON `null` (not `""` or omitted)
- [ ] Ordering of keys is reasonable (id/number first, identification next, status, then runtime fields)

### `current_step` enrichment
- [ ] Same field set on `current_step` as on the per-step entries (plus the existing `duration`)
- [ ] `duration` key is preserved
- [ ] No regressions in the in-progress detection (the `for s in steps: if s.status == StepStatus.in_progress: ...` loop is untouched)

### Back-compat
- [ ] No existing keys were removed or renamed
- [ ] Output remains valid JSON for existing consumers
- [ ] The non-JSON (human-readable) code path is untouched OR enhanced minimally — both are acceptable; the JSON path is the AC1 requirement

### Smoke verification
- [ ] S05 ran `uv run iw item-status I-00041 --json` and the report shows the expected new fields
- [ ] Legacy items (registered pre-CR-00023) show `null` for the three new manifest-derived columns
- [ ] An item registered after S01+S03 (none exist yet, but the test in S09 will create one) would show populated values

### Doc update
- [ ] `docs/IW_AI_Core_CLI_Spec.md`'s `iw item-status` section reflects the new fields. If S05 didn't find a relevant section, the report should explain why no doc edit was made.

### Style + Lint
- [ ] mypy clean on `orch/cli/item_commands.py`
- [ ] `make lint` clean

## Findings Severity

- **CRITICAL**: an existing key was removed or renamed (breaks back-compat)
- **HIGH**: NULL handling wrong (e.g., `""` instead of `null`); missing one of the AC1 keys
- **MEDIUM**: doc not updated; new key missing from `current_step`
- **LOW**: key ordering, comment wording

## Subagent Result Contract

```json
{
  "step": "S06",
  "agent": "code-review-impl",
  "work_item": "CR-00023",
  "completion_status": "complete",
  "files_reviewed": [
    "orch/cli/item_commands.py",
    "docs/IW_AI_Core_CLI_Spec.md"
  ],
  "findings": {
    "critical": 0,
    "high": 0,
    "medium": 0,
    "low": 0
  },
  "verdict": "approved|fix-required",
  "blockers": [],
  "notes": ""
}
```
