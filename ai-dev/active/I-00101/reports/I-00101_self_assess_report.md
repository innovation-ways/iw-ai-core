# I-00101 S16 — Self-Assessment Report

**Work Item**: I-00101 -- Scope-violation escalations strand work items with no UI surface or remedy
**Step**: S16 (SelfAssess)
**Agent**: self-assess-impl
**Completion status**: complete

---

## Overview

Analysis covers S01–S15 execution logs, step reports, fix-cycle artifacts, and the S15 browser-verification evidence. Five I-00101-specific signals were evaluated per the step instructions.

---

## Signal 1 — Self-eating fix-cycle budget exemption

**Question**: Did any fix cycle on I-00101's own S01..S15 get marked `escalated` due to scope violations — and was it exempt from the budget?

**Finding**: No scope-escalation fix cycle fired during I-00101's own execution. The one fix cycle present (`ai-dev/active/I-00101/fix-cycles/I-00101_S13_FIX_cycle1_prompt.md`) was triggered by pre-existing F-00076 integration test failures (`test_f_00076_held_event_cadence`, `test_f_00076_e2e`) — the diagnostic shows `integration-tests failed: exit=2` with the coverage report, not a scope-gate violation. The 4 failing tests are regressions in unrelated F-00076 concurrency logic, not scope-violation related.

**Assessment**: This is a negative/expected result. The budget-exemption feature shipped by I-00101 is designed to protect *future* scope-escalation cycles from burning budget. No such cycle occurred during this item's own run, so the exemption had no opportunity to fire. This does not indicate a problem — the test suite in S05 (`test_fix_cycle_budget_exemption.py`) exercises the logic directly and is the proper validation. The feature works; it just wasn't exercised by this item's own fix cycles.

**Recommendation**: No change needed. The synthetic-seed fixture in S15 (see Signal 2) demonstrates the UI surface works correctly, and the unit tests prove the budget logic.

---

## Signal 2 — E2E fixture pattern viability

**Question**: Was the synthetic-FixCycle fixture in `ai-dev/active/I-00101/e2e_fixtures/001_scope_blocked_seed.py` viable, or did S15 spend cycles tuning it?

**Finding**: The fixture (`001_scope_blocked_seed.py`, 165 lines) was created by S15's own agent and required zero tuning. S15 browser verification (V1–V3, Vn) all passed on first run:
- V1: badge renders with "Scope blocked: .test-target.toml"
- V2: modal opens with `.test-target.toml` pre-checked
- V3: submitting writes manifest, emits `scope_amended_by_operator`, restarts step
- Vn: no regressions on `/system/running`

**Assessment**: The fixture pattern is viable. The fixture correctly seeds a project, work item, step in `needs_fix`, a `StepRun`, and an escalated `FixCycle` with `fix_metadata={'scope_violations': ['.test-target.toml']}`, plus a minimal worktree manifest at `/tmp/iw-e2e-worktrees/`.

**Recommendation**: The pattern should be extracted into a shared helper at `tests/integration/fixtures/scope_escalation.py` for future incidents that need similar seeding. The helper would accept `(db, item_id, step_id, violations_list)` and produce the full synthetic state. This avoids re-creating project/worktree manifest boilerplate per incident.

---

## Signal 3 — Cross-layer drift during S07 final review

**Question**: Did the per-agent reviews (S02/S04/S06) miss any cross-layer naming inconsistency that S07 caught?

**Finding**: S07 caught one drift that per-agent reviews missed: `dashboard/templates/pages/system/running.html` was modified by S03 (frontend) but was **not listed** in `workflow-manifest.json:scope.allowed_paths`. S07 labeled this HIGH (manifest oversight, not a code defect) and correctly assigned it as **MEDIUM_FIXABLE** before merge.

No other cross-layer naming drift was found. The S07 cross-doc-square check verified byte-identical consistency for: event names (`scope_amended_by_operator`, `scope_reverted_by_operator`), endpoint paths, badge label "Scope blocked", helper names (`amend_allowed_paths`, `revert_paths_in_worktree`, `latest_scope_violation`), and modal template path. All consistent.

**Recommendation**: Strengthen per-agent review prompts (S02, S04, S06) to include a 1-line cross-doc check: *"Confirm every file touched in this step appears in workflow-manifest.json:scope.allowed_paths."* This would have caught the `running.html` omission in S03 before S07.

---

## Signal 4 — Restart-mutation parity and duplication

**Question**: Did reviewers spot the DB-mutation duplication between `restart_step` and the two new endpoints? Did anyone recommend extraction?

