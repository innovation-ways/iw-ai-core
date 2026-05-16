# F-00085 — S15 Final Cross-Agent Review (Implementation + Tests)

## Summary

F-00085 is **not yet ready to merge**. The feature surface is largely in place (migration, aggregator, daemon probe hook, router, templates, and tests), but several contract-level gaps remain between the design ACs/invariants and what is actually asserted/implemented. Most importantly: AC coverage is incomplete (AC5/AC10/AC11), phase-0 safe-by-default is not yet provable from server-side rendering behavior, phase 2/3 refusal is not enforced at TOML-load boundary, and the diff modal currently introduces a Semgrep/XSS baseline regression. Default-on Phase 0 merge readiness is therefore **not approved** in this step.

## Evidence reviewed

- Design + functional docs:
  - `ai-dev/active/F-00085/F-00085_Feature_Design.md`
  - `ai-dev/active/F-00085/F-00085_Functional.md`
- Canonical reference:
  - `ai-dev/active/AUTO_MERGE_RESOLUTION.md` (§5b, rows 1.10..1.18)
- Prior reports:
  - `ai-dev/active/F-00085/reports/F-00085_S01_Database_report.md` … `F-00085_S14_CodeReview_report.md`
- Key implementation files inspected:
  - `orch/auto_merge_aggregator.py`
  - `orch/daemon/auto_merge_health.py`
  - `orch/daemon/auto_merge.py`
  - `dashboard/routers/auto_merge_ui.py`
  - `dashboard/templates/base.html`
  - `dashboard/templates/fragments/auto_merge_event_detail.html`
  - `dashboard/templates/fragments/auto_merge_settings.html`
- Test files inspected:
  - `tests/unit/test_auto_merge_aggregator.py`
  - `tests/unit/test_auto_merge_config_resolution.py`
  - `tests/unit/test_auto_merge_health.py`
  - `tests/unit/test_auto_merge_pricing.py`
  - `tests/integration/test_auto_merge_observability.py`
  - `tests/integration/test_auto_merge_control_surface.py`
  - `tests/dashboard/test_auto_merge_routes.py`

## Full test-suite run (this step)

- `make test-unit` ✅ pass (`3052 passed, 4 skipped, 5 xfailed, 2 xpassed`)
- `make test-integration` ❌ fail (`3 failed, 2568 passed, 33 skipped, 3 xfailed`)
  - Failures:
    - `tests/integration/daemon/test_phase2_apply_no_self_deadlock.py::test_i_00063_apply_does_not_self_deadlock_when_caller_holds_share_lock`
    - `tests/integration/daemon/test_phase2_apply_no_self_deadlock.py::test_i_00063_apply_succeeds_when_no_blocking_lock`
    - `tests/integration/test_security_sast_baseline.py::test_semgrep_baseline_is_zero_blocking_findings`
  - Relevant new regression for F-00085 scope: Semgrep finding on `dashboard/templates/fragments/auto_merge_event_detail.html` (`|safe` rendering path).

## Holistic checklist verdict

### Implementation × tests round-trip

- Public functions in `orch/auto_merge_aggregator.py` exercised: **mostly yes** (unit coverage present; reported ~95.85%).
- Every `auto_merge_health` emitted event type asserted: **partial** (probe success/failure/timeout asserted; no full multi-project AC5 flow assertion).
- Every endpoint in `dashboard/routers/auto_merge_ui.py` with happy+error tests: **partial** (route presence + basic error paths exist; several assertions are too shallow and AC mapping incomplete).
- `git show` boundaries (success/non-zero/timeout): **not fully covered**.
- End-to-end config resolution chain in `test_auto_merge_control_surface.py`: **incomplete** (AC10/AC11 missing).

### AC + invariant sign-off

- AC1..AC14 complete traceability: **NO** (AC5, AC10, AC11 still uncovered by direct tests).
- Invariant 1..9 enforce + fail-if-broken test: **partial**.
  - Invariant 5 (phase 2/3 rejected everywhere): API/DB paths covered; TOML loader still permissive.
  - Invariant 7 (health probe never blocks merges): not proven via integration behavior test.

### Whole-feature safety

- Phase 0 safe-by-default equivalence to F-00084: **not yet provable** (header chip container still rendered and filled via HX call, instead of strict server-side non-render gate).
- Phase 2/3 unreachable: **partial** (DB/API/UI reject, but TOML load path still accepts arbitrary phase int before later coercion).
- Refuse-list intact / F-00084 safety-list supremacy: **appears intact** in code; no contradictory changes found.
- Operator UX preserved (`merge_conflict`, `merge_failed`, retry-merge flow): **no direct regression detected** in reviewed paths.
- Health probe non-blocking merges (Inv7): **design intent present**, but no strong integration assertion proving non-blocking behavior under contention.

### Documentation completeness

