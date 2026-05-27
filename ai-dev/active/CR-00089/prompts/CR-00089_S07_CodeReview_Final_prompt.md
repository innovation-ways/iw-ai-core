# CR-00089_S07_CodeReview_Final_prompt

**Work Item**: CR-00089 -- Fix-Cycle Pipeline Systemic Hardening (I-00113 RCA Follow-up)
**Review Step**: S07 (Final Cross-Agent Review)

---

## ⛔ Docker is off-limits

(Standard policy. This step touches no Docker.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. This CR adds no migrations.)

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00089 --json`
- `ai-dev/active/CR-00089/CR-00089_CR_Design.md`
- `ai-dev/active/CR-00089/CR-00089_Functional.md`
- All `ai-dev/work/CR-00089/reports/CR-00089_S0*.md` reports
- All files listed across S01–S05 `files_changed`

## Output Files

- `ai-dev/work/CR-00089/reports/CR-00089_S07_CodeReview_Final_report.md`

## Context

You are performing the **final cross-agent global review** of CR-00089. You have access to all implementation and per-agent review output. Your job is to verify: (1) the three independent fixes are each correct in isolation, (2) they compose correctly without interfering with each other, (3) no AC is missing from the combined diff, and (4) scope discipline was maintained.

## Cross-Agent Integration Checks

### Fix 1 × Fix 2 — always_in_scope threading

- `ProjectConfig.always_in_scope_paths` from S01 is consumed at BOTH reconciliation sites in S02. If S02 only updated one site (e.g., `_complete_fix_cycle` but not `run_fix_cycle`), that is a CRITICAL gap.
- The `_build_scope_block` prompt shown to agents (in `run_fix_cycle`) uses the expanded `allowed` list. Agents will see the global files in their scope block and will not accidentally flag them as out-of-scope.

### Fix 2 × Fix 4 — Two changes in fix_cycle.py

- S02 and S04 both modified `fix_cycle.py`. Verify neither change accidentally overwrote the other. The diff must include BOTH the `always_in_scope_paths` append AND the `_GATE_RELEVANT_EXTENSIONS` constant + `_gate_is_relevant` + updated signatures.
- The `_complete_fix_cycle` function must reflect both: the always_in_scope extension at the reconciliation site AND the changed_files parameter passed to `_cascade_reset_upstream_qv_gates`.

### Fix 3 — Isolation of step_monitor.py

- S03 only touches `_check_step_health`. No other function in `step_monitor.py` was modified.
- The guard position is correct: AFTER `_probe_for_child`, BEFORE `_handle_crashed`.

### Conservative fallback (AC5) — end-to-end

- When `_files_changed_by_fix_cycle` returns `[]` (git diff failed or no files), both `_cascade_reset_upstream_qv_gates` and `_peek_cascade_reset_ids` must reset all upstream gates. Trace the call path in `_complete_fix_cycle` to confirm `changed_files or []` propagates correctly.

### _peek vs _cascade consistency

- `_peek_cascade_reset_ids` must produce the same set of step_ids as `_cascade_reset_upstream_qv_gates` would for the same inputs. If `_peek` was not updated to accept `changed_files`, the thrashing detector will preview a different (larger) reset-set than what actually executes — this would break thrashing detection for filtered cascades. CRITICAL if `_peek` signature or filter is missing.

## Final Checklist Against Design AC

| AC | Description | Status (Pass/Fail) |
|----|-------------|-------------------|
| AC1 | always_in_scope file never triggers scope violation | — |
| AC2 | Global file visible in allowed even without manifest entry | — |
| AC3 | completed_at guard skips _handle_crashed | — |
| AC4 | .txt-only change skips lint/format/typecheck gates | — |
| AC5 | Empty changed_files resets all gates (conservative) | — |
| AC6 | Missing always_in_scope in projects.toml → empty list, no error | — |

## Severity Levels

| Severity | Meaning |
|----------|---------|
| **CRITICAL** | Any AC not implemented, `_peek` not updated, either reconciliation site missing |
| **HIGH** | Mutable default arg, missing conservative fallback, guard at wrong position |
| **MEDIUM** | Convention drift, weak test assertion |
| **LOW** | Nitpick |

## Review Result Contract

```json
{
  "step": "S07",
  "agent": "code-review-final-impl",
  "work_item": "CR-00089",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "ac_status": {
    "AC1": "pass|fail",
    "AC2": "pass|fail",
    "AC3": "pass|fail",
    "AC4": "pass|fail",
    "AC5": "pass|fail",
    "AC6": "pass|fail"
  },
  "cross_agent_integration_verified": true,
  "scope_violations": [],
  "notes": ""
}
```