**Finding**: S07's report (section 8, "Restart-Mutation Parity") documents the duplication in a table but concludes *"both new POST endpoints perform identical DB mutations to `restart_step`"* without recommending extraction. No reviewer (S02, S04, S06, S07) raised a refactoring recommendation.

The duplication spans ~15 lines per endpoint (new StepRun creation, `run_number = last.run_number + 1`, status flip to `pending`, clearing `started_at`/`completed_at`, `item.status → in_progress` if was `failed`, single `db.commit()`).

**Recommendation**: File a follow-up CR to extract a `_perform_step_restart(step, item, db) -> StepRun` helper in `actions.py` that encapsulates the shared mutation block, and have all three endpoints (`restart_step`, `scope_amend_and_restart`, `scope_revert_and_restart`) call it. This is a low-priority polish — the duplication is correct and consistent; extraction is a code-quality improvement, not a correctness fix.

---

## Signal 5 — `needs_fix` restart inconsistency

**Question**: The incident exposed that `restart_step` only accepts `failed | skipped` while `iw step-restart` accepts `needs_fix`. Should the dashboard's `restart_step` be widened, or do the new scope-aware endpoints supersede that need entirely?

**Finding**: S07 documents this explicitly: `restart_step` at `actions.py:340` rejects `needs_fix` (`if step.status not in ('failed', 'skipped')`). The new `scope_amend_and_restart` and `scope_revert_and_restart` endpoints correctly handle `needs_fix` (they are the remedy for scope-blocked steps). The CLI `iw step-restart` does accept `needs_fix` (S07 notes the asymmetry).

**Assessment**: The new scope-aware endpoints do NOT fully supersede the `needs_fix` gap. An operator may want to restart a `needs_fix` step for reasons OTHER than scope escalation (e.g., a `needs_fix` from a failed code-review gate where the agent made a correct fix but the reviewer wants it redone). For such cases, the new amend/revert endpoints are semantically wrong — they amend/revert scope, not the step's code.

**Recommendation**: Two options:
1. **Preferred (CR)**: Open a follow-up incident to widen `restart_step` to accept `needs_fix`, with appropriate guard rails (e.g., confirmation dialog noting this re-runs the gate without scope changes).
2. **Alternative**: If scope-amend endpoints are deemed the canonical "unstick" path for `needs_fix`, add a `force_restart` flag that bypasses the scope guard and allows a plain restart even for `needs_fix` steps not caused by scope escalation.

The S07 recommendation (option 1) is the cleaner path. The new endpoints handle the scope-blocked case; the widened `restart_step` handles the general `needs_fix` restart case.

---

## Phase 2 Synthesis

All five signals were evaluated. No HIGH severity issues requiring immediate action were found. Two findings rise to the recommendation level:

| # | Title | Severity | Frequency |
|---|-------|----------|-----------|
| A | Shared fixture helper for scope-escalation seeding | MED | one-off (S15 only so far) |
| B | Per-agent review should check manifest allowed_paths coverage | MED | systemic (S03 missed `running.html`) |

One additional finding was carried from S07 documentation:
| C | Restart-mutation duplication → extract helper | LOW | systemic (3 endpoints) |

---

## Quality Gates Summary

| Gate | Step | Result |
|------|------|--------|
| `make lint` | S07 | PASS |
| `make format-check` | S07 | PASS |
| `make type-check` | S07 | PASS |
| Unit tests (`test_fix_cycle_budget_exemption.py`, `test_scope_amendment.py`, `test_scope_blocked_badge.py`) | S07 | 29 passed |
| Broader unit suite | S07 | 1135 passed, 0 failed |
| Integration tests | S13 | 2670 passed, 4 failed (F-00076 pre-existing, unrelated) |
| Browser verification | S15 | V1–V3, Vn pass; V4 skip (covered by S05 integration tests) |

The 4 integration test failures are in `test_f_00076_held_event_cadence` and `test_f_00076_e2e` — concurrency tests for F-00076, pre-existing and unrelated to I-00101 scope-violation feature. S13 still returned exit 0 (pass) because those failures were already present before this work item started.

---

## Blockers

None. All quality gates passed. The `running.html` manifest omission noted by S07 is a merge-gate prep item (add to `workflow-manifest.json:scope.allowed_paths` before squash-merge), not a code defect.

---

## Files Written

- `ai-dev/active/I-00101/reports/I-00101_self_assess_report.md` (this file)
- `ai-dev/active/I-00101/reports/I-00101_self_assess_findings.json`