- Feature design accurately reflects intended build: **yes (design quality)**.
- Functional doc accurately reflects operator-visible behavior: **partial drift risk** (claims strict phase-0 invisibility/behavior that is not fully proven by current implementation/tests).
- `AUTO_MERGE_RESOLUTION.md` §5b rows 1.10..1.18 status update needed post-merge: **yes, must be updated by follow-up/operator**.
- CLAUDE.md updates required: **none identified**.
- New invariants to promote globally: **none yet**.

### Cross-batch hygiene

- Files outside intended impacted paths: **minor drift risk** (extra touched files beyond core feature set exist; requires explicit maintainers’ confirmation before merge).
- New dependency in `pyproject.toml`: **none observed**.
- New env var required: **none observed**.
- One new migration file: **yes** (`678ac4dd44b7_f00085_observability_and_control.py`).

### Production readiness

- Default deploy (phase 0) no operator-visible change: **not yet guaranteed**.
- Per-project phase 1 enablement via Settings: **implemented**, but end-to-end dual-project behavior test missing.
- Per-project runtime swap via Settings: **implemented**, but end-to-end runtime propagation test missing.
- Rollback to phase 0 via Settings/TOML: **implemented**, needs stronger end-to-end proof.
- Probe respects per-project runtime (cost control): **implemented in code**, insufficiently validated across full flow.

## Risk register (carried)

- `git show` subprocess failure modes: router has try/except, but timeout/non-zero behaviors are not fully contract-tested.
- Per-model pricing drift: `MODEL_PRICING` remains code-resident; requires manual upkeep.
- Health probe idle cost: mitigable by `probe_interval_seconds` increase or phase=0.
- Settings concurrency: last-write-wins remains acceptable for single-operator localhost.
- JSONB row inflation: unchanged carry-over from F-00084; Phase 1 still inlines proposed content in events.

## Phase 2 readiness

- Future Phase 2 CR needs gate/apply/resume-rebase machinery (lint/type/tests/assertion scanner + `git add` + `git rebase --continue` + `--resume-rebase` implementation). F-00085 surface does not block that direction.
- Phase 1 audit events are now dashboard-visible in principle, but confidence is reduced until AC5/10/11 and diff-boundary tests are completed.

## Mandatory findings

1. **CRITICAL** — **AC coverage gap remains (AC5/AC10/AC11)**
   - Agents: `tests-impl` (+ API/backend/frontend as needed)
   - Add direct end-to-end tests for: health probe/chip transitions; per-project split behavior; runtime override propagation into execution metadata + UI.

2. **CRITICAL** — **Semgrep/SAST baseline regression in diff modal**
   - Agents: `frontend-impl`, `api-impl`
   - `auto_merge_event_detail.html` currently renders diff HTML through `|safe`; must be replaced with a safe rendering strategy acceptable to baseline security checks.

3. **HIGH** — **Phase-0 “hidden chip” invariant not strictly server-side proven**
   - Agents: `frontend-impl`, `api-impl`
   - Base layout still renders header chip container with HX load path; move to deterministic server-side non-render for phase 0.

4. **HIGH** — **Phase 2/3 refusal not enforced at TOML load boundary**
   - Agents: `pipeline-impl`, `backend-impl`
   - `AutoMergeConfig.load()` accepts arbitrary phase; enforce explicit refusal/normalization with clear diagnostics aligned to invariant 5.

5. **HIGH** — **Config/control-surface tests still shallow in critical paths**
   - Agents: `tests-impl`
   - Strengthen assertions beyond status codes/text snippets to exact Given/When/Then contractual outputs and persisted metadata fields.

6. **MEDIUM** — **Diff boundary contract not fully tested**
   - Agents: `tests-impl`
   - Add explicit tests for `git show` non-zero + timeout placeholders, plus pagination boundary and multi-file event modal behavior.

## Operator guidance after merge (once fixes land)

- Visit `/<project>/auto-merge`.
- Confirm status chip + settings reflect current resolved config.
- Optionally switch project to Phase 1 in Settings.
- Optionally select project-specific runtime model and save.

## What to watch in production

- Token-cost trend per model (7d/30d rollup).
- Health probe failure rate and degraded/down chip transitions.
- Verdict accuracy drift (`correct/wrong/partial`) to validate readiness for future Phase 2.

```json
{
  "step": "S15",
  "agent": "code-review-final-impl",
  "work_item": "F-00085",
  "decision": "request_changes",
  "verdict": "NEEDS_FIX",
  "mandatory_fix_count": 6,
  "findings": [
    "AC5/AC10/AC11 uncovered",
    "Semgrep baseline regression in diff modal",
    "Phase-0 chip non-render invariant not fully enforced",
    "TOML phase 2/3 refusal gap",
    "Control-surface assertion strength insufficient",
    "Diff/pagination boundary coverage incomplete"
  ],
  "notes": "No CLAUDE.md update required. AUTO_MERGE_RESOLUTION.md §5b rows 1.10..1.18 should be updated post-merge by follow-up/operator workflow."
}
```
