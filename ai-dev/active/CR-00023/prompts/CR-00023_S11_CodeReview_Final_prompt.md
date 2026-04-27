# CR-00023_S11_CodeReview_Final_prompt

**Work Item**: CR-00023 — Make iw item-status the runtime source of truth for step list and per-step runtime info
**Step**: S11
**Agent**: code-review-final-impl

---

## Input Files

- `ai-dev/active/CR-00023/CR-00023_CR_Design.md` — design (all 7 ACs, including AC7 pre-flight gates fold-in)
- All prior step reports under `ai-dev/active/CR-00023/reports/` (S01–S10)
- All modified files across the chain:
  - `orch/db/models.py` (S01)
  - `orch/db/migrations/versions/<new_revision>_add_command_gate_timeout_to_workflow_steps.py` (S01)
  - `orch/cli/item_commands.py` (S03 + S05)
  - `orch/daemon/batch_manager.py` (S03)
  - `orch/daemon/fix_cycle.py` (S03)
  - 8 prompt template files (S07)
  - `docs/IW_AI_Core_CLI_Spec.md` (possibly S05)
  - `tests/unit/test_item_commands_register.py`, `tests/unit/test_item_commands_item_status.py`, `tests/unit/test_template_hints.py`, `tests/integration/test_register_to_item_status_roundtrip.py`, `tests/integration/test_daemon_legacy_fallback.py` (S09)

## Output Files

- `ai-dev/active/CR-00023/reports/CR-00023_S11_CodeReview_Final_report.md`

## Context

This is a global cross-step review. Per-step reviews (S02, S04, S06, S08, S10) caught
local issues. Your job is to verify the END-TO-END contract holds:

```
manifest field → register stores in DB column → item-status returns it →
agent uses it instead of reading the file
```

AND that the legacy fallback still works:

```
legacy item: NULL DB column → daemon reads manifest → step launches normally
```

## End-to-End Verification

### Chain integrity
- [ ] The new model columns (S01) match the kwargs passed to `WorkflowStep(...)` in `register` (S03)
- [ ] The kwargs in `register` match the keys returned by `item-status --json` (S05)
- [ ] The keys returned by `item-status --json` are the keys agents are now told to use via the template hints (S07)
- [ ] The migration `down_revision` (S01) chains correctly from the prior head with no gap (whatever that head was at run time — design-time head was `c062b6bf5eb3`)

### Fallback contract (AC4 — most critical)
- [ ] For a `WorkflowStep` row with `command IS NULL`, the daemon code paths in `_build_claude_prompt`, `_get_gate_name_and_command`, and `_compute_qv_baselines` ALL fall back to manifest read
- [ ] The fallback code is the EXACT original logic (preserved, not subtly rewritten)
- [ ] No code path silently fails when both DB and manifest yield no value (should produce a clear error or use the documented default)

### Manifest stamping (AC2)
- [ ] Stamping is idempotent (running `iw register` twice produces a byte-identical file the second time)
- [ ] All existing keys are preserved
- [ ] The `_note` text matches the contract enforced by AC2 (mentions "design-time snapshot" and "iw item-status")

### Back-compat
- [ ] Existing `iw item-status --json` consumers (look for any callers in `dashboard/` or `orch/`) still get the keys they expect
- [ ] No existing CLI command behavior changed in scope outside this CR

### Cross-cutting concerns
- [ ] Acceptance criteria AC1–AC7 are all addressable by the implementation as it stands
- [ ] No silent dependency on test data / fixture state — production code paths are self-contained
- [ ] No new dependencies were added to `pyproject.toml`

### Test coverage (now visible to the final review)
- [ ] S09's AC coverage map references a real, named test for each of AC1–AC7 (no "deferred" entries)
- [ ] AC6's `test_item_status_surfaces_db_only_step_not_in_manifest` exists and asserts the manifest file is not read (mtime unchanged or `read_text` patched to raise)
- [ ] All three daemon fallback paths (`_build_claude_prompt`, `_get_gate_name_and_command`, `_compute_qv_baselines`) have explicit AC4 tests
- [ ] Stamping idempotency, unicode-preservation, and key-preservation tests are all present (AC2)
- [ ] AC7 pre-flight section tests cover: heading present in both Implementation copies, three commands named, `preflight` field in Subagent Result Contract, byte-identity of the two copies, and ABSENCE in the other 6 in-scope templates plus FIX/Browser variants

### Documentation
- [ ] `docs/IW_AI_Core_CLI_Spec.md` mentions the new `iw item-status` JSON keys (or has a follow-up TODO if intentionally deferred)
- [ ] The CR design doc's File Manifest matches what was actually changed

### Hard rules (carried from per-step reviews)
- [ ] No `alembic upgrade/downgrade` was executed against the live DB
- [ ] No Docker compose mutations
- [ ] mypy clean across all modified `*.py` files
- [ ] `make lint` clean

## Findings Severity

- **CRITICAL**: chain breaks (e.g., `register` writes a column the model doesn't have, or `item-status` reads a column `register` doesn't write)
- **HIGH**: AC4 fallback contract violated (legacy items would fail)
- **MEDIUM**: doc drift, missing back-compat key, idempotency edge cases
- **LOW**: style, comment wording

## Subagent Result Contract

```json
{
  "step": "S11",
  "agent": "code-review-final-impl",
  "work_item": "CR-00023",
  "completion_status": "complete",
  "global_verdict": "approved|fix-required",
  "ac_coverage": {
    "AC1_item_status_enriched": "covered|gap",
    "AC2_manifest_stamped": "covered|gap",
    "AC3_schema_reversible": "covered|gap",
    "AC4_legacy_fallback": "covered|gap",
    "AC5_template_hints": "covered|gap",
    "AC6_no_step_panic": "covered|gap",
    "AC7_preflight_gates": "covered|gap"
  },
  "findings": {
    "critical": 0,
    "high": 0,
    "medium": 0,
    "low": 0
  },
  "blockers": [],
  "notes": ""
}
```
