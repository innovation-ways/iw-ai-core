# CR-00023_S04_CodeReview_Backend_prompt

**Work Item**: CR-00023 — Make iw item-status the runtime source of truth for step list and per-step runtime info
**Step**: S04
**Agent**: code-review-impl

---

## Input Files

- `ai-dev/active/CR-00023/CR-00023_CR_Design.md` — design (AC2, AC4)
- `ai-dev/active/CR-00023/reports/CR-00023_S03_Backend_report.md` — S03's report
- `orch/cli/item_commands.py` — modified `register` (lines 145-383)
- `orch/daemon/batch_manager.py` — modified `_build_claude_prompt` and `_compute_qv_baselines`
- `orch/daemon/fix_cycle.py` — modified `_get_gate_name_and_command`

## Output Files

- `ai-dev/active/CR-00023/reports/CR-00023_S04_CodeReview_Backend_report.md`

## Review Checklist

### Register-side ingest
- [ ] `command`, `gate`, `timeout_secs` are passed to the `WorkflowStep(...)` constructor for every step
- [ ] Type coercion is defensive (`int(step_data["timeout"])` wrapped against ValueError)
- [ ] Empty/missing manifest fields produce `None` (NOT empty strings or zero) — verify NULL semantics in DB
- [ ] No silent failures: invalid `timeout` values cause `register` to error out, not silently NULL

### Manifest stamping (AC2)
- [ ] `_note` is added as the FIRST key in the JSON output (insertion order matters for human readability)
- [ ] All existing keys are preserved with identical contents (byte-for-byte after pretty-print)
- [ ] Stamping is idempotent — re-running `iw register` on an already-stamped manifest is a no-op (no double-stamp, no formatting churn)
- [ ] `ensure_ascii=False` is passed to `json.dumps` so non-ASCII characters (em-dashes, accents) survive the round-trip
- [ ] The note text contains both substrings "design-time snapshot" and "iw item-status" (required by AC5 — and indirectly by AC2)
- [ ] OSError / JSONDecodeError on the stamping step are caught and surfaced as warnings, not failures (manifest could be read-only in some test setups)

### Daemon fallback wiring (AC4)
- [ ] `_build_claude_prompt` checks DB columns FIRST; manifest read is the `if not prompt_content and manifest_path.exists()` fallback only
- [ ] `_get_gate_name_and_command` returns DB values when `step.command is not None`; falls back to manifest read otherwise
- [ ] `_compute_qv_baselines` per-step lookup uses DB-first pattern; manifest read still happens at the function top (needed for legacy items)
- [ ] The fallback code paths are EXACTLY the original manifest-read code (not subtly changed) — `git diff` should show ADD-only changes around the existing logic

### Idempotency / Safety
- [ ] `register`'s early-return for already-registered items (line ~199) is unchanged
- [ ] No accidental edits to `parse_manifest_steps` (the parser is independent of stamping)
- [ ] The S05 scope (`item_status` JSON enrichment) is NOT touched in this step

### Style + Convention
- [ ] mypy clean on the three touched files
- [ ] `make lint` clean
- [ ] Imports are alphabetized / grouped per project convention
- [ ] Inline comments reference CR-00023 for the DB-first additions (so future readers can find the context)

## Findings Severity

- **CRITICAL**: stamping is non-idempotent / mangles existing keys; daemon fallback path is broken (legacy items would fail to launch)
- **HIGH**: type coercion swallows errors silently; manifest stamping logs failure but doesn't degrade gracefully; daemon DB-first/fallback ordering wrong
- **MEDIUM**: missing inline CR reference; comment wording
- **LOW**: cosmetic

## Subagent Result Contract

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "CR-00023",
  "completion_status": "complete",
  "files_reviewed": [
    "orch/cli/item_commands.py",
    "orch/daemon/batch_manager.py",
    "orch/daemon/fix_cycle.py"
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
